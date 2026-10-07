/**
 * Call agentsociety2 literature library helpers (ingest / sync / BibTeX / PDF).
 */

import { execFile } from 'child_process';
import { promisify } from 'util';
import * as vscode from 'vscode';
import { EnvManager } from '../envManager';
import { isExtensionZh } from '../i18n';
import {
  resolveAgentsocietyPython,
  type ResolveAgentsocietyPythonOptions,
} from './agentsocietyPythonResolver';

const execFileAsync = promisify(execFile);

export type LiteratureJsonPayload = {
  ok: boolean;
  error?: string;
  [key: string]: unknown;
};

export type LiteratureIngestPayload = LiteratureJsonPayload & {
  added?: boolean;
  duplicate?: boolean;
  title?: string;
  file_path?: string;
  doi?: string | null;
  message?: string;
};

export type LiteratureSyncPayload = LiteratureJsonPayload & {
  metadata_updated?: number;
  metadata_skipped?: number;
  metadata_failed?: number;
  pdf_downloaded?: number;
  pdf_skipped?: number;
  pdf_failed?: number;
  pdf_no_candidate?: number;
};

export type LiteratureBibExportPayload = LiteratureJsonPayload & {
  bibtex?: string;
  count?: number;
  path?: string | null;
};

function resolvePython(workspacePath: string): string {
  const env = new EnvManager().readEnv();
  const options: ResolveAgentsocietyPythonOptions = {
    configuredPath: env.pythonPath,
    workspacePath,
    extensionPath: vscode.extensions.getExtension('tsinghua-fib-lab.ai-social-scientist')?.extensionPath,
  };
  const resolved = resolveAgentsocietyPython(options);
  if (!resolved) {
    throw new Error(
      isExtensionZh()
        ? '未找到已安装 agentsociety2 的 Python。请在配置页设置 PYTHON_PATH。'
        : 'No Python with agentsociety2 found. Set PYTHON_PATH in the config page.'
    );
  }
  return resolved;
}

function asText(value: unknown): string {
  if (value === null || value === undefined) {
    return '';
  }
  if (typeof value === 'string') {
    return value;
  }
  if (Buffer.isBuffer(value)) {
    return value.toString('utf8');
  }
  return String(value);
}

function parseJsonPayload(stdout: string, stderr: string): LiteratureJsonPayload {
  const text = (stdout || stderr || '').trim();
  const line = text.split('\n').filter(Boolean).pop() || '';
  return JSON.parse(line) as LiteratureJsonPayload;
}

async function runPythonModule(
  workspacePath: string,
  moduleName: string,
  args: string[],
  timeoutMs: number
): Promise<LiteratureJsonPayload> {
  const python = resolvePython(workspacePath);
  try {
    const { stdout, stderr } = await execFileAsync(
      python,
      ['-m', moduleName, '--workspace', workspacePath, '--json', ...args],
      {
        timeout: timeoutMs,
        maxBuffer: 4 * 1024 * 1024,
        env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
      }
    );
    return parseJsonPayload(asText(stdout), asText(stderr));
  } catch (error: any) {
    const stdout = asText(error?.stdout);
    const stderr = asText(error?.stderr);
    if (stdout.trim() || stderr.trim()) {
      try {
        return parseJsonPayload(stdout, stderr);
      } catch {
        // fall through
      }
    }
    throw new Error(stderr.trim() || stdout.trim() || error.message || String(error));
  }
}

async function runIngest(
  workspacePath: string,
  args: string[],
  timeoutMs: number
): Promise<LiteratureIngestPayload> {
  return runPythonModule(
    workspacePath,
    'agentsociety2.skills.literature.ingest',
    args,
    timeoutMs
  ) as Promise<LiteratureIngestPayload>;
}

async function runLibraryOps(
  workspacePath: string,
  args: string[],
  timeoutMs: number
): Promise<LiteratureJsonPayload> {
  return runPythonModule(
    workspacePath,
    'agentsociety2.skills.literature.library_ops',
    args,
    timeoutMs
  );
}

export async function ingestByIdentifier(
  workspacePath: string,
  identifier: string
): Promise<LiteratureIngestPayload> {
  return runIngest(workspacePath, ['add-id', identifier], 60_000);
}

export async function ingestLocalFile(
  workspacePath: string,
  filePath: string,
  title?: string
): Promise<LiteratureIngestPayload> {
  const args = ['add-file', filePath];
  if (title) {
    args.push('--title', title);
  }
  return runIngest(workspacePath, args, 30_000);
}

export async function syncLiteratureLibrary(
  workspacePath: string,
  entryIds?: number[]
): Promise<LiteratureSyncPayload> {
  const args = ['sync'];
  if (entryIds && entryIds.length > 0) {
    args.push('--entries', entryIds.join(','));
  }
  return runLibraryOps(workspacePath, args, 300_000) as Promise<LiteratureSyncPayload>;
}

export async function downloadLiteraturePdfs(
  workspacePath: string,
  entryIds: number[],
  force = false
): Promise<LiteratureSyncPayload> {
  const args = ['download-pdf', '--entries', entryIds.join(',')];
  if (force) {
    args.push('--force');
  }
  return runLibraryOps(workspacePath, args, 300_000) as Promise<LiteratureSyncPayload>;
}

export async function exportLiteratureBibtex(
  workspacePath: string,
  entryIds?: number[],
  stdoutOnly = false
): Promise<LiteratureBibExportPayload> {
  const args = ['export-bib'];
  if (entryIds && entryIds.length > 0) {
    args.push('--entries', entryIds.join(','));
  }
  if (stdoutOnly) {
    args.push('--stdout-only');
  }
  return runLibraryOps(workspacePath, args, 30_000) as Promise<LiteratureBibExportPayload>;
}

export async function importLiteratureBibtex(
  workspacePath: string,
  bibPath: string
): Promise<LiteratureJsonPayload & { added?: number; duplicates?: number; parsed?: number }> {
  return runLibraryOps(workspacePath, ['import-bib', bibPath], 60_000) as Promise<
    LiteratureJsonPayload & { added?: number; duplicates?: number; parsed?: number }
  >;
}
