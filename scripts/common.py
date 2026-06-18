#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

PROJECT_ID_RE = re.compile(r'^[a-z][a-z0-9-]{4,28}[a-z0-9]$')
PARTICIPANT_ID_RE = re.compile(r'^[a-z][a-z0-9-]{1,20}$')
BILLING_ACCOUNT_RE = re.compile(r'^[A-F0-9]{6}-[A-F0-9]{6}-[A-F0-9]{6}$')
PUBSUB_TOPIC_RE = re.compile(r'^projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/topics/[A-Za-z][A-Za-z0-9._~-]{2,254}$')
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def load_config(path: Path) -> dict[str, Any]:
    with path.open() as f:
        config = json.load(f)
    validate_config(config)
    return config


def load_participants(path: Path, config: dict[str, Any] | None = None) -> list[dict[str, str]]:
    with path.open() as f:
        rows = list(csv.DictReader(f, delimiter='\t'))
    required = {'participant_id', 'google_email'}
    missing = required - set(rows[0].keys() if rows else [])
    if missing:
        raise SystemExit(f'participant file missing columns: {sorted(missing)}')
    if config is not None:
        validate_participants(rows, config)
    return rows


def project_id_for(config: dict[str, Any], participant_id: str) -> str:
    return config['project_pattern'].format(participant_id=participant_id)


def project_resource_name(project_id: str) -> str:
    return f'projects/{project_id}'


def expected_budget_display_name(config: dict[str, Any], project_id: str) -> str:
    return f"{config['budget_prefix']}{project_id} ${config['budget_amount_usd']}"


def validate_config(config: dict[str, Any]) -> None:
    required = {
        'billing_account', 'control_project', 'budget_topic', 'kill_switch_service_account',
        'project_pattern', 'budget_prefix', 'budget_amount_usd', 'participant_roles',
        'kill_switch_project_roles', 'tpu',
    }
    missing = sorted(required - set(config))
    if missing:
        raise SystemExit(f'config missing required keys: {missing}')

    billing = str(config['billing_account'])
    if billing == 'XXXXXX-XXXXXX-XXXXXX' or not BILLING_ACCOUNT_RE.match(billing):
        raise SystemExit('billing_account must be a real billing account id like ABCDEF-123456-789ABC, not the placeholder')

    if not PROJECT_ID_RE.match(str(config['control_project'])):
        raise SystemExit('control_project must be a valid Google Cloud project id')

    if not PUBSUB_TOPIC_RE.match(str(config['budget_topic'])):
        raise SystemExit('budget_topic must be a full Pub/Sub topic resource: projects/{project_id}/topics/{topic_id}')

    if not str(config['budget_prefix']).endswith(':'):
        raise SystemExit('budget_prefix should end with a delimiter such as : to avoid project-id prefix collisions')

    try:
        amount = int(config['budget_amount_usd'])
    except (TypeError, ValueError):
        raise SystemExit('budget_amount_usd must be an integer')
    if amount <= 0:
        raise SystemExit('budget_amount_usd must be positive')

    tpu = config.get('tpu') or {}
    for key in ['allowed_zone', 'max_v6e_cores', 'v6e_zones']:
        if key not in tpu:
            raise SystemExit(f'tpu.{key} is required')
    if tpu['allowed_zone'] not in tpu.get('v6e_zones', []):
        raise SystemExit('tpu.allowed_zone must be included in tpu.v6e_zones')
    if int(tpu['max_v6e_cores']) < 0 or int(tpu.get('preemptible_v6e_cores', 0)) < 0:
        raise SystemExit('TPU quota values must be non-negative')


def validate_participants(rows: list[dict[str, str]], config: dict[str, Any]) -> None:
    seen_projects: set[str] = set()
    for i, row in enumerate(rows, start=2):
        participant_id = (row.get('participant_id') or '').strip()
        google_email = (row.get('google_email') or '').strip()
        if not PARTICIPANT_ID_RE.match(participant_id):
            raise SystemExit(f'participant_id on row {i} must match {PARTICIPANT_ID_RE.pattern}')
        if not EMAIL_RE.match(google_email):
            raise SystemExit(f'google_email on row {i} is not a valid-looking email')
        project_id = project_id_for(config, participant_id)
        if not PROJECT_ID_RE.match(project_id):
            raise SystemExit(f'generated project id is invalid on row {i}: {project_id}')
        if project_id in seen_projects:
            raise SystemExit(f'duplicate generated project id: {project_id}')
        seen_projects.add(project_id)


def run_gcloud(args: list[str], *, config_dir: str | None = None, gcloud_bin: str = 'gcloud') -> tuple[int, str, str]:
    env = os.environ.copy()
    if config_dir:
        env['CLOUDSDK_CONFIG'] = config_dir
    p = subprocess.run([gcloud_bin, *args], env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def gcloud_json(args: list[str], *, config_dir: str | None = None, gcloud_bin: str = 'gcloud'):
    code, out, err = run_gcloud([*args, '--format=json'], config_dir=config_dir, gcloud_bin=gcloud_bin)
    if code != 0:
        return None, err
    try:
        return json.loads(out or 'null'), ''
    except json.JSONDecodeError as exc:
        return None, f'json parse failed: {exc}: {out[:200]}'


def shell_join(action: list[str]) -> str:
    import shlex
    return ' '.join(shlex.quote(str(x)) for x in action)


def print_action(apply: bool, action: list[str]) -> None:
    prefix = 'APPLY' if apply else 'DRY_RUN'
    print(prefix + ': ' + shell_join(action))
