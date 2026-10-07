/**
 * AI Chat Invoker - 支持 Claude Code、Codex、Cursor 和 VSCode Chat
 *
 * 当有多个 AI Chat 提供商可用时，弹出 QuickPick 让用户选择，
 * 并可选"记住"选择到 VSCode 设置中。
 */

import * as vscode from 'vscode';
import { getMainOutputChannel } from './shared/outputChannels';

export type AIChatType = 'claude-code' | 'codex' | 'cursor' | 'vscode-chat' | 'none';

const CHAT_LABELS: Record<Exclude<AIChatType, 'none'>, string> = {
  'claude-code': 'Claude Code',
  'codex': 'Codex',
  'cursor': 'Cursor Chat',
  'vscode-chat': 'VSCode Chat',
};

const CHAT_DESCRIPTIONS: Record<Exclude<AIChatType, 'none'>, string> = {
  'claude-code': 'Anthropic Claude Code extension',
  'codex': 'OpenAI Codex extension',
  'cursor': 'Cursor built-in chat',
  'vscode-chat': 'VSCode built-in chat panel',
};

const OPEN_COMMANDS: Record<Exclude<AIChatType, 'none'>, string> = {
  'claude-code': 'claude-vscode.editor.open',
  'codex': 'chatgpt.openSidebar',
  'cursor': 'cursor.chat',
  'vscode-chat': 'workbench.action.chat.open',
};

export class AIChatInvoker {
  private outputChannel: vscode.OutputChannel;

  constructor() {
    this.outputChannel = getMainOutputChannel();
  }

  private log(message: string): void {
    this.outputChannel.appendLine(`${new Date().toISOString()} [Chat] ${message}`);
  }

  /**
   * Detect all available AI chat providers.
   */
  getAvailableChats(): Exclude<AIChatType, 'none'>[] {
    const available: Exclude<AIChatType, 'none'>[] = [];

    if (vscode.extensions.getExtension('anthropic.claude-code')) {
      available.push('claude-code');
    }
    if (vscode.extensions.getExtension('openai.chatgpt')) {
      available.push('codex');
    }
    if (typeof (vscode.env as any).appHost === 'string'
      && ((vscode.env as any).appHost as string).includes('cursor')) {
      available.push('cursor');
    }
    try {
      if (vscode.chat) {
        available.push('vscode-chat');
      }
    } catch {
      // chat API 不存在
    }

    return available;
  }

  private getPreferredFromConfig(): AIChatType | undefined {
    const config = vscode.workspace.getConfiguration('aiSocialScientist');
    const saved = config.get<string>('preferredAiChat', '');
    if (saved && saved !== 'none' && saved in OPEN_COMMANDS) {
      return saved as AIChatType;
    }
    return undefined;
  }

  async invokeChat(): Promise<boolean> {
    const available = this.getAvailableChats();

    if (available.length === 0) {
      vscode.window.showInformationMessage(
        'Install Claude Code: https://claude.ai/code or Codex: https://marketplace.visualstudio.com/items?itemName=openai.chatgpt'
      );
      return false;
    }

    // If only one provider, use it directly
    if (available.length === 1) {
      return this._openChat(available[0]);
    }

    // Check for saved preference
    const preferred = this.getPreferredFromConfig();
    if (preferred && available.includes(preferred as Exclude<AIChatType, 'none'>)) {
      return this._openChat(preferred as Exclude<AIChatType, 'none'>);
    }

    // Multiple available, no preference — show QuickPick
    return this._pickAndOpen(available);
  }

  /**
   * Show the provider picker regardless of saved preference (for "change provider" command).
   */
  async pickProvider(): Promise<boolean> {
    const available = this.getAvailableChats();

    if (available.length === 0) {
      vscode.window.showInformationMessage(
        'No AI Chat provider available. Install Claude Code or Codex.'
      );
      return false;
    }

    return this._pickAndOpen(available);
  }

  private async _pickAndOpen(available: Exclude<AIChatType, 'none'>[]): Promise<boolean> {
    const items = available.map((type) => {
      const isSaved = this.getPreferredFromConfig() === type;
      return {
        label: (isSaved ? '$(bookmark) ' : '') + CHAT_LABELS[type],
        description: isSaved ? '当前默认' : '',
        detail: CHAT_DESCRIPTIONS[type],
        type,
      };
    });

    const selected = await vscode.window.showQuickPick(items, {
      placeHolder: '选择要打开的 AI Chat',
      title: 'AI Chat 提供商',
    });

    if (!selected) {
      return false;
    }

    // Ask if they want to remember
    const remember = await vscode.window.showInformationMessage(
      `记住「${CHAT_LABELS[selected.type]}」为默认 AI Chat？`,
      '记住', '仅本次'
    );

    if (remember === '记住') {
      const config = vscode.workspace.getConfiguration('aiSocialScientist');
      await config.update('preferredAiChat', selected.type, vscode.ConfigurationTarget.Global);
    }

    return this._openChat(selected.type);
  }

  private async _openChat(type: Exclude<AIChatType, 'none'>): Promise<boolean> {
    const command = OPEN_COMMANDS[type];
    this.log(`Invoking ${type}...`);

    const success = await vscode.commands.executeCommand(command).then(
      () => true,
      (err) => {
        this.log(`Failed: ${err}`);
        return false;
      }
    );

    if (!success) {
      vscode.window.showInformationMessage(
        `Failed to open ${CHAT_LABELS[type]}. Make sure the extension is installed and enabled.`
      );
    }
    return success;
  }

  dispose(): void {
  }
}
