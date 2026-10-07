# Webview 组件

此目录包含 VSCode 插件中使用的 Webview 前端组件（React）。

## 目录结构

```
webview/
├── components/      # 共享 React 组件
├── configPage/      # 配置页面 Webview 组件
├── prefillParams/   # 预填充参数查看器组件
├── replay/          # 回放可视化组件
├── simSettings/     # SIM_SETTINGS 编辑器组件
├── i18n/            # 国际化资源
└── tsconfig.json    # TypeScript 配置
```

## 关联文件

### 前端入口（VSCode Extension）

- `@extension/src/configPageViewProvider.ts` - 配置页面提供者，加载 `configPage.js`
- `@extension/src/prefillParamsViewProvider.ts` - 预填充参数提供者，加载 `prefillParams.js`
- `@extension/src/replayWebviewProvider.ts` - 回放可视化提供者，加载 `replay.js`
- `@extension/src/simSettingsEditorProvider.ts` - SIM_SETTINGS 编辑器，加载 `simSettings.js`

### 后端 API

- `@packages/agentsociety2/agentsociety2/backend/app.py` - FastAPI 应用主入口
- `@packages/agentsociety2/agentsociety2/backend/routers/prefill_params.py` - 预填充参数 API
- `@packages/agentsociety2/agentsociety2/backend/routers/experiments.py` - 实验数据 API
- `@packages/agentsociety2/agentsociety2/backend/routers/replay.py` - 回放数据 API
- `@packages/agentsociety2/agentsociety2/backend/routers/modules.py` - 模块列表 API

## 构建流程

React 组件通过 webpack 编译为单个 JavaScript 文件，输出到 `extension/out/webview/` 目录：

- `configPage.tsx` → `out/webview/configPage.js`
- `prefillParams.tsx` → `out/webview/prefillParams.js`
- `replay.tsx` → `out/webview/replay.js`
- `simSettings.tsx` → `out/webview/simSettings.js`

## 组件说明

### configPage

配置页面，用于首次启动或手动配置时设置 LLM API 密钥等参数。

**关联：** `@extension/src/configPageViewProvider.ts`, `@extension/src/envManager.ts`

### prefillParams

预填充参数查看器（只读），显示可用的 Agent 类和 Environment 模块类的预填充参数。

**关联：** `@extension/src/prefillParamsViewProvider.ts`

### replay

回放可视化组件，用于展示和回放仿真实验数据。

**关联：** `@extension/src/replayWebviewProvider.ts`

### simSettings

SIM_SETTINGS.json 文件的自定义编辑器。

**关联：** `@extension/src/simSettingsEditorProvider.ts`
