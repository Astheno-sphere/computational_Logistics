import * as vscode from 'vscode';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { localize } from '../i18n';
import { getMainOutputChannel } from '../shared/outputChannels';
import { resolveAgentsocietyPython } from './agentsocietyPythonResolver';
import { collectContentDigests, runPythonArchiveCommand } from './workspaceArchiveIo';
import {
  WORKSPACE_EXPORT_MANIFEST_RELATIVE_PATH,
  canonicalizeContentHash,
  formatExportRootSummary,
  parseExportManifest,
  planImportTarget,
  shouldSkipImportPath,
  verifyZipMagic,
} from './workspaceExportManifest';

export class WorkspaceImportManager implements vscode.Disposable {
  private readonly outputChannel: vscode.OutputChannel;

  constructor() {
    this.outputChannel = getMainOutputChannel();
  }

  async importWorkspaceZip(): Promise<void> {
    const zipUri = await vscode.window.showOpenDialog({
      canSelectFiles: true,
      canSelectFolders: false,
      canSelectMany: false,
      filters: { 'ZIP Archive': ['zip'] },
      openLabel: localize('workspaceImport.openLabel'),
      title: localize('workspaceImport.title'),
    });
    if (!zipUri || zipUri.length === 0) {
      return;
    }
    const zipPath = zipUri[0].fsPath;
    if (!verifyZipMagic(zipPath)) {
      vscode.window.showErrorMessage(localize('workspaceImport.invalidZip'));
      return;
    }

    const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'ai-social-scientist-import-'));
    try {
      const extractedRoot = path.join(tempRoot, 'extracted');
      fs.mkdirSync(extractedRoot, { recursive: true });
      const parsed = await vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: localize('workspaceImport.progress'),
          cancellable: false,
        },
        async () => {
          const pythonCommand = this.resolvePython();
          await runPythonArchiveCommand(pythonCommand, 'extract', zipPath, extractedRoot);
          const manifestPath = path.join(extractedRoot, WORKSPACE_EXPORT_MANIFEST_RELATIVE_PATH);
          if (!fs.existsSync(manifestPath)) {
            throw new Error(localize('workspaceImport.invalidManifest'));
          }
          const result = parseExportManifest(JSON.parse(fs.readFileSync(manifestPath, 'utf-8')));
          if (!result.ok) {
            throw new Error(localize(
              result.error === 'unsupported_version'
                ? 'workspaceImport.unsupportedVersion'
                : 'workspaceImport.invalidManifest',
            ));
          }
          const actualHash = canonicalizeContentHash(collectContentDigests(extractedRoot));
          if (actualHash !== result.manifest.contentHash) {
            throw new Error(localize('workspaceImport.hashMismatch'));
          }
          return result.manifest;
        },
      );

      const parent = await vscode.window.showOpenDialog({
        canSelectFiles: false,
        canSelectFolders: true,
        canSelectMany: false,
        defaultUri: vscode.workspace.workspaceFolders?.[0]?.uri,
        openLabel: localize('workspaceImport.pickParentLabel'),
        title: localize('workspaceImport.pickParentTitle'),
      });
      if (!parent || parent.length === 0) {
        return;
      }

      const parentPath = parent[0].fsPath;
      const projectName = await vscode.window.showInputBox({
        title: localize('workspaceImport.projectNameTitle'),
        prompt: localize('workspaceImport.projectNamePrompt', parentPath),
        value: parsed.workspaceName,
        valueSelection: [0, parsed.workspaceName.length],
        ignoreFocusOut: true,
        validateInput: (value) => {
          const plan = planImportTarget(parentPath, value);
          if (plan.ok) {
            return undefined;
          }
          return localize(`workspaceImport.target.${plan.error}`);
        },
      });
      if (projectName === undefined) {
        return;
      }
      const targetPlan = planImportTarget(parentPath, projectName);
      if (!targetPlan.ok) {
        throw new Error(localize(`workspaceImport.target.${targetPlan.error}`));
      }
      const targetRoot = targetPlan.targetPath;
      const rootSummary = formatExportRootSummary(parsed.roots)
        || localize('workspaceImport.successRootsFallback');

      const confirm = localize('workspaceImport.noticeConfirm');
      const choice = await vscode.window.showWarningMessage(
        [
          localize('workspaceImport.confirmSummary', projectName, targetRoot, rootSummary),
          '',
          localize('workspaceExport.share.copyright'),
          '',
          localize('workspaceExport.share.redistribution'),
          '',
          `• ${localize('workspaceImport.securitySecrets')}`,
          `• ${localize('workspaceImport.securitySkills')}`,
          `• ${localize('workspaceImport.securityIntegrity')}`,
          `• ${localize('workspaceImport.securityImporter')}`,
        ].join('\n'),
        { modal: true },
        confirm,
      );
      if (choice !== confirm) {
        return;
      }

      try {
        fs.mkdirSync(targetRoot);
      } catch (error: unknown) {
        if (
          error instanceof Error &&
          'code' in error &&
          error.code === 'EEXIST'
        ) {
          throw new Error(localize('workspaceImport.target.target_exists'));
        }
        throw error;
      }

      let skipped: string[];
      try {
        skipped = this.copyExtractedTree(extractedRoot, targetRoot, '');
      } catch (error) {
        fs.rmSync(targetRoot, { recursive: true, force: true });
        throw error;
      }
      this.log(`Imported workspace into ${targetRoot}`);
      if (skipped.length > 0) {
        this.log(`Skipped sensitive or non-portable paths: ${skipped.join(', ')}`);
      }

      const openLabel = localize('workspaceImport.openFolder');
      const copyPathLabel = localize('workspaceImport.copyPath');
      const action = await vscode.window.showInformationMessage(
        localize(
          'workspaceImport.success',
          targetRoot,
          rootSummary,
        ),
        openLabel,
        copyPathLabel,
      );
      if (action === openLabel) {
        await vscode.commands.executeCommand('vscode.openFolder', vscode.Uri.file(targetRoot), true);
      } else if (action === copyPathLabel) {
        await vscode.env.clipboard.writeText(targetRoot);
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      this.log(`Import failed: ${message}`);
      const action = await vscode.window.showErrorMessage(
        localize('workspaceImport.failed', message),
        localize('workspaceExport.viewOutput'),
      );
      if (action === localize('workspaceExport.viewOutput')) {
        this.outputChannel.show(true);
      }
    } finally {
      fs.rmSync(tempRoot, { recursive: true, force: true });
    }
  }

  dispose(): void {
    return;
  }

  private copyExtractedTree(sourceDir: string, targetDir: string, relativeDir: string): string[] {
    const skipped: string[] = [];
    fs.mkdirSync(targetDir, { recursive: true });
    for (const entry of fs.readdirSync(sourceDir, { withFileTypes: true })) {
      const relativePath = relativeDir ? `${relativeDir}/${entry.name}` : entry.name;
      if (shouldSkipImportPath(relativePath)) {
        skipped.push(relativePath);
        continue;
      }
      const from = path.join(sourceDir, entry.name);
      const to = path.join(targetDir, entry.name);
      if (fs.existsSync(to) && !entry.isDirectory()) {
        throw new Error(localize('workspaceImport.targetConflict', entry.name));
      }
      if (entry.isDirectory()) {
        skipped.push(...this.copyExtractedTree(from, to, relativePath));
      } else if (entry.isFile()) {
        fs.copyFileSync(from, to);
      } else {
        skipped.push(relativePath);
      }
    }
    return skipped;
  }

  private resolvePython(): string {
    const workspacePath = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    const resolved = resolveAgentsocietyPython({
      workspacePath,
      extensionPath: vscode.extensions.getExtension('tsinghua-fib-lab.ai-social-scientist')?.extensionPath,
    });
    if (resolved) {
      return resolved;
    }
    return process.platform === 'win32' ? 'python' : 'python3';
  }

  private log(message: string): void {
    this.outputChannel.appendLine(`[${new Date().toISOString()}] [Import] ${message}`);
  }
}
