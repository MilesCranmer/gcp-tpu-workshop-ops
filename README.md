# Build-a-GCP Workshop 🧸 — TPU edition!

You want to hand a room full of people their own TPUs for a day. You do not want one of them to accidentally spin up far more accelerator than intended and leave you explaining a five-figure bill. This repo is the build table: one sandboxed Google Cloud project per participant, one billing account behind the whole thing.

The build goes like this:

1. collect each participant's Google account;
2. create one Google Cloud project per participant;
3. link those projects to one billing account with credits;
4. create one per-project budget;
5. send budget notifications to Pub/Sub;
6. deploy a budget kill-switch that disables billing for over-budget projects;
7. apply strict TPU quota caps so delayed billing data cannot create a large overspend;
8. verify every project before granting participant IAM;
9. add participants only as the final step — stitch them in last, once everything else holds.

This is for the people running the workshop, not the people attending it. It assumes you're comfortable with `gcloud` and a billing account you actually own.

## Why this design

Here's the thing a budget alert won't tell you: it is not a prepaid hard cap, and it arrives late. Budget notifications lag behind actual usage, sometimes by hours. For most products that lag is harmless. For TPUs it isn't — someone can provision a lot of accelerator-hours in the window before the budget data catches up, and by the time the alert fires the money is already spent.

So this doesn't lean on budgets alone. The layers are:

- **one project per participant**: isolates IAM, budgets, and cleanup;
- **budget alerts**: detect gross usage against a participant allowance;
- **billing kill-switch**: disables billing for a project once a budget alert says it is over budget;
- **TPU quota caps**: limit how much TPU capacity can exist while budget data is delayed;
- **final IAM gate**: participants only get access after all controls are verified.

If you are adapting this for a new workshop, read [`docs/architecture.md`](docs/architecture.md) first, then follow [`docs/setup-walkthrough.md`](docs/setup-walkthrough.md). Keep [`docs/verification-checklist.md`](docs/verification-checklist.md) open while you work.

## Quick start

Copy the examples. The default config intentionally contains a placeholder billing account; edit it before running organizer scripts against Google Cloud:

```bash
cp examples/workshop.config.example.json workshop.config.json
cp examples/participants.example.tsv participants.tsv
```

Edit both files for your workshop. Keep real participant data private and do not commit it. The scripts reject placeholder billing accounts and invalid project/topic formats before issuing cloud commands.

Dry-run provisioning:

```bash
python3 scripts/provision_projects.py \
  --config workshop.config.json \
  --participants participants.tsv
```

Apply only after reading the generated actions:

```bash
python3 scripts/provision_projects.py \
  --config workshop.config.json \
  --participants participants.tsv \
  --apply
```

Verify before adding participants:

```bash
python3 scripts/verify_projects.py \
  --config workshop.config.json \
  --participants participants.tsv
```

Final participant IAM rollout:

```bash
python3 scripts/final_add_participants.py \
  --config workshop.config.json \
  --participants participants.tsv \
  --apply \
  --approval-token ADD_PARTICIPANTS_FINAL
```

## Local checks

Run the repository checks with:

```bash
make check
```

This uses `uv` for Python tests and `npm ci && npm test` for the Cloud Function.

## Important caveat

Don't sell this to yourself or anyone else as a guaranteed prepaid hard cap — it isn't one. It's a layered safety system where the quota caps do the real blast-radius work and the rest catches up after the fact:

- quota caps bound how much TPU can exist at once, so the worst case stays small;
- budgets detect reported spend;
- the kill-switch disables billing once a budget notification arrives.

Google documents budget Pub/Sub delivery as at-least-once, potentially duplicated or out of order, and budget data is not a real-time meter. Disabling billing can also leave already-incurred but unreported charges on the original billing account.

For high-stakes deployments, test the full path in your own billing account before adding participants.

## Source references

- Cloud Billing budget notifications: https://docs.cloud.google.com/billing/docs/how-to/budgets-programmatic-notifications
- Billing account changes and disable-billing permissions: https://docs.cloud.google.com/billing/docs/how-to/modify-project
- `gcloud billing budgets create`: https://docs.cloud.google.com/sdk/gcloud/reference/billing/budgets/create
- Cloud TPU quotas: https://docs.cloud.google.com/tpu/docs/quota
