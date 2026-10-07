#!/usr/bin/env node
/**
 * Live E2E test for book_batch_and_label — books 2 test orders on Royal Mail Click & Drop,
 * gets their labels, merges them into one PDF, then cancels both.
 *
 * Usage:  node scripts/live-batch.mjs
 *
 * Safety:
 *   - Requires RM_ALLOW_LIVE=yes in .env or env to proceed.
 *   - Uses try/finally so cancels ALWAYS run, even on failure.
 *   - Click & Drop orders stay in draft until manifested, so cancel prevents real dispatch.
 */

import { readFileSync, existsSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { tmpdir } from 'os';
import { join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const envPath = resolve(__dirname, '../.env');

if (existsSync(envPath)) {
  for (const line of readFileSync(envPath, 'utf-8').split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const [key, ...rest] = trimmed.split('=');
    if (key && rest.length) {
      process.env[key.trim()] = rest.join('=').trim().replace(/^["']|["']$/g, '');
    }
  }
}

if (!process.env.RM_API_KEY || process.env.RM_API_KEY.includes('your-rm')) {
  console.error('✗ Set RM_API_KEY in .env first.');
  process.exit(1);
}
if (process.env.RM_ALLOW_LIVE !== 'yes') {
  console.error('✗ Safety check: RM_ALLOW_LIVE=yes is not set.');
  console.error('  Set RM_ALLOW_LIVE=yes in .env to confirm you understand this books (and then cancels) 2 real orders.');
  process.exit(1);
}

console.log('⚠  LIVE MODE: this will book TWO real Click & Drop orders and cancel them immediately.');
console.log('   Orders stay in draft until you manifest them — cancellation prevents real dispatch.\n');

process.env.PARCEL_TOOLKIT_LABELS_DIR = join(tmpdir(), `rm-batch-test-${Date.now()}`);

const rm = await import('../src/carriers/royalmail.js');
const { mergeLabelsToPdf, saveLabelToDisk, timestamp } = await import('../src/utils/labels.js');
const { PDFDocument } = await import('pdf-lib');

const shipments = [
  {
    recipient: {
      fullName:     'Alice Smith',
      companyName:  'Batch Test Recipient 1',
      addressLine1: '1 High Street',
      city:         'Manchester',
      postcode:     'M1 1AA',
      phone:        '07000000001',
      email:        'alice@example.com',
    },
    weightGrams: 500,
    reference: `MCP-BATCH-RM-${Date.now()}-1`,
    goodsDescription: 'Batch test #1',
  },
  {
    recipient: {
      fullName:     'Bob Jones',
      companyName:  'Batch Test Recipient 2',
      addressLine1: '2 Church Road',
      city:         'Bristol',
      postcode:     'BS1 1AA',
      phone:        '07000000002',
      email:        'bob@example.com',
    },
    weightGrams: 300,
    reference: `MCP-BATCH-RM-${Date.now()}-2`,
    goodsDescription: 'Batch test #2',
  },
];

const step = (n, msg) => console.log(`\n[${n}] ${msg}`);
const ok   = (msg) => console.log(`    ✓ ${msg}`);
const err  = (msg) => console.error(`    ✗ ${msg}`);
const warn = (msg) => console.warn(`    ⚠ ${msg}`);

const orderIdentifiers = [];
const errors = [];

try {
  // ── 1. Book each order ────────────────────────────────────────────────────
  step(1, `Booking ${shipments.length} test orders on LIVE endpoint...`);
  for (let i = 0; i < shipments.length; i++) {
    const s = shipments[i];
    try {
      const result = await rm.createOrder({
        service: 'tracked-24',
        packageFormat: 'small-parcel',
        weightGrams: s.weightGrams,
        recipient: s.recipient,
        reference: s.reference,
        goodsDescription: s.goodsDescription,
      });
      if (!result.orderIdentifier) throw new Error(`No orderIdentifier. Raw: ${JSON.stringify(result.raw)}`);
      orderIdentifiers.push(result.orderIdentifier);
      ok(`Order ${i + 1}: ${result.orderIdentifier} (${s.recipient.fullName}, ${s.recipient.postcode})`);
    } catch (e) {
      err(`Order ${i + 1} booking failed: ${e.message}`);
      errors.push(`book#${i + 1}: ${e.message}`);
    }
  }

  if (orderIdentifiers.length === 0) throw new Error('No orders booked — aborting.');

  // ── 2. Fetch labels ───────────────────────────────────────────────────────
  step(2, `Fetching labels for ${orderIdentifiers.length} orders...`);
  const labelsBase64 = [];
  for (const oid of orderIdentifiers) {
    try {
      const label = await rm.getLabel(oid);
      if (!label.labelBase64) throw new Error('No label content returned');
      labelsBase64.push(label.labelBase64);
      ok(`Label fetched for ${oid} (${(Buffer.from(label.labelBase64, 'base64').length / 1024).toFixed(1)} KB)`);
    } catch (e) {
      err(`Label fetch failed for ${oid}: ${e.message}`);
      errors.push(`label#${oid}: ${e.message}`);
    }
  }

  if (labelsBase64.length === 0) throw new Error('No labels fetched — aborting merge test.');

  // ── 3. Save single ────────────────────────────────────────────────────────
  step(3, 'Saving a single label to disk...');
  try {
    const singlePath = await saveLabelToDisk({
      labelBase64: labelsBase64[0],
      filenameStem: `rm-${orderIdentifiers[0]}-${timestamp()}`,
      extension: 'pdf',
    });
    const singleDoc = await PDFDocument.load(readFileSync(singlePath));
    ok(`Saved: ${singlePath} (${singleDoc.getPageCount()} page(s), ${readFileSync(singlePath).length} bytes)`);
  } catch (e) {
    err(`Single save failed: ${e.message}`);
    errors.push(`single-save: ${e.message}`);
  }

  // ── 4. Merge ──────────────────────────────────────────────────────────────
  step(4, `Merging ${labelsBase64.length} labels into one PDF...`);
  try {
    const mergedPath = await mergeLabelsToPdf({
      labelsBase64,
      filenameStem: `rm-batch-${timestamp()}-${labelsBase64.length}labels`,
    });
    const mergedDoc = await PDFDocument.load(readFileSync(mergedPath));
    const pageCount = mergedDoc.getPageCount();
    ok(`Merged PDF: ${mergedPath}`);
    ok(`Pages: ${pageCount} (expected >= ${labelsBase64.length})`);
    ok(`Size: ${readFileSync(mergedPath).length} bytes`);
    if (pageCount < labelsBase64.length) {
      errors.push(`merge: expected at least ${labelsBase64.length} pages, got ${pageCount}`);
    }
  } catch (e) {
    err(`Merge failed: ${e.message}`);
    errors.push(`merge: ${e.message}`);
  }
} finally {
  // ── 5. Cancel all orders ──────────────────────────────────────────────────
  if (orderIdentifiers.length) {
    step(5, `Cancelling ${orderIdentifiers.length} orders...`);
    for (const oid of orderIdentifiers) {
      try {
        const cancel = await rm.cancelOrder(oid);
        if (cancel.success) {
          ok(`Cancelled ${oid}: ${cancel.message}`);
        } else {
          err(`Cancel not confirmed for ${oid}: ${cancel.message}`);
          err(`⚠  MANUALLY CANCEL VIA CLICK & DROP: ${oid}`);
          errors.push(`cancel#${oid}: ${cancel.message}`);
        }
      } catch (e) {
        err(`Cancel failed for ${oid}: ${e.message}`);
        err(`⚠  MANUALLY CANCEL VIA CLICK & DROP: ${oid}`);
        errors.push(`cancel#${oid}: ${e.message}`);
      }
    }
  }
}

if (errors.length === 0) {
  console.log('\n✓ Batch flow passed. book_batch_and_label is working.\n');
  process.exit(0);
} else {
  console.error(`\n✗ ${errors.length} step(s) failed:`);
  for (const e of errors) console.error(`   - ${e}`);
  process.exit(1);
}
