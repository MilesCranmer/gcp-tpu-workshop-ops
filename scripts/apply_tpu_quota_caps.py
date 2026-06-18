#!/usr/bin/env python3
"""Apply or dry-run TPU v6e quota caps for workshop projects."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from common import run_gcloud

QUOTAS = {
    'on_demand': 'TPUV6EPerProjectPerZoneForTPUAPI',
    'preemptible': 'TPUV6EPreemptiblePerProjectPerZoneForTPUAPI',
}

@dataclass
class Action:
    project_id: str
    quota_id: str
    zone: str
    preferred_value: int
    preference_id: str
    applied: bool
    ok: bool
    stdout: str = ''
    stderr: str = ''


def preference_id(kind: str, zone: str) -> str:
    return f'workshop_{kind}_v6e_{zone.replace("-", "_")}'


def create_or_update(project_id: str, quota_id: str, zone: str, value: int, kind: str, args) -> Action:
    pref = preference_id(kind, zone)
    create = [
        'beta', 'quotas', 'preferences', 'create',
        '--project', project_id,
        '--billing-project', project_id,
        '--service', 'tpu.googleapis.com',
        '--quota-id', quota_id,
        '--dimensions', f'zone={zone}',
        '--preferred-value', str(value),
        '--preference-id', pref,
        '--allow-high-percentage-quota-decrease',
        '--allow-quota-decrease-below-usage',
        '--justification', 'Workshop safety cap: prevent delayed-billing TPU overspend.',
        '--quiet',
    ]
    if not args.apply:
        return Action(project_id, quota_id, zone, value, pref, False, True, 'DRY RUN: ' + ' '.join(create))
    code, out, err = run_gcloud(create, config_dir=args.cloudsdk_config, gcloud_bin=args.gcloud_bin)
    if code != 0 and 'already exist' in err.lower():
        update = [
            'beta', 'quotas', 'preferences', 'update', pref,
            '--project', project_id,
            '--billing-project', project_id,
            '--service', 'tpu.googleapis.com',
            '--quota-id', quota_id,
            '--dimensions', f'zone={zone}',
            '--preferred-value', str(value),
            '--allow-high-percentage-quota-decrease',
            '--allow-quota-decrease-below-usage',
            '--justification', 'Workshop safety cap: prevent delayed-billing TPU overspend.',
            '--quiet',
        ]
        code, out, err = run_gcloud(update, config_dir=args.cloudsdk_config, gcloud_bin=args.gcloud_bin)
    return Action(project_id, quota_id, zone, value, pref, True, code == 0, out[-2000:], err[-4000:])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', required=True, action='append')
    ap.add_argument('--zone', action='append', required=True)
    ap.add_argument('--max-v6e-cores', type=int, required=True)
    ap.add_argument('--preemptible-v6e-cores', type=int, default=0)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--cloudsdk-config')
    ap.add_argument('--gcloud-bin', default='gcloud')
    ap.add_argument('--out', type=Path, default=Path('out/tpu_quota_cap_actions.json'))
    args = ap.parse_args()

    actions: list[Action] = []
    for project in args.project:
        if args.apply:
            code, out, err = run_gcloud(['services', 'enable', 'cloudquotas.googleapis.com', '--project', project, '--quiet'], config_dir=args.cloudsdk_config, gcloud_bin=args.gcloud_bin)
            actions.append(Action(project, 'cloudquotas.googleapis.com', 'global', 1, 'enable_api', True, code == 0, out[-2000:], err[-4000:]))
        for zone in args.zone:
            actions.append(create_or_update(project, QUOTAS['on_demand'], zone, args.max_v6e_cores, 'ondemand', args))
            actions.append(create_or_update(project, QUOTAS['preemptible'], zone, args.preemptible_v6e_cores, 'preemptible', args))

    payload = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'apply': args.apply, 'actions': [asdict(a) for a in actions]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))
    return 0 if all(a.ok for a in actions) else 1

if __name__ == '__main__':
    raise SystemExit(main())
