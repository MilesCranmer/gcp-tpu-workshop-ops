#!/usr/bin/env bash
set -euo pipefail

APPLY=0
CONFIG=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --config) CONFIG="$2"; shift 2 ;;
    --apply) APPLY=1; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$CONFIG" ]]; then
  echo "Usage: $0 --config workshop.config.json [--apply]" >&2
  exit 2
fi

CONFIG_VALUES=$(python3 - "$CONFIG" <<'PY'
import json, sys
cfg=json.load(open(sys.argv[1]))
required=['control_project','budget_topic','budget_prefix','billing_account','kill_switch_service_account']
missing=[k for k in required if k not in cfg]
if missing:
    raise SystemExit(f'missing config keys: {missing}')
print(cfg['control_project'])
print(cfg['budget_topic'])
print(cfg.get('budget_prefix','DIS2026_CAP:'))
print(cfg['billing_account'])
print(cfg['kill_switch_service_account'])
print(cfg.get('function_name','workshop-budget-kill-switch'))
print(cfg.get('function_region','europe-west2'))
PY
)
mapfile -t VALUES <<< "$CONFIG_VALUES"
CONTROL_PROJECT=${VALUES[0]}
TOPIC_FULL=${VALUES[1]}
PREFIX=${VALUES[2]}
BILLING_ACCOUNT=${VALUES[3]}
SERVICE_ACCOUNT=${VALUES[4]}
FUNCTION_NAME=${VALUES[5]}
REGION=${REGION:-${VALUES[6]}}

if [[ ! "$TOPIC_FULL" =~ ^projects/[^/]+/topics/[^/]+$ ]]; then
  echo "budget_topic must be a full resource: projects/{project_id}/topics/{topic_id}" >&2
  exit 2
fi
TOPIC_PROJECT=$(cut -d/ -f2 <<< "$TOPIC_FULL")
TOPIC=$(cut -d/ -f4 <<< "$TOPIC_FULL")
if [[ "$TOPIC_PROJECT" != "$CONTROL_PROJECT" ]]; then
  echo "budget_topic project must match control_project for this deploy helper" >&2
  exit 2
fi

run_cmd() {
  if [[ "$APPLY" == "1" ]]; then
    printf 'APPLY:'
    printf ' %q' "$@"
    printf '\n'
    "$@"
  else
    printf 'DRY_RUN:'
    printf ' %q' "$@"
    printf '\n'
  fi
}

run_cmd gcloud pubsub topics create "$TOPIC" --project "$CONTROL_PROJECT"
run_cmd gcloud functions deploy "$FUNCTION_NAME" \
  --gen2 \
  --runtime=nodejs20 \
  --region="$REGION" \
  --source=cloud-function \
  --entry-point=stopBilling \
  --trigger-topic="$TOPIC" \
  --project="$CONTROL_PROJECT" \
  --service-account="$SERVICE_ACCOUNT" \
  --set-env-vars="BUDGET_DISPLAY_NAME_PREFIX=$PREFIX,EXPECTED_BILLING_ACCOUNT_ID=$BILLING_ACCOUNT"
