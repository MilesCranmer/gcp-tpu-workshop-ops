.PHONY: check python-test function-test dry-run-example leak-scan

check: python-test function-test dry-run-example leak-scan

python-test:
	uv run python -m unittest discover -s tests -v

function-test:
	cd cloud-function && npm ci && npm test

dry-run-example:
	uv run python scripts/dry_run_example.py
	bash scripts/deploy_budget_kill_switch.sh --config examples/workshop.config.dryrun.json

leak-scan:
	! rg -n --hidden -g '!cloud-function/node_modules' -g '!out' -g '!.git' '0169BA[-]|0041B5[-]|miles[.]cranmer|cam[.]ac[.]uk|/Users/mcranme[r]|projects/dis-2026-tpu/topic[s]|budget-kill-switch@dis-2026-tp[u]|ya29[.]|AIz[a]|BEGIN .*PRIVATE KE[Y]' .
