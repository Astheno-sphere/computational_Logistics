// Unit test for mergeLabelsToPdf — no API calls, no credentials required.
// Creates three synthetic single-page PDFs, merges them, confirms the output has 3 pages.

import { PDFDocument } from 'pdf-lib';
import { readFileSync, existsSync, rmSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import { mergeLabelsToPdf, saveLabelToDisk } from '../src/utils/labels.js';

const labelsDir = join(tmpdir(), `parcel-toolkit-test-${Date.now()}`);
process.env.PARCEL_TOOLKIT_LABELS_DIR = labelsDir;

const fail = (msg) => { console.error(`FAIL: ${msg}`); rmSync(labelsDir, { recursive: true, force: true }); process.exit(1); };

async function makeOnePagePdf(text) {
  const doc = await PDFDocument.create();
  const page = doc.addPage([400, 300]);
  page.drawText(text, { x: 50, y: 150, size: 24 });
  const bytes = await doc.save();
  return Buffer.from(bytes).toString('base64');
}

const labelA = await makeOnePagePdf('LABEL A');
const labelB = await makeOnePagePdf('LABEL B');
const labelC = await makeOnePagePdf('LABEL C');

const savedPath = await saveLabelToDisk({
  labelBase64: labelA,
  filenameStem: 'single-label',
});
if (!existsSync(savedPath)) fail(`saveLabelToDisk did not create file at ${savedPath}`);
const savedBytes = readFileSync(savedPath);
if (savedBytes.length < 100) fail(`saved PDF suspiciously small: ${savedBytes.length} bytes`);

const mergedPath = await mergeLabelsToPdf({
  labelsBase64: [labelA, labelB, labelC],
  filenameStem: 'merged-batch',
});
if (!existsSync(mergedPath)) fail(`merged PDF not found at ${mergedPath}`);

const mergedDoc = await PDFDocument.load(readFileSync(mergedPath));
const pageCount = mergedDoc.getPageCount();
if (pageCount !== 3) fail(`expected 3 pages in merged PDF, got ${pageCount}`);

const mergedBytes = readFileSync(mergedPath).length;

rmSync(labelsDir, { recursive: true, force: true });

console.log(`OK: saveLabelToDisk wrote ${savedBytes.length} byte PDF`);
console.log(`OK: mergeLabelsToPdf produced 3-page merged PDF (${mergedBytes} bytes)`);
