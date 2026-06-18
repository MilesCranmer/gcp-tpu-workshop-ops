# Adding participants

Adding participants should be the final rollout step.

## Roster schema

Use a private TSV:

```text
participant_id	institutional_email	name	google_email
alice01	alice@example.edu	Alice Example	alice.personal@gmail.com
```

Do not commit real rosters.

## Project naming

Use a deterministic pattern:

```text
dis-2026-tpu-{participant_id}
```

This makes budgets, verification, and support easier.

## Suggested participant roles

For a TPU VM workshop, participants usually need enough permission to create and manage TPU VMs and use service accounts. A minimal role set depends on your organization, but this guide's example uses:

```text
roles/tpu.admin
roles/iam.serviceAccountUser
roles/compute.viewer
```

Review these roles against your own policy before rollout.

## Final gate

Before granting IAM, verify:

- project exists;
- billing is linked to the intended billing account;
- budget exists and is scoped only to that project;
- budget notifications go to the kill-switch topic;
- kill-switch service account has project access;
- TPU quota caps are applied;
- no live TPU resources are left from testing.
