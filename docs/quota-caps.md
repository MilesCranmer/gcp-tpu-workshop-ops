# TPU quota caps

This repository automates **v6e quota caps only**. Other TPU families use different quota names and must be added deliberately.

Quota caps prevent participants from creating more TPU capacity than the workshop intends, even if budget notifications lag. The included script hard-codes Google Cloud TPU v6e quota IDs; do not assume it covers v5e, v5p, v4, reservations, or future TPU families.

## Recommended pattern

For each participant project:

- allow only the approved TPU family and zone;
- cap approved TPU quota to the intended maximum;
- set preemptible TPU quota to zero unless explicitly teaching preemptibles;
- set other relevant TPU zones to zero or do not grant access to them;
- verify quota state before granting participant IAM.

Example workshop default:

```text
allowed zone: us-east5-b
allowed TPU: v6e-1
maximum v6e quota units: 2
preemptible v6e quota units: 0
```

## Why caps matter

Budget notifications are based on billing data, not instantaneous resource state. A quota cap bounds the worst-case resource burst while billing catches up.

## Verification

Check both configured quota preferences and live TPU VMs. Live TPU counts alone are not enough: a project can have no running TPUs but still have excessive quota available.

## Source reference

- Cloud TPU quota names and per-zone quota behavior: https://docs.cloud.google.com/tpu/docs/quota
