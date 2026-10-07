import '../i18n';
import * as React from 'react';
import * as ReactDOM from 'react-dom/client';
import { ConfigPageApp } from './ConfigPageApp';
import { ConfigPageErrorBoundary } from './ConfigPageErrorBoundary';
import type { VSCodeAPI } from './types';
import 'antd/dist/reset.css';

declare function acquireVsCodeApi(): VSCodeAPI;

const vscode: VSCodeAPI = acquireVsCodeApi();

const rootElement = document.getElementById('root');
if (rootElement) {
  const root = ReactDOM.createRoot(rootElement);
  root.render(
    <ConfigPageErrorBoundary>
      <ConfigPageApp vscode={vscode} />
    </ConfigPageErrorBoundary>
  );
} else {
  console.error('Root element not found');
}
