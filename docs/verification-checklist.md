# Verification checklist

Run this before adding participants.

## Control plane

- Pub/Sub topic exists.
- Budget kill-switch function is deployed.
- Function service account has required billing permissions.
- Synthetic below-budget event does not disable billing.
- Synthetic over-budget event disables billing for a test project.
- Test project billing can be intentionally relinked after the test.

## Per participant project

- Project exists.
- Billing is enabled and linked to the intended billing account.
- Required APIs are enabled.
- Participant IAM roles are absent before final rollout.
- Budget exists with the correct amount and exact prefix/project delimiter.
- Budget is scoped to exactly the expected `projects/{project_id}` resource.
- Budget notification topic is correct.
- Budget credit treatment matches the allowance policy.
- Kill-switch service account has the configured per-project role bindings.
- TPU quota caps are verified.
- No unexpected live TPU VMs exist, unless an active test explicitly allows them.
- Participant IAM has not been granted before the final gate.

## Final rollout

- Run `verify_projects.py`.
- Review output.
- Grant participant IAM with `final_add_participants.py` only after verification passes.
- Re-run verification in post-IAM mode if you add that check for your deployment.
