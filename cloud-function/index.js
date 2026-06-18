'use strict';

const {CloudBillingClient} = require('@google-cloud/billing');

const billing = new CloudBillingClient();
const displayNamePrefix = process.env.BUDGET_DISPLAY_NAME_PREFIX || 'DIS2026_CAP:';
const expectedBillingAccountId = process.env.EXPECTED_BILLING_ACCOUNT_ID || '';
const dryRun = String(process.env.DRY_RUN || '').toLowerCase() === 'true';

function decodeEvent(event) {
  const encoded =
    event.data && event.data.message && event.data.message.data ||
    event.data && event.data.data ||
    event.message && event.message.data ||
    typeof event.data === 'string' && event.data;
  if (!encoded) {
    throw new Error(`Missing Pub/Sub message data in event shape: ${JSON.stringify(event)}`);
  }
  const payload = JSON.parse(Buffer.from(encoded, 'base64').toString('utf8'));
  const attributes =
    event.data && event.data.message && event.data.message.attributes ||
    event.data && event.data.attributes ||
    event.message && event.message.attributes ||
    event.attributes ||
    {};
  return {payload, attributes};
}

function projectIdFromDisplayName(displayName) {
  if (!displayName || !displayName.startsWith(displayNamePrefix)) {
    return null;
  }
  const rest = displayName.slice(displayNamePrefix.length);
  const projectId = rest.split(/\s+/)[0].trim();
  if (!/^[a-z][a-z0-9-]{4,28}[a-z0-9]$/.test(projectId)) {
    throw new Error(`Invalid project id parsed from budget display name: ${projectId}`);
  }
  return projectId;
}

function assertExpectedBillingAccount(attributes) {
  if (!expectedBillingAccountId) {
    return;
  }
  const actual = attributes.billingAccountId;
  if (actual !== expectedBillingAccountId) {
    throw new Error(`Unexpected billing account in budget event: ${actual || '<missing>'}`);
  }
}

async function disableBilling(projectId) {
  if (dryRun) {
    console.log(`DRY_RUN: would disable billing for ${projectId}`);
    return;
  }
  const name = `projects/${projectId}`;
  const [current] = await billing.getProjectBillingInfo({name});
  if (!current.billingEnabled) {
    console.log(`Billing already disabled for ${projectId}`);
    return;
  }
  const [updated] = await billing.updateProjectBillingInfo({
    name,
    resource: {billingAccountName: ''},
  });
  console.log(`Disabled billing for ${projectId}: ${JSON.stringify({name: updated.name, projectId: updated.projectId, billingEnabled: updated.billingEnabled})}`);
}

async function stopBilling(event) {
  const {payload, attributes} = decodeEvent(event);
  console.log(`Budget event: ${JSON.stringify({budgetDisplayName: payload.budgetDisplayName, costAmount: payload.costAmount, budgetAmount: payload.budgetAmount, billingAccountId: attributes.billingAccountId, budgetId: attributes.budgetId})}`);

  assertExpectedBillingAccount(attributes);

  const projectId = projectIdFromDisplayName(payload.budgetDisplayName);
  if (!projectId) {
    console.log(`Ignoring budget without prefix ${displayNamePrefix}: ${payload.budgetDisplayName}`);
    return;
  }

  const cost = Number(payload.costAmount);
  const budget = Number(payload.budgetAmount);
  if (!Number.isFinite(cost) || !Number.isFinite(budget)) {
    throw new Error(`Invalid budget payload amounts: ${JSON.stringify(payload)}`);
  }

  if (cost < budget) {
    console.log(`No shutoff for ${projectId}: cost ${cost} < budget ${budget}`);
    return;
  }

  await disableBilling(projectId);
}

exports.stopBilling = stopBilling;
exports._private = {decodeEvent, projectIdFromDisplayName, assertExpectedBillingAccount};
