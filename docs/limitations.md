# Limitations

- Google Cloud budgets are notification-based and can lag.
- The budget kill-switch reacts after a budget event arrives; it is not a prepaid hard meter.
- Quota systems and quota IDs can vary by accelerator family and Google Cloud rollout state.
- Billing credits may apply to invoices even when budgets are configured to track gross spend. Decide whether participant allowances should count gross usage or net-after-credit cost.
- Organization policies may require different IAM roles from the examples here.
- Always test with a small project before adding real participants.

## Budget delivery and billing caveats

Cloud Billing budget notifications are not real-time. Pub/Sub delivery is at-least-once, so messages can be duplicated or arrive out of order. If the Pub/Sub topic is misconfigured, delivery can fail without a useful automatic fallback. After billing is disabled, already-incurred but unreported charges can still be billed to the previously linked billing account.

## Support boundary

The included quota automation is v6e-specific. Treat other TPU families and zones as unsupported until you add matching quota IDs, tests, docs, and live verification.
