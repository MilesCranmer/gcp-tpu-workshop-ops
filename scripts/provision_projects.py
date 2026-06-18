#!/usr/bin/env python3
"""Create/configure workshop projects up to the pre-participant-IAM gate."""
from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from common import expected_budget_display_name, load_config, load_participants, project_id_for, project_resource_name, run_gcloud, shell_join

@dataclass
class Action:
    project_id: str
    step: str
    applied: bool
    ok: bool
    command: str
    stdout: str = ''
    stderr: str = ''


def do(actions: list[Action], project_id: str, step: str, cmd: list[str], args) -> None:
    if not args.apply:
        actions.append(Action(project_id, step, False, True, shell_join(cmd)))
        return
    code, out, err = run_gcloud(cmd, config_dir=args.cloudsdk_config, gcloud_bin=args.gcloud_bin)
    actions.append(Action(project_id, step, True, code == 0, shell_join(cmd), out[-2000:], err[-4000:]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', type=Path, required=True)
    ap.add_argument('--participants', type=Path, required=True)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--cloudsdk-config')
    ap.add_argument('--gcloud-bin', default='gcloud')
    ap.add_argument('--out', type=Path, default=Path('out/provision_projects_actions.json'))
    args = ap.parse_args()

    config = load_config(args.config)
    participants = load_participants(args.participants, config)
    actions: list[Action] = []

    for row in participants:
        participant_id = row['participant_id'].strip()
        project_id = project_id_for(config, participant_id)
        display_name = expected_budget_display_name(config, project_id)

        do(actions, project_id, 'project_create', ['projects', 'create', project_id, '--name', project_id, '--quiet'], args)
        do(actions, project_id, 'billing_link', ['billing', 'projects', 'link', project_id, '--billing-account', config['billing_account'], '--quiet'], args)
        for service in config.get('required_services', []):
            do(actions, project_id, f'enable_service:{service}', ['services', 'enable', service, '--project', project_id, '--quiet'], args)
        for role in config.get('kill_switch_project_roles', []):
            do(actions, project_id, f'kill_switch_iam:{role}', ['projects', 'add-iam-policy-binding', project_id, '--member', f"serviceAccount:{config['kill_switch_service_account']}", '--role', role, '--condition', 'None', '--quiet'], args)
        budget_cmd = [
            'billing', 'budgets', 'create',
            '--billing-account', config['billing_account'],
            '--display-name', display_name,
            '--budget-amount', f"{config['budget_amount_usd']}USD",
            '--filter-projects', project_resource_name(project_id),
            '--notifications-rule-pubsub-topic', config['budget_topic'],
            '--threshold-rule', 'percent=0.5,basis=current-spend',
            '--threshold-rule', 'percent=0.9,basis=current-spend',
            '--threshold-rule', 'percent=1.0,basis=current-spend',
            '--threshold-rule', 'percent=1.0,basis=forecasted-spend',
            '--credit-types-treatment', config.get('budget_credit_treatment', 'exclude-all-credits'),
            '--calendar-period', config.get('budget_calendar_period', 'year'),
            '--quiet',
        ]
        do(actions, project_id, 'budget_create', budget_cmd, args)

        tpu = config['tpu']
        zones = sorted(set(tpu.get('v6e_zones', [tpu['allowed_zone']])))
        repo_root = Path(__file__).resolve().parents[1]
        helper = Path('scripts/apply_tpu_quota_caps.py')
        allowed_cmd = ['python3', str(helper), '--project', project_id, '--zone', tpu['allowed_zone'], '--max-v6e-cores', str(tpu['max_v6e_cores']), '--preemptible-v6e-cores', str(tpu.get('preemptible_v6e_cores', 0)), '--gcloud-bin', args.gcloud_bin]
        if args.cloudsdk_config:
            allowed_cmd += ['--cloudsdk-config', args.cloudsdk_config]
        if args.apply:
            allowed_cmd.append('--apply')
        if args.apply:
            proc = subprocess.run(allowed_cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            actions.append(Action(project_id, 'quota_allowed_zone', True, proc.returncode == 0, shell_join(allowed_cmd), proc.stdout[-2000:], proc.stderr[-4000:]))
        else:
            actions.append(Action(project_id, 'quota_allowed_zone', False, True, shell_join(allowed_cmd)))
        denied = [z for z in zones if z != tpu['allowed_zone']]
        if denied:
            denied_cmd = ['python3', str(helper), '--project', project_id, '--max-v6e-cores', '0', '--preemptible-v6e-cores', '0', '--gcloud-bin', args.gcloud_bin]
            for z in denied:
                denied_cmd += ['--zone', z]
            if args.cloudsdk_config:
                denied_cmd += ['--cloudsdk-config', args.cloudsdk_config]
            if args.apply:
                denied_cmd.append('--apply')
            if args.apply:
                proc = subprocess.run(denied_cmd, cwd=repo_root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                actions.append(Action(project_id, 'quota_disallowed_zones', True, proc.returncode == 0, shell_join(denied_cmd), proc.stdout[-2000:], proc.stderr[-4000:]))
            else:
                actions.append(Action(project_id, 'quota_disallowed_zones', False, True, shell_join(denied_cmd)))

    payload = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'apply': args.apply, 'actions': [asdict(a) for a in actions]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))
    return 0 if all(a.ok for a in actions) else 1

if __name__ == '__main__':
    raise SystemExit(main())
