import * as React from 'react';

interface ConfigPageErrorBoundaryProps {
  children: React.ReactNode;
}

interface ConfigPageErrorBoundaryState {
  error: Error | null;
}

function resolveUiLanguage(): 'zh-CN' | 'en-US' {
  const injected = typeof window !== 'undefined' ? window.__AS_LANG__ : undefined;
  if (injected === 'en-US' || injected === 'en') {
    return 'en-US';
  }
  return 'zh-CN';
}

const COPY = {
  'zh-CN': {
    title: '配置页加载失败',
    hint: '请重新加载窗口后重试。如果仍然失败，请重新打开配置页。',
  },
  'en-US': {
    title: 'Config page failed to load',
    hint: 'Reload the window and try again. If it still fails, reopen the configuration page.',
  },
} as const;

export class ConfigPageErrorBoundary extends React.Component<
  ConfigPageErrorBoundaryProps,
  ConfigPageErrorBoundaryState
> {
  state: ConfigPageErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ConfigPageErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    console.error('ConfigPage render error:', error, info.componentStack);
  }

  render(): React.ReactNode {
    const { error } = this.state;
    if (!error) {
      return this.props.children;
    }

    const copy = COPY[resolveUiLanguage()];

    return (
      <div
        style={{
          minHeight: '100vh',
          padding: 24,
          fontFamily: 'var(--vscode-font-family, sans-serif)',
          background: 'var(--vscode-editor-background)',
          color: 'var(--vscode-editor-foreground, #ccc)',
        }}
      >
        <h2 style={{ marginBottom: 12, fontSize: 18 }}>{copy.title}</h2>
        <p style={{ marginBottom: 12, opacity: 0.85 }}>{copy.hint}</p>
      </div>
    );
  }
}
