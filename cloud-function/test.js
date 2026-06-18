'use strict';

const assert = require('assert');
process.env.DRY_RUN = 'true';
process.env.EXPECTED_BILLING_ACCOUNT_ID = 'ABCDEF-123456-789ABC';
const fn = require('./index.js');

function event(payload, attributes = {}) {
  return {data: {message: {attributes, data: Buffer.from(JSON.stringify(payload)).toString('base64')}}};
}

assert.strictEqual(fn._private.projectIdFromDisplayName('DIS2026_CAP:dis-2026-tpu-alice01 $500'), 'dis-2026-tpu-alice01');
assert.strictEqual(fn._private.projectIdFromDisplayName('OTHER:dis-2026-tpu-alice01 $500'), null);
assert.strictEqual(fn._private.projectIdFromDisplayName('DIS2026_CAP:dis-2026-tpu-alice $500'), 'dis-2026-tpu-alice');
assert.throws(() => fn._private.projectIdFromDisplayName('DIS2026_CAP:Bad_Project $500'), /Invalid project id/);

(async () => {
  await fn.stopBilling(event({budgetDisplayName: 'OTHER:dis-2026-tpu-alice01 $500', costAmount: 999, budgetAmount: 500}, {billingAccountId: 'ABCDEF-123456-789ABC'}));
  await fn.stopBilling(event({budgetDisplayName: 'DIS2026_CAP:dis-2026-tpu-alice01 $500', costAmount: 1, budgetAmount: 500}, {billingAccountId: 'ABCDEF-123456-789ABC'}));
  await assert.rejects(
    () => fn.stopBilling(event({budgetDisplayName: 'DIS2026_CAP:dis-2026-tpu-alice01 $500', costAmount: 500, budgetAmount: 500}, {billingAccountId: 'WRONG-123456-789ABC'})),
    /Unexpected billing account/
  );
  await fn.stopBilling(event({budgetDisplayName: 'DIS2026_CAP:dis-2026-tpu-alice01 $500', costAmount: 500, budgetAmount: 500}, {billingAccountId: 'ABCDEF-123456-789ABC'}));
  console.log('ok');
})().catch(err => { console.error(err); process.exit(1); });
