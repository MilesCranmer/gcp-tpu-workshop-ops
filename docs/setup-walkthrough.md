# Setup walkthrough

## 1. Collect participant accounts

Use a form to collect:

- institutional email or stable participant ID;
- name, if needed for your own records;
- Google account email to grant access to Cloud projects.

Keep the real roster private. Use `examples/participants.example.tsv` as the schema.

## 2. Prepare a workshop config

Create `workshop.config.json` from `examples/workshop.config.example.json` and set. The scripts reject the placeholder billing account:

- billing account ID;
- control project ID;
- Pub/Sub topic;
- project name pattern;
- budget amount;
- budget prefix;
- approved TPU type and zone;
- Cloud Function name and region;
- participant IAM roles.

Do not commit the real config if it contains private identifiers.

## 3. Deploy the budget kill-switch

Create the Pub/Sub topic and deploy the function:

```bash
bash scripts/deploy_budget_kill_switch.sh --config workshop.config.json --apply
```

Grant the function service account. The provisioning script handles per-project roles; billing-account IAM must be granted by an operator with billing-admin authority:

- billing permission on the billing account;
- project billing-manager permission on each participant project it may shut off.

The provisioning script can grant the per-project roles after each participant project exists.

## 4. Pre-provision projects

Dry-run first:

```bash
python3 scripts/provision_projects.py --config workshop.config.json --participants participants.tsv
```

Then apply:

```bash
python3 scripts/provision_projects.py --config workshop.config.json --participants participants.tsv --apply
```

This creates or configures each participant project, links billing, enables required APIs, creates the budget, grants kill-switch roles, and applies TPU quota caps.

## 5. Verify before participant access

Run:

```bash
python3 scripts/verify_projects.py --config workshop.config.json --participants participants.tsv
```

Do not add participants until verification passes.

## 6. Add participants last

Only after verification:

```bash
python3 scripts/final_add_participants.py \
  --config workshop.config.json \
  --participants participants.tsv \
  --apply \
  --approval-token ADD_PARTICIPANTS_FINAL
```

## 7. Workshop operation

Teach participants one approved TPU creation path and one cleanup path. Keep the allowed zone/type narrow. Make cleanup part of the live teaching material.

## Tool requirements

- Google Cloud CLI with `billing`, `budgets`, `functions`, `pubsub`, `services`, `compute tpus`, and beta `quotas` commands available.
- Python runnable through `uv`.
- Node.js 20-compatible runtime for local Cloud Function tests.
- An authenticated Google account with project creation, billing, IAM, quota, and Cloud Functions permissions.
