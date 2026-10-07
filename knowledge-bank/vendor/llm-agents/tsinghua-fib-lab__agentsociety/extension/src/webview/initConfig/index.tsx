import * as React from 'react';
import * as ReactDOM from 'react-dom/client';
import { InitConfigApp } from './InitConfigApp';

declare function acquireVsCodeApi(): any;

const vscode = acquireVsCodeApi();

// 从全局变量获取初始配置
const initialConfig = (window as any).initialConfig;

const root = ReactDOM.createRoot(document.getElementById('root')!);
root.render(<InitConfigApp vscode={vscode} initialConfig={initialConfig} />);
