import * as React from 'react';
import * as ReactDOM from 'react-dom/client';
import { PrefillParamsApp } from './PrefillParamsApp';
import type { VSCodeAPI } from './types';
import 'antd/dist/reset.css';
import '../i18n';

// 声明全局函数 acquireVsCodeApi
declare function acquireVsCodeApi(): VSCodeAPI;

// 获取 VSCode API
const vscode: VSCodeAPI = acquireVsCodeApi();

// 渲染 React 应用
const rootElement = document.getElementById('root');
if (rootElement) {
  const root = ReactDOM.createRoot(rootElement);
  root.render(
    <PrefillParamsApp vscode={vscode} />
  );
} else {
  console.error('Root element not found');
}
