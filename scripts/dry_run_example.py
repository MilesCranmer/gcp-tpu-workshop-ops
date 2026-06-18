#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    cfg = json.loads((ROOT / 'examples/workshop.config.example.json').read_text())
    cfg['billing_account'] = 'ABCDEF-123456-789ABC'
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        config = td_path / 'workshop.config.json'
        config.write_text(json.dumps(cfg))
        subprocess.run([sys.executable, str(ROOT / 'scripts/provision_projects.py'), '--config', str(config), '--participants', str(ROOT / 'examples/participants.example.tsv'), '--out', str(td_path / 'provision.json')], check=True)
        subprocess.run([sys.executable, str(ROOT / 'scripts/final_add_participants.py'), '--config', str(config), '--participants', str(ROOT / 'examples/participants.example.tsv'), '--out', str(td_path / 'final.json')], check=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
