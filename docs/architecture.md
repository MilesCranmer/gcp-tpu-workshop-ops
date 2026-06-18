# Architecture

## Control model

```text
participant roster
  -> one project per participant
  -> one budget per project
  -> budget notifications to Pub/Sub
  -> Cloud Function kill-switch
  -> disable billing for over-budget project
```

TPU quota caps are applied independently of budgets:

```text
project quota preferences
  -> allow approved TPU type/zone
  -> set other relevant TPU zones/types to zero or a safe value
```

## Components

- **Participant roster**: private TSV with participant IDs and Google accounts.
- **Control project**: owns the Pub/Sub topic and Cloud Function.
- **Billing account**: linked to all participant projects.
- **Participant projects**: one per participant, named from a predictable pattern such as `dis-2026-tpu-{participant_id}`.
- **Budget kill-switch**: receives Cloud Billing budget events and unlinks billing from the relevant project when cost is at or above the budget.
- **Quota caps**: Cloud Quotas preferences limiting TPU usage per project and zone.

## Why one project per participant

Per-participant projects make the safety model simple:

- one participant cannot affect another participant's resources;
- budgets can be scoped exactly to one project;
- the kill-switch can disable only the over-budget project;
- cleanup and audit are straightforward;
- IAM grants are narrow and reversible.

## Budget display name convention

The kill-switch needs a safe way to map a budget event back to a project. This guide uses budget display names like:

```text
DIS2026_CAP:<project-id> $500
```

The function only acts on budgets with the configured prefix. It parses the project ID immediately after the prefix.

## Safety boundaries

Budgets are not real-time meters. The quota cap is the main protection against large sudden overspend. The budget kill-switch is still useful, but it reacts only after Cloud Billing publishes a budget notification.
