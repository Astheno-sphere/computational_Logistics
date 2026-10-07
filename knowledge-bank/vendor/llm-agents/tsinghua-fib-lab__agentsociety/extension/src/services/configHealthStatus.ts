import * as vscode from 'vscode';
import { localize } from '../i18n';

const GLOBAL_KEY = 'configHealth.defaultLlm';

export type DefaultLlmHealth = {
  valid: boolean;
  model: string;
  validatedAt: number;
  error?: string;
};

export function setDefaultLlmHealth(
  context: vscode.ExtensionContext,
  health: DefaultLlmHealth | null
): void {
  void context.globalState.update(GLOBAL_KEY, health);
}

export function getDefaultLlmHealth(
  context: vscode.ExtensionContext
): DefaultLlmHealth | null {
  return context.globalState.get<DefaultLlmHealth | null>(GLOBAL_KEY) ?? null;
}

export class ConfigHealthStatusBar {
  private readonly item: vscode.StatusBarItem;

  constructor(private readonly context: vscode.ExtensionContext) {
    this.item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 98);
    this.item.command = 'aiSocialScientist.openConfigPage';
    context.subscriptions.push(this.item);
    this.refresh();
  }

  refresh(): void {
    const health = getDefaultLlmHealth(this.context);
    if (!health) {
      this.item.hide();
      return;
    }
    if (health.valid) {
      const model = this.shortModelName(health.model);
      this.item.text = `$(check) ${model}`;
      this.item.tooltip = localize('configHealth.statusBar.validTooltipShort', health.model);
      this.item.backgroundColor = undefined;
    } else {
      this.item.text = '$(warning) LLM';
      this.item.tooltip = health.error ?? localize('configHealth.statusBar.invalidTooltip');
      this.item.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
    }
    this.item.show();
  }

  private shortModelName(model: string): string {
    const trimmed = model.trim();
    if (trimmed.length <= 18) {
      return trimmed;
    }
    return `${trimmed.slice(0, 16)}…`;
  }

  updateFromValidation(
    success: boolean,
    model: string,
    error?: string | null
  ): void {
    setDefaultLlmHealth(this.context, {
      valid: success,
      model: model.trim() || localize('configHealth.statusBar.modelUnset'),
      validatedAt: Date.now(),
      error: error ?? undefined,
    });
    this.refresh();
  }
}
