#!/usr/bin/env python3
"""Read-only verifier for workshop participant projects."""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from common import (
    expected_budget_display_name,
    gcloud_json,
    load_config,
    load_participants,
    project_id_for,
    project_resource_name,
)

V6E_ON_DEMAND = 'TPUV6EPerProjectPerZoneForTPUAPI'
V6E_PREEMPTIBLE = 'TPUV6EPreemptiblePerProjectPerZoneForTPUAPI'


@dataclass
class ControlPlaneCheck:
    topic_exists: bool | None
    function_exists: bool | None
    notes: str = ''


@dataclass
class Check:
    participant_id: str
    project_id: str
    project_exists: bool
    billing_enabled: bool | None
    billing_account_ok: bool | None
    required_services_ok: bool | None
    missing_services: list[str]
    budget_found: bool | None
    budget_amount_ok: bool | None
    budget_topic_ok: bool | None
    budget_scope_ok: bool | None
    budget_credit_treatment_ok: bool | None
    kill_switch_roles_ok: bool | None
    participant_iam_absent: bool | None
    quota_cap_ok: bool | None
    quota_cap_note: str
    live_tpu_count: int | None
    live_tpus_ok: bool | None
    notes: str = ''


def find_budget_for_project(budgets: list[dict], budget_prefix: str, project_id: str) -> dict | None:
    # Require a delimiter after project_id. This avoids prefix collisions such as
    # dis-2026-tpu-alice matching dis-2026-tpu-alice01.
    pattern = re.compile(rf'^{re.escape(budget_prefix + project_id)}(?:\s|$)')
    matches = [b for b in budgets if pattern.match(str(b.get('displayName', '')))]
    if len(matches) > 1:
        raise RuntimeError(f'multiple budgets match {budget_prefix}{project_id}: {[m.get("name") for m in matches]}')
    return matches[0] if matches else None


def budget_scope_matches(budget: dict, project_id: str) -> bool:
    projects = (budget.get('budgetFilter', {}) or {}).get('projects', []) or []
    return projects == [project_resource_name(project_id)]


def quota_value_for_zone(quota: dict, zone: str) -> int | None:
    for info in quota.get('dimensionsInfos', []) or []:
        dims = info.get('dimensions', {}) or {}
        locations = info.get('applicableLocations', []) or []
        if dims.get('zone') == zone or zone in locations:
            raw = (info.get('details', {}) or {}).get('value')
            if raw is None and dims.get('zone') == zone:
                return 0
            if raw is None:
                return None
            try:
                return int(raw)
            except (TypeError, ValueError):
                return None
    return None


def check_quota(project_id: str, config: dict, args) -> tuple[bool | None, str]:
    quotas, err = gcloud_json([
        'beta', 'quotas', 'info', 'list',
        '--service', 'tpu.googleapis.com',
        '--project', project_id,
        '--billing-project', project_id,
    ], config_dir=args.cloudsdk_config, gcloud_bin=args.gcloud_bin)
    if not isinstance(quotas, list):
        return None, err or 'could not read quota info'
    by_id = {q.get('quotaId'): q for q in quotas if isinstance(q, dict)}
    on_demand = by_id.get(V6E_ON_DEMAND)
    preemptible = by_id.get(V6E_PREEMPTIBLE)
    if not on_demand or not preemptible:
        return None, 'missing v6e quota info'
    tpu = config['tpu']
    allowed = tpu['allowed_zone']
    expected_allowed = int(tpu['max_v6e_cores'])
    expected_preemptible = int(tpu.get('preemptible_v6e_cores', 0))
    problems = []
    for zone in tpu.get('v6e_zones', [allowed]):
        od = quota_value_for_zone(on_demand, zone)
        pr = quota_value_for_zone(preemptible, zone)
        expected_od = expected_allowed if zone == allowed else 0
        expected_pr = expected_preemptible if zone == allowed else 0
        if od != expected_od:
            problems.append(f'{zone} on-demand={od}, expected {expected_od}')
        if pr != expected_pr:
            problems.append(f'{zone} preemptible={pr}, expected {expected_pr}')
    if problems:
        return False, '; '.join(problems)
    return True, 'quota caps match config'


def iam_bindings(policy: dict) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for binding in policy.get('bindings', []) or []:
        result.setdefault(binding.get('role', ''), set()).update(binding.get('members', []) or [])
    return result


def check_control_plane(config: dict, args) -> ControlPlaneCheck:
    topic_parts = config['budget_topic'].split('/')
    topic_project = topic_parts[1]
    topic_name = topic_parts[3]
    topic, topic_err = gcloud_json(['pubsub', 'topics', 'describe', topic_name, '--project', topic_project], config_dir=args.cloudsdk_config, gcloud_bin=args.gcloud_bin)
    function_name = config.get('function_name', 'workshop-budget-kill-switch')
    function_region = config.get('function_region', 'europe-west2')
    fn, fn_err = gcloud_json(['functions', 'describe', function_name, '--gen2', '--region', function_region, '--project', config['control_project']], config_dir=args.cloudsdk_config, gcloud_bin=args.gcloud_bin)
    return ControlPlaneCheck(
        topic_exists=isinstance(topic, dict),
        function_exists=isinstance(fn, dict),
        notes='; '.join(x for x in [topic_err if not topic else '', fn_err if not fn else ''] if x),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', type=Path, required=True)
    ap.add_argument('--participants', type=Path, required=True)
    ap.add_argument('--allow-live-tpus', action='store_true', help='Do not fail verification only because TPU VMs are currently present')
    ap.add_argument('--skip-control-plane', action='store_true', help='Skip Pub/Sub topic and Cloud Function existence checks')
    ap.add_argument('--cloudsdk-config')
    ap.add_argument('--gcloud-bin', default='gcloud')
    ap.add_argument('--out', type=Path, default=Path('out/verify_projects.json'))
    args = ap.parse_args()

    config = load_config(args.config)
    participants = load_participants(args.participants, config)
    budgets, budget_err = gcloud_json(['billing', 'budgets', 'list', '--billing-account', config['billing_account']], config_dir=args.cloudsdk_config, gcloud_bin=args.gcloud_bin)
    if budgets is None:
        budgets = []

    control = None if args.skip_control_plane else check_control_plane(config, args)
    checks: list[Check] = []
    for row in participants:
        participant_id = row['participant_id'].strip()
        project_id = project_id_for(config, participant_id)
        project, project_err = gcloud_json(['projects', 'describe', project_id], config_dir=args.cloudsdk_config, gcloud_bin=args.gcloud_bin)
        billing, billing_err = gcloud_json(['beta', 'billing', 'projects', 'describe', project_id], config_dir=args.cloudsdk_config, gcloud_bin=args.gcloud_bin)
        services, services_err = gcloud_json(['services', 'list', '--enabled', '--project', project_id], config_dir=args.cloudsdk_config, gcloud_bin=args.gcloud_bin)
        enabled_services = {s.get('config', {}).get('name') for s in services or [] if isinstance(s, dict)} if isinstance(services, list) else set()
        missing_services = sorted(set(config.get('required_services', [])) - enabled_services)
        try:
            budget = find_budget_for_project(budgets, config['budget_prefix'], project_id)
            budget_lookup_note = ''
        except RuntimeError as exc:
            budget = None
            budget_lookup_note = str(exc)

        tpu_count = 0
        tpu_notes = []
        for zone in config['tpu'].get('v6e_zones', [config['tpu']['allowed_zone']]):
            tpus, err = gcloud_json(['compute', 'tpus', 'tpu-vm', 'list', '--project', project_id, '--zone', zone], config_dir=args.cloudsdk_config, gcloud_bin=args.gcloud_bin)
            if isinstance(tpus, list):
                tpu_count += len(tpus)
            elif err:
                tpu_notes.append(f'{zone}: {err[:120]}')
        filt = budget.get('budgetFilter', {}) if budget else {}
        quota_ok, quota_note = check_quota(project_id, config, args)

        policy, policy_err = gcloud_json(['projects', 'get-iam-policy', project_id], config_dir=args.cloudsdk_config, gcloud_bin=args.gcloud_bin)
        bindings = iam_bindings(policy or {}) if isinstance(policy, dict) else {}
        ks_member = f"serviceAccount:{config['kill_switch_service_account']}"
        kill_roles_ok = all(ks_member in bindings.get(role, set()) for role in config.get('kill_switch_project_roles', [])) if isinstance(policy, dict) else None
        participant_member = f"user:{row['google_email'].strip()}"
        participant_iam_absent = all(participant_member not in bindings.get(role, set()) for role in config.get('participant_roles', [])) if isinstance(policy, dict) else None
        live_tpus_ok = (tpu_count == 0) or args.allow_live_tpus if not tpu_notes else None

        checks.append(Check(
            participant_id=participant_id,
            project_id=project_id,
            project_exists=isinstance(project, dict),
            billing_enabled=(billing or {}).get('billingEnabled') if isinstance(billing, dict) else None,
            billing_account_ok=((billing or {}).get('billingAccountName') == f"billingAccounts/{config['billing_account']}") if isinstance(billing, dict) else None,
            required_services_ok=(len(missing_services) == 0) if isinstance(services, list) else None,
            missing_services=missing_services,
            budget_found=budget is not None,
            budget_amount_ok=(str((budget or {}).get('amount', {}).get('specifiedAmount', {}).get('units')) == str(config['budget_amount_usd'])) if budget else None,
            budget_topic_ok=((budget or {}).get('notificationsRule', {}).get('pubsubTopic') == config['budget_topic']) if budget else None,
            budget_scope_ok=budget_scope_matches(budget, project_id) if budget else None,
            budget_credit_treatment_ok=(filt.get('creditTypesTreatment') == str(config.get('budget_credit_treatment', 'exclude-all-credits')).upper().replace('-', '_')) if budget else None,
            kill_switch_roles_ok=kill_roles_ok,
            participant_iam_absent=participant_iam_absent,
            quota_cap_ok=quota_ok,
            quota_cap_note=quota_note,
            live_tpu_count=tpu_count if not tpu_notes else None,
            live_tpus_ok=live_tpus_ok,
            notes='; '.join(x for x in [
                project_err if not project else '', billing_err if not billing else '', services_err if services is None else '',
                budget_err if budget_err else '', budget_lookup_note, policy_err if policy is None else '', '; '.join(tpu_notes)
            ] if x),
        ))

    payload = {
        'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'control_plane': asdict(control) if control else None,
        'checks': [asdict(c) for c in checks],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))
    control_ok = True if control is None else bool(control.topic_exists and control.function_exists)
    checks_ok = all(
        c.project_exists and c.billing_enabled and c.billing_account_ok and c.required_services_ok and
        c.budget_found and c.budget_amount_ok and c.budget_topic_ok and c.budget_scope_ok and
        c.budget_credit_treatment_ok and c.kill_switch_roles_ok and c.participant_iam_absent and
        c.quota_cap_ok and c.live_tpus_ok
        for c in checks
    )
    return 0 if control_ok and checks_ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
