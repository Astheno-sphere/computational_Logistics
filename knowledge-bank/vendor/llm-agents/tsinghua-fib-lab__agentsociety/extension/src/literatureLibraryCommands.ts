/**
 * Literature library commands for the project tree / command palette.
 *
 * Plugin-only: local index + public DOI/OA helpers. Topic search stays in the
 * Claude literature-search skill (MCP).
 */

import * as fs from 'fs';
import * as path from 'path';
import * as vscode from 'vscode';
import {localize, isExtensionZh} from './i18n';
import { LiteratureIndexViewer } from './literatureIndexViewer';
import {
  exportLiteratureBibtex,
  importLiteratureBibtex,
  syncLiteratureLibrary,
  type LiteratureSyncPayload,
} from './services/literatureIngest';

function workspaceRoot(): string | undefined {
  return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
}

export function literatureIndexPath(root?: string): string | undefined {
  const base = root ?? workspaceRoot();
  return base ? path.join(base, 'papers', 'literature_index.json') : undefined;
}

function ensureIndexFile(root: string): string {
  const papersDir = path.join(root, 'papers');
  const indexPath = path.join(papersDir, 'literature_index.json');
  if (!fs.existsSync(papersDir)) {
    fs.mkdirSync(papersDir, { recursive: true });
  }
  if (!fs.existsSync(indexPath)) {
    const now = new Date().toISOString();
    fs.writeFileSync(
      indexPath,
      JSON.stringify(
        { version: '1.0', created_at: now, updated_at: now, entries: [] },
        null,
        2
      ) + '\n',
      'utf-8'
    );
  }
  return indexPath;
}

function formatSyncSummary(payload: LiteratureSyncPayload, isZh: boolean): string {
  const meta = payload.metadata_updated ?? 0;
  const pdf = payload.pdf_downloaded ?? 0;
  const noCand = payload.pdf_no_candidate ?? 0;
  const failed = (payload.metadata_failed ?? 0) + (payload.pdf_failed ?? 0);
  if (isZh) {
    return (
      `同步完成：补全元数据 ${meta}，下载原文 ${pdf}` +
      (noCand ? `，无开放 PDF ${noCand}` : '') +
      (failed ? `，失败 ${failed}` : '') +
      '（公开接口，不使用文献 MCP）'
    );
  }
  return (
    `Sync done: metadata ${meta}, PDFs ${pdf}` +
    (noCand ? `, no OA PDF ${noCand}` : '') +
    (failed ? `, failed ${failed}` : '') +
    ' (public APIs only; literature MCP not used)'
  );
}

export async function openLiteratureLibrary(
  context: vscode.ExtensionContext,
  item?: { filePath?: string }
): Promise<void> {
  const root = workspaceRoot();
  if (!root) {
    vscode.window.showErrorMessage(localize('extension.literature.noWorkspace'));
    return;
  }
  const indexPath =
    typeof item?.filePath === 'string' && item.filePath.endsWith('literature_index.json')
      ? item.filePath
      : ensureIndexFile(root);
  await LiteratureIndexViewer.show(context, indexPath);
}

export async function runSyncLiteratureLibrary(): Promise<void> {
  const isZh = isExtensionZh();
  const root = workspaceRoot();
  if (!root) {
    vscode.window.showErrorMessage(localize('extension.literature.noWorkspace'));
    return;
  }
  ensureIndexFile(root);

  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: isZh
        ? '正在同步完善文献库（公开元数据 + 开放 PDF）…'
        : 'Syncing literature library (public metadata + OA PDFs)…',
    },
    async () => {
      try {
        const payload = await syncLiteratureLibrary(root);
        if (!payload.ok) {
          throw new Error(payload.error || 'Sync failed');
        }
        vscode.window.showInformationMessage(formatSyncSummary(payload, isZh));
        void vscode.commands.executeCommand('aiSocialScientist.refreshProjectView');
      } catch (error: any) {
        vscode.window.showErrorMessage(
          isZh
            ? `同步失败: ${error.message || error}`
            : `Sync failed: ${error.message || error}`
        );
      }
    }
  );
}

export async function runExportLiteratureBib(mode: 'copy' | 'file'): Promise<void> {
  const isZh = isExtensionZh();
  const root = workspaceRoot();
  if (!root) {
    vscode.window.showErrorMessage(localize('extension.literature.noWorkspace'));
    return;
  }
  ensureIndexFile(root);

  try {
    const payload = await exportLiteratureBibtex(root, undefined, mode === 'copy');
    if (!payload.ok) {
      throw new Error(payload.error || 'Export failed');
    }
    const bibtex = typeof payload.bibtex === 'string' ? payload.bibtex : '';
    if (!bibtex.trim()) {
      vscode.window.showWarningMessage(
        isZh ? '文献库为空，没有可导出的 BibTeX。' : 'Literature library is empty.'
      );
      return;
    }
    if (mode === 'copy') {
      await vscode.env.clipboard.writeText(bibtex);
      vscode.window.showInformationMessage(
        isZh
          ? `已复制 ${payload.count ?? 0} 条 BibTeX`
          : `Copied ${payload.count ?? 0} BibTeX entr(y/ies)`
      );
    } else {
      vscode.window.showInformationMessage(
        isZh
          ? `已写入 ${payload.path || 'papers/library.bib'}（${payload.count ?? 0} 条）`
          : `Wrote ${payload.path || 'papers/library.bib'} (${payload.count ?? 0})`
      );
      void vscode.commands.executeCommand('aiSocialScientist.refreshProjectView');
    }
  } catch (error: any) {
    vscode.window.showErrorMessage(
      isZh
        ? `导出 BibTeX 失败: ${error.message || error}`
        : `BibTeX export failed: ${error.message || error}`
    );
  }
}

export async function runImportLiteratureBib(
  context: vscode.ExtensionContext
): Promise<void> {
  const isZh = isExtensionZh();
  const root = workspaceRoot();
  if (!root) {
    vscode.window.showErrorMessage(localize('extension.literature.noWorkspace'));
    return;
  }

  const uris = await vscode.window.showOpenDialog({
    canSelectMany: false,
    openLabel: isZh ? '导入 BibTeX' : 'Import BibTeX',
    filters: { BibTeX: ['bib'] },
  });
  if (!uris || uris.length === 0) {
    return;
  }

  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: isZh ? '正在导入 BibTeX…' : 'Importing BibTeX…',
    },
    async () => {
      try {
        const payload = await importLiteratureBibtex(root, uris[0].fsPath);
        if (!payload.ok) {
          throw new Error(payload.error || 'Import failed');
        }
        vscode.window.showInformationMessage(
          isZh
            ? `导入完成：新增 ${payload.added ?? 0}，重复 ${payload.duplicates ?? 0}`
            : `Import done: added ${payload.added ?? 0}, duplicates ${payload.duplicates ?? 0}`
        );
        void vscode.commands.executeCommand('aiSocialScientist.refreshProjectView');
        await openLiteratureLibrary(context);
      } catch (error: any) {
        vscode.window.showErrorMessage(
          isZh
            ? `导入失败: ${error.message || error}`
            : `Import failed: ${error.message || error}`
        );
      }
    }
  );
}

export function registerLiteratureLibraryCommands(
  context: vscode.ExtensionContext
): vscode.Disposable[] {
  return [
    vscode.commands.registerCommand(
      'aiSocialScientist.viewLiteratureIndex',
      async (item?: { filePath?: string }) => openLiteratureLibrary(context, item)
    ),
    vscode.commands.registerCommand(
      'aiSocialScientist.syncLiteratureLibrary',
      () => runSyncLiteratureLibrary()
    ),
    vscode.commands.registerCommand(
      'aiSocialScientist.exportLiteratureBibCopy',
      () => runExportLiteratureBib('copy')
    ),
    vscode.commands.registerCommand(
      'aiSocialScientist.exportLiteratureBibFile',
      () => runExportLiteratureBib('file')
    ),
    vscode.commands.registerCommand(
      'aiSocialScientist.importLiteratureBib',
      () => runImportLiteratureBib(context)
    ),
  ];
}
