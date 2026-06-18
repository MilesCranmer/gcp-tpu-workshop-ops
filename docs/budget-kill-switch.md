# Budget kill-switch

The kill-switch is a Cloud Function subscribed to Cloud Billing budget notifications.

## Behavior

1. Receive a Pub/Sub budget event.
2. Ignore budgets whose display name does not start with the configured prefix.
3. Parse the project ID from the display name.
4. Compare `costAmount` and `budgetAmount`.
5. If `costAmount >= budgetAmount`, unlink the project from its billing account.

Unlinking billing is intentionally blunt. It prevents new paid activity in the project and makes the over-budget state obvious.

## Required IAM

Google documents disable-billing as an unlink operation that needs both project-side and billing-account visibility/authority. The practical predefined-role path is:

- On each participant project: `roles/billing.projectManager` and `roles/browser` for the kill-switch service account.
- On the billing account: `roles/billing.viewer` or `roles/billing.admin`, depending on your organization policy and whether the project-side `resourcemanager.projects.deleteBillingAssignment` path is sufficient.

For least privilege, create and test a custom role containing only the permissions your organization accepts. The relevant documented permissions are `billing.resourceAssociations.list`, `resourcemanager.projects.get`, `billing.resourceAssociations.delete`, and/or `resourcemanager.projects.deleteBillingAssignment`. Test this on a disposable project before rollout.

## Testing

Before rollout, test three cases:

- below-budget event: no billing change;
- over-budget event: billing is disabled on a test project;
- unrelated budget prefix: ignored.

Then run a small natural spend test to measure notification lag in your billing account. Record the observed lag and the maximum tolerated overspend buffer.

## Limitation

This is not a prepaid hard cap. Cloud Billing budget notifications can be delayed, duplicated, delivered out of order, or silently missed if the Pub/Sub topic is misconfigured. Disabling billing stops future paid use, but already-incurred unreported charges can still appear later. Use TPU quota caps as the primary protection against sudden overspend.

## Local function test

From a fresh clone:

```bash
cd cloud-function
npm ci
npm test
```

The local test covers wrong-prefix no-op, below-budget no-op, wrong billing-account rejection, invalid project IDs, and over-budget dry-run shutoff.

## Source references

- Programmatic budget notifications: https://docs.cloud.google.com/billing/docs/how-to/budgets-programmatic-notifications
- Disable billing and required permissions: https://docs.cloud.google.com/billing/docs/how-to/modify-project
