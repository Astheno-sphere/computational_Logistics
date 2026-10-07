/**
 * Claude Code 配置入口：跳转至主配置页高级区 Claude Code 标签。
 */

import * as vscode from 'vscode';
import { ConfigPageViewProvider } from './configPageViewProvider';
import { isClaudeCodeEnvCustomized } from './services/claudeCodeSettings';

export { isClaudeCodeEnvCustomized };

export function openClaudeCodeConfig(
  context: vscode.ExtensionContext,
  viewColumn: vscode.ViewColumn = vscode.ViewColumn.One
): void {
  ConfigPageViewProvider.createOrShow(context, viewColumn);
  queueMicrotask(() => {
    ConfigPageViewProvider.currentPanel?.navigateToAdvancedTab('claude');
  });
}
