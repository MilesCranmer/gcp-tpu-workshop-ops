#!/usr/bin/env python3
"""Final approval-gated participant IAM rollout."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from common import load_config, load_participants, project_id_for, run_gcloud, shell_join

@dataclass
class Action:
    participant_id: str
    project_id: str
    member: str
    role: str
    applied: bool
    ok: bool
    command: str
    stdout: str = ''
    stderr: str = ''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', type=Path, required=True)
    ap.add_argument('--participants', type=Path, required=True)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--approval-token', default='')
    ap.add_argument('--cloudsdk-config')
    ap.add_argument('--gcloud-bin', default='gcloud')
    ap.add_argument('--out', type=Path, default=Path('out/final_add_participants_actions.json'))
    args = ap.parse_args()

    if args.apply and args.approval_token != 'ADD_PARTICIPANTS_FINAL':
        raise SystemExit('Refusing to apply: pass --approval-token ADD_PARTICIPANTS_FINAL after final approval.')

    config = load_config(args.config)
    actions: list[Action] = []
    for row in load_participants(args.participants, config):
        participant_id = row['participant_id'].strip()
        project_id = project_id_for(config, participant_id)
        member = f"user:{row['google_email'].strip()}"
        for role in config['participant_roles']:
            cmd = ['projects', 'add-iam-policy-binding', project_id, '--member', member, '--role', role, '--condition', 'None', '--quiet']
            if args.apply:
                code, out, err = run_gcloud(cmd, config_dir=args.cloudsdk_config, gcloud_bin=args.gcloud_bin)
                actions.append(Action(participant_id, project_id, member, role, True, code == 0, shell_join(cmd), out[-2000:], err[-4000:]))
            else:
                actions.append(Action(participant_id, project_id, member, role, False, True, shell_join(cmd)))

    payload = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'apply': args.apply, 'actions': [asdict(a) for a in actions]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))
    return 0 if all(a.ok for a in actions) else 1

if __name__ == '__main__':
    raise SystemExit(main())
