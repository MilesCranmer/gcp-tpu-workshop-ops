# Day-of operations

## Before participants start

- Run `make check` locally.
- Run `verify_projects.py` against the real config and roster.
- Confirm Cloud Function logs are visible.
- Confirm the Pub/Sub topic exists and is connected to each budget.
- Confirm no participant project has live TPU VMs from testing.
- Keep the billing reports and TPU VM list open during the first live exercise.

## During the workshop

Monitor:

- Cloud Function errors;
- budget notifications;
- live TPU VMs in approved zones;
- billing report trends;
- participant support messages about disabled billing or quota errors.

If the kill-switch fires, treat the project as stopped until an operator reviews it. Do not relink billing automatically.

## Break glass

If the automated path fails and spend is unsafe, manually disable billing on affected participant projects from Cloud Billing account management, or run the equivalent `gcloud beta billing projects unlink` command if your permissions allow it. Then delete or stop active TPU VMs and record what happened.

## Recovery after a controlled shutoff

- Verify no unexpected paid resources remain.
- Decide whether the participant should continue.
- Relink billing only after reviewing budget state and quota caps.
- Some resources may need manual restart after billing is re-enabled.
