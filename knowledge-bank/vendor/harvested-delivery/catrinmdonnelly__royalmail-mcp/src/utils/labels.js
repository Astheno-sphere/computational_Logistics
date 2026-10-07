import { PDFDocument } from 'pdf-lib';
import { mkdir, writeFile } from 'fs/promises';
import { existsSync } from 'fs';
import { homedir } from 'os';
import { resolve, join } from 'path';

function labelsDir() {
  if (process.env.PARCEL_TOOLKIT_LABELS_DIR) {
    return resolve(process.env.PARCEL_TOOLKIT_LABELS_DIR);
  }
  const downloads = join(homedir(), 'Downloads');
  const base = existsSync(downloads) ? downloads : homedir();
  return join(base, 'parcel-toolkit');
}

function timestamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}

export async function saveLabelToDisk({ labelBase64, filenameStem, extension = 'pdf' }) {
  const dir = labelsDir();
  await mkdir(dir, { recursive: true });
  const filename = `${filenameStem}.${extension}`;
  const fullPath = join(dir, filename);
  const buffer = Buffer.from(labelBase64, 'base64');
  await writeFile(fullPath, buffer);
  return fullPath;
}

export async function mergeLabelsToPdf({ labelsBase64, filenameStem }) {
  const dir = labelsDir();
  await mkdir(dir, { recursive: true });

  const merged = await PDFDocument.create();
  for (const b64 of labelsBase64) {
    const src = await PDFDocument.load(Buffer.from(b64, 'base64'), { ignoreEncryption: true });
    const pages = await merged.copyPages(src, src.getPageIndices());
    for (const p of pages) merged.addPage(p);
  }

  const bytes = await merged.save();
  const fullPath = join(dir, `${filenameStem}.pdf`);
  await writeFile(fullPath, bytes);
  return fullPath;
}

export { timestamp };
