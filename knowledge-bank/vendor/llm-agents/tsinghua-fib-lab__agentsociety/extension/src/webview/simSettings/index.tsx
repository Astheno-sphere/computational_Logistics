import * as React from 'react';
import * as ReactDOM from 'react-dom/client';
import { SimSettingsApp } from './SimSettingsApp';
import type { VSCodeAPI, SimSettings, AgentInfo, EnvModuleInfo } from './types';
import 'antd/dist/reset.css';
import '../i18n';

// 声明全局函数 acquireVsCodeApi
declare function acquireVsCodeApi(): VSCodeAPI;

// 获取 VSCode API
const vscode: VSCodeAPI = acquireVsCodeApi();

// 从全局变量获取初始设置（由 webview HTML 注入）
declare global {
  interface Window {
    initialSettings?: SimSettings;
  }
}

const initialSettings: SimSettings = window.initialSettings || {};

// 渲染 React 应用
const rootElement = document.getElementById('root');
if (rootElement) {
  const root = ReactDOM.createRoot(rootElement);
  root.render(
    <SimSettingsApp
      vscode={vscode}
      initialSettings={initialSettings}
    />
  );
} else {
  console.error('Root element not found');
}

