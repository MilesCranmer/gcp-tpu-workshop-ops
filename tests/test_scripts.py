from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import common  # noqa: E402
import verify_projects  # noqa: E402


def write(path: Path, text: str) -> Path:
    path.write_text(text)
    return path


def example_config() -> dict:
    return json.loads((ROOT / "examples/workshop.config.example.json").read_text())


class ScriptBehaviorTests(unittest.TestCase):
    def test_generated_budget_filter_uses_project_resource_name(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            config = td_path / "config.json"
            participants = td_path / "participants.tsv"
            out = td_path / "out.json"
            cfg = example_config()
            cfg["billing_account"] = "ABCDEF-123456-789ABC"
            write(config, json.dumps(cfg))
            write(participants, "participant_id\tinstitutional_email\tname\tgoogle_email\nalice01\talice@example.edu\tAlice\talice@example.edu\n")
            subprocess.run(
                [sys.executable, str(ROOT / "scripts/provision_projects.py"), "--config", str(config), "--participants", str(participants), "--out", str(out)],
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            )
            payload = json.loads(out.read_text())
            budget_actions = [a for a in payload["actions"] if a["step"] == "budget_create"]
            self.assertTrue(budget_actions)
            self.assertIn("--filter-projects projects/dis-2026-tpu-alice01", budget_actions[0]["command"])

    def test_exact_budget_match_rejects_prefix_collision(self):
        budget_alice01 = {"displayName": "DIS2026_CAP:dis-2026-tpu-alice01 $500"}
        self.assertIsNone(verify_projects.find_budget_for_project([budget_alice01], "DIS2026_CAP:", "dis-2026-tpu-alice"))
        self.assertIs(verify_projects.find_budget_for_project([budget_alice01], "DIS2026_CAP:", "dis-2026-tpu-alice01"), budget_alice01)

    def test_budget_scope_must_equal_expected_project_resource(self):
        self.assertTrue(verify_projects.budget_scope_matches({"budgetFilter": {"projects": ["projects/dis-2026-tpu-alice01"]}}, "dis-2026-tpu-alice01"))
        self.assertFalse(verify_projects.budget_scope_matches({"budgetFilter": {"projects": ["projects/dis-2026-tpu-bob02"]}}, "dis-2026-tpu-alice01"))
        self.assertFalse(verify_projects.budget_scope_matches({"budgetFilter": {"projects": ["projects/dis-2026-tpu-alice01", "projects/dis-2026-tpu-bob02"]}}, "dis-2026-tpu-alice01"))

    def test_config_validation_rejects_placeholders_and_bad_topic(self):
        cfg = example_config()
        with self.assertRaisesRegex(SystemExit, "billing_account"):
            common.validate_config(cfg)

        cfg["billing_account"] = "ABCDEF-123456-789ABC"
        cfg["budget_topic"] = "bad-topic"
        with self.assertRaisesRegex(SystemExit, "budget_topic"):
            common.validate_config(cfg)

    def test_participant_validation_rejects_bad_project_ids(self):
        cfg = example_config()
        cfg["billing_account"] = "ABCDEF-123456-789ABC"
        cfg["budget_topic"] = "projects/workshop-control/topics/workshop-budget-alerts"
        rows = [{"participant_id": "alice;rm", "google_email": "alice@example.edu"}]
        with self.assertRaises(SystemExit):
            common.validate_participants(rows, cfg)


if __name__ == "__main__":
    unittest.main()
