/**
 * Open workspace files with the right viewer (PDF preview webview, markdown preview, etc.).
 */

import * as path from 'path';
import * as vscode from 'vscode';
import { isExtensionZh } from './i18n';

const PDF_PANEL_TYPE = 'agentsocietyPdfPreview';

/**
 * Open a PDF in an iframe webview. The text editor cannot render binary PDFs
 * (especially under code-server).
 */
export async function openPdfPreview(filePath: string): Promise<void> {
  const uri = vscode.Uri.file(filePath);
  const panel = vscode.window.createWebviewPanel(
    PDF_PANEL_TYPE,
    path.basename(filePath),
    vscode.ViewColumn.Beside,
    {
      enableScripts: false,
      retainContextWhenHidden: true,
      localResourceRoots: [vscode.Uri.file(path.dirname(filePath))],
    }
  );
  const src = panel.webview.asWebviewUri(uri);
  const isZh = isExtensionZh();
  panel.webview.html = `<!DOCTYPE html>
<html lang="${isZh ? 'zh-CN' : 'en'}">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>${escapeHtml(path.basename(filePath))}</title>
  <style>
    html, body { margin: 0; height: 100%; background: var(--vscode-editor-background, #1e1e1e); }
    iframe { border: 0; width: 100%; height: 100%; }
    .fallback {
      font-family: var(--vscode-font-family);
      color: var(--vscode-descriptionForeground);
      padding: 24px;
      line-height: 1.5;
    }
  </style>
</head>
<body>
  <iframe src="${src}" title="PDF"></iframe>
  <noscript>
    <div class="fallback">${isZh ? '无法预览 PDF，请在资源管理器中打开该文件。' : 'PDF preview requires a browser engine that can render PDFs.'}</div>
  </noscript>
</body>
</html>`;
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/** Open a workspace file with an appropriate viewer. */
export async function openWorkspaceFile(filePath: string): Promise<void> {
  const uri = vscode.Uri.file(filePath);
  const ext = path.extname(filePath).toLowerCase();
  if (ext === '.md' || ext === '.markdown') {
    await vscode.commands.executeCommand('markdown.showPreview', uri);
    return;
  }
  if (ext === '.pdf') {
    await openPdfPreview(filePath);
    return;
  }
  await vscode.commands.executeCommand('vscode.open', uri);
}
