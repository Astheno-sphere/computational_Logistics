# AI Social Scientist Extension - Development Guide

## 目录

- [开发环境设置](#开发环境设置)
- [项目结构](#项目结构)
- [核心模块](#核心模块)
- [后端开发](#后端开发)
- [React Webview 开发](#react-webview-开发)
- [帮助页面维护](#帮助页面维护)
- [打包发布](#打包发布)
- [代码规范](#代码规范)

## 开发环境设置

### 前置要求

- Node.js ^22.13.0 或 >=24（与 `package.json` 的 `engines`、`.nvmrc` 一致）
- Python >= 3.11
- uv (Python 包管理器)
- VSCode >= 1.120.0

### 安装依赖

```bash
cd extension
npm ci
```

### 编译项目

```bash
npm run build        # 生产构建：tsc 主进程 + webpack 全部 webview
npm run rebuild      # 清理后重新构建
npm run compile      # 仅编译主进程 TypeScript（不含 webview）
npm run watch        # tsc --watch（主进程）
npm run dev          # 主进程 tsc watch + webview webpack watch（并发）
```

### 清理

```bash
npm run clean        # 删除 out、.vsix、缓存等
npm run clean:deep   # 含 node_modules
npm run clean:dry-run # 仅预览，不删除
```

### 测试与检查

```bash
npm run lint              # ESLint 检查
npm run test:gateway      # extension/test 冒烟单测（鉴权 / 分享 / 技能源）
npm run check             # lint + test:gateway + build
```

### 调试

1. 在 VSCode 中打开 `extension` 文件夹
2. 按 `F5` 启动调试会话
3. 新的 Extension Development Host 窗口将打开

## 项目结构

```
extension/
├── src/                              # 源代码目录
│   ├── extension.ts                  # 主入口文件
│   ├── projectStructureProvider.ts   # 项目结构树视图提供者
│   ├── apiClient.ts                  # API 客户端
│   ├── configPageViewProvider.ts     # 配置页面 Webview
│   ├── helpPageViewProvider.ts       # 帮助页面 Webview
│   ├── prefillParamsViewProvider.ts  # 预填充参数查看器
│   ├── replayWebviewProvider.ts      # 回放可视化 Webview
│   ├── simSettingsEditorProvider.ts  # SIM_SETTINGS 自定义编辑器
│   ├── initConfigEditorProvider.ts   # init_config 自定义编辑器
│   ├── skillMarketplaceProvider.ts   # 技能市场面板
│   ├── envManager.ts                 # 环境变量(.env)管理
│   ├── i18n.ts                       # 国际化字符串
│   ├── jsonViewer.ts                 # JSON 可视化查看器
│   ├── yamlViewer.ts                 # YAML 可视化查看器
│   ├── stepsViewer.ts                # 步骤时间线查看器
│   ├── pidStatusViewer.ts            # 实验状态监控查看器
│   ├── literatureIndexViewer.ts      # 文献索引查看器
│   ├── experimentResultsViewer.ts    # 实验结果查看器
│   ├── dragAndDropController.ts      # 拖放控制器
│   ├── runtimeConfig.ts              # 运行时配置读取
│   ├── atReference.ts                # @引用格式工具
│   ├── aiChatInvoker.ts              # AI Chat 调用器
│   ├── portUtils.ts                  # 动态端口分配
│   ├── workspaceManager.ts           # 工作区管理
│   ├── aiCli/                        # CLI 供应商共享逻辑（extension 与 webview 共用）
│   │   ├── officialEndpoints.ts      # 官方端点常量与 apiKind 推断（唯一实现）
│   │   ├── providerAuth.ts           # 供应商鉴权模式 / 角色上游计数
│   │   ├── upstreamAuthHeaders.ts    # 上游鉴权请求头（auto / bearer / x-api-key / both）
│   │   └── providerPresets.ts        # 供应商预设与模型合并
│   ├── services/                     # 服务模块
│   │   ├── aiCliGateway.ts           # HTTP 代理核心（路由、格式转换、上游转发）
│   │   ├── aiCliGatewayManager.ts    # 供应商生命周期、用量追踪、故障转移
│   │   ├── aiCliGatewayUpstream.ts   # 上游供应商类型定义
│   │   ├── anthropicModelMapping.ts  # Claude 角色模型名 → 供应商模型名映射
│   │   ├── anthropicOpenAiBridge.ts  # Anthropic Messages ↔ OpenAI Chat 格式转换
│   │   ├── backendManager.ts         # 后端进程管理
│   │   ├── backendService.ts         # 后端服务接口
│   │   ├── claudeCodeModels.ts       # 模型列表拉取
│   │   ├── claudeCodeSettings.ts     # ~/.claude/settings.json 读写
│   │   ├── codexApiFormat.ts         # OpenAI API 格式检测
│   │   ├── codexModelMapping.ts      # Codex 模型名 → 供应商模型名映射
│   │   ├── codexResponsesBridge.ts   # Codex Responses ↔ OpenAI Chat 格式转换
│   │   ├── codexSettings.ts          # Codex 配置读写
│   │   ├── gatewayFailover.ts        # 故障转移：断路器、优先级排序
│   │   ├── gatewayModelPricing.ts    # 模型定价与成本计算
│   │   ├── gatewayProviderUsage.ts   # 供应商配额查询
│   │   ├── gatewayRemotePricing.ts   # 远程定价数据拉取与缓存
│   │   ├── gatewayUsageTracker.ts    # Token 用量提取与聚合（要求显式 app，无历史猜测）
│   │   ├── httpClient.ts             # HTTP 请求客户端
│   │   ├── index.ts                  # 服务模块导出
│   │   ├── llmValidator.ts           # LLM 配置验证
│   │   ├── officialBuiltinModels.ts  # 内置模型列表（API 不可用时的兜底）
│   │   ├── responsesAnthropicBridge.ts # Codex Responses ↔ Anthropic Messages 格式转换
│   │   ├── validateTimeouts.ts       # 超时配置校验
│   │   ├── workspaceExportManager.ts # 工作区导出
│   │   └── workspaceImportManager.ts # 工作区导入
│   ├── webview/                      # React Webview 组件
│   │   ├── components/               # 共享组件
│   │   ├── configPage/               # 配置页面
│   │   ├── helpPage/                 # 帮助页面
│   │   ├── initConfig/               # 初始化配置
│   │   ├── prefillParams/            # 预填充参数界面
│   │   ├── replay/                   # 实验回放界面
│   │   ├── simSettings/              # SIM 设置界面
│   │   ├── skillMarketplace/         # 技能市场
│   │   ├── i18n/                     # 国际化资源
│   │   └── theme.ts                  # VSCode 主题适配
│   ├── platforms/                    # 多平台适配器
│   │   ├── PlatformAdapter.ts        # 平台适配器基类
│   │   ├── GitHubAdapter.ts          # GitHub API 适配器
│   │   ├── GitLabAdapter.ts          # GitLab API 适配器
│   │   └── GiteeAdapter.ts           # Gitee API 适配器
│   ├── skillMarketplace/             # 技能市场工具
│   │   ├── security.ts               # 安全验证
│   │   └── utils.ts                  # 工具函数
│   └── shared/                       # 共享模块
│       ├── messages.ts               # 消息类型定义
│       └── protocol.ts               # 通信协议
├── skills/                           # Claude Code Skills
│   ├── agentsociety-analysis/        # 数据分析
│   ├── agentsociety-create-agent/    # 创建 Agent
│   ├── agentsociety-create-env-module/ # 创建环境模块
│   ├── agentsociety-create-dataset/  # 创建数据集
│   ├── agentsociety-use-dataset/     # 使用数据集
│   ├── agentsociety-experiment-config/ # 实验配置
│   ├── agentsociety-hypothesis/      # 假设管理
│   ├── agentsociety-literature-search/ # 文献检索
│   ├── agentsociety-run-experiment/  # 运行实验
│   ├── agentsociety-scan-modules/    # 扫描模块
│   ├── paper-toolkit plugin             # 外部论文模板、证据图、检查和编译工具
│   ├── agentsociety-analysis/        # …/v1.0.0/support/frontend-design 等分析附属包
│   ├── docx/                         # Word 文档处理
│   ├── pdf/                          # PDF 文档处理
│   ├── pptx/                         # PPT 文档处理
│   └── xlsx/                         # Excel 文档处理
├── docs/                             # 开发文档
│   └── DEVELOPMENT.md                # 开发指南
├── test/                             # 单测（node:test，仅保留必要冒烟）
│   ├── gateway.test.js               # 网关鉴权 / 角色 / 用量
│   ├── parseSkillSourceInput.test.js # 技能源 URL 解析
│   └── workspaceShare.test.js        # 工作区分享包导入安全
├── CHANGELOG.md                      # 变更入口（指向仓库根 CHANGELOG）
├── README.md                         # 项目说明
├── package.json                      # 插件配置
├── tsconfig.json                     # TypeScript 配置
├── webpack.config.js                 # Webpack 构建配置
└── out/                              # 编译输出（自动生成）
```

## 核心模块

### 1. 项目结构视图 (ProjectStructureProvider)

**文件**: `src/projectStructureProvider.ts`

提供左侧树视图，展示工作区文件结构：

- **研究话题 (Topic)** - TOPIC.md 文件
- **假设 (Hypotheses)** - hypothesis_xxx/ 目录
- **实验 (Experiments)** - experiment_xxx/ 目录
- **论文 (Papers)** - papers/ 目录

支持特性：
- 拖放操作（文件拖入 papers/ 目录）
- 上下文菜单操作
- 自动刷新
- 实验状态概览显示
- 自定义模块扫描和测试

### 2. 配置页面 (ConfigPageViewProvider)

**文件**: `src/configPageViewProvider.ts`, `src/webview/configPage/`, `src/services/claudeCodeSettings.ts`

统一配置页（单页 Webview），配置写入工作区 `.env`；Claude Code 写入 `~/.claude/settings.json`：

| 区域             | 说明                                                                                   |
| ---------------- | -------------------------------------------------------------------------------------- |
| **配置向导**     | 仿真 LLM → 保存 `.env` → 启动后端 →（可选）文献 MCP / CLI 网关；可随时切到「全部设置」 |
| **全部设置 Tab** | 专用模型、Python、文献 MCP、Claude / Codex 供应商与网关路由                            |
| **概览卡片**     | 后端状态、配置验证汇总、Claude / Codex 状态；点击可跳转并触发验证                      |
| **底部操作**     | 恢复默认、保存、保存并启动后端、同步 Codex 配置                                        |

Webview 主要组件：

```
webview/configPage/
├── ConfigPageApp.tsx           # 主页面与向导步骤
├── AiCliConfigSection.tsx      # Claude / Codex 供应商与网关
├── AdvancedConfigSection.tsx   # 专用模型 / Python / 文献 MCP
├── WebConfigImportPanel.tsx    # Web 配置导入确认
├── ValidationAction.tsx        # 验证按钮
├── advancedValidation.ts       # 指纹与状态色
├── claudeCodeTypes.ts          # Claude 配置类型
└── ConfigPageErrorBoundary.tsx # 运行时错误边界
```

**验证策略**：修改配置约 1.5 秒后自动验证该项；概览卡片点击可验证全部；已验证且配置未变则不重复请求 API。

**Claude Code 入口**：命令 `aiSocialScientist.openClaudeCodeConfig` 打开本页并定位到 Claude / Codex 区域。

### 3. 帮助页面 (HelpPageViewProvider)

**文件**: `src/helpPageViewProvider.ts`, `src/webview/helpPage/`

默认嵌入 [ReadTheDocs](https://agentsociety2.readthedocs.io/)（中英文按 VS Code 语言切换）。iframe 加载失败时显示简短离线页（配置、技能市场等快捷入口）。

- 用户文档维护入口：`packages/agentsociety2/docs/`（见仓库根目录 `READTHEDOCS.md`）
- 离线回退页支持 `command:` 链接与外部 URL
- 注入脚本使用 CSP `nonce`（见 `helpPageViewProvider.ts`）

### 4. 后端管理器 (BackendManager)

**文件**: `src/services/backendManager.ts`

管理 FastAPI 后端进程的生命周期：

- 启动/停止/重启后端服务
- 动态端口分配
- 健康检查（每 10 秒）
- 进程 PID 管理
- 状态栏显示 Backend 端口、Gateway 路由与 LLM 验证状态
- 日志输出到 ``AI Social Scientist Backend`` 输出通道（主通道 ``AI Social Scientist`` 承载其余子系统日志）
- **激活阶段**使用 `loadConfig({ fast: true })`，避免在 `activate()` 中同步执行 `uv`/Python 全量探测（Coder 大工作区下会卡住扩展激活）；完整探测在 `start()` 前执行

#### 端口与状态检测逻辑

- **端口来源**：工作区 `.env` 的 `BACKEND_PORT`
- **插件启动后端**：若 `BACKEND_PORT` 可用就使用；若被占用则自动分配可用端口，并写回 `.env`
- **手动启动后端**：插件不会扫描端口；只会按 `.env` 的 `BACKEND_PORT` 进行 `/health` 检测与连接
- **通知去重**：配置页内「保存并启动后端」使用静默启动，仅在 Webview 内提示；命令面板/状态栏启动则显示单条 Toast

#### 后端状态查询

- `aiSocialScientist.backendStatusMenu`：状态栏菜单（启动/停止/日志/配置）
- `aiSocialScientist.getBackendStatus`：返回结构化状态对象（Webview/配置页数据源）

### 5. 技能市场 (SkillMarketplaceProvider)

**文件**: `src/skillMarketplaceProvider.ts`, `src/webview/skillMarketplace/`

管理 Agent 技能和 Claude 技能：

- **Agent 运行时** - 后端注册表（`built-in` / `env` / `custom`），工作区自定义装到 `custom/skills`；安装后会扫描注册
- **Claude 目录** - 安装到 `.claude/skills`；可用开关控制是否加载（关闭不删文件）
- 支持从 GitHub/GitLab/Gitee 仓库安装
- Agent 运行时技能按需被模型选择，无手动启停；内置行为技能以 `daily-guidance` 为主
- 内置 Claude 模板可同步到工作区

### 6. 可视化查看器

| 查看器                    | 文件                         | 功能                            |
| ------------------------- | ---------------------------- | ------------------------------- |
| JSON Viewer               | `jsonViewer.ts`              | 语法高亮、折叠展开、搜索、复制  |
| YAML Viewer               | `yamlViewer.ts`              | 语法高亮、复制内容、转换为 JSON |
| Steps Viewer              | `stepsViewer.ts`             | 时间线视图、编辑保存            |
| PID Status Viewer         | `pidStatusViewer.ts`         | 实验状态监控、自动刷新          |
| Literature Index Viewer   | `literatureIndexViewer.ts`   | 文献列表、搜索、批量操作        |
| Experiment Results Viewer | `experimentResultsViewer.ts` | 实验结果可视化                  |

### 7. API 客户端 (ApiClient)

**文件**: `src/apiClient.ts`

处理与 FastAPI 后端的 HTTP 通信：

- 支持 SSE 流式响应
- 自动重连机制
- 错误处理
- 连接状态管理

## 后端开发

### 后端项目位置

后端代码位于 `packages/agentsociety2/agentsociety2/backend/`：

```
backend/
├── app.py              # FastAPI 应用主入口
├── run.py              # 启动脚本
├── routers/            # API 路由
│   ├── agent_skills.py # Agent Skills 管理
│   ├── custom.py       # 自定义模块管理
│   ├── experiments.py  # 实验数据接口
│   ├── modules.py      # 模块信息接口
│   ├── prefill_params.py # 预填充参数
│   └── replay.py       # 回放数据接口
└── services/           # 服务层
```

### 启动后端服务

```bash
cd packages/agentsociety2
uv run python -m agentsociety2.backend.run
```

服务启动后：
- 默认地址：`http://localhost:8001`
- API 文档：`http://localhost:8001/docs`
- ReDoc：`http://localhost:8001/redoc`

### 主要 API 端点

#### 基础接口
| 端点      | 方法 | 说明             |
| --------- | ---- | ---------------- |
| `/health` | GET  | 健康检查         |
| `/docs`   | GET  | Swagger API 文档 |

#### Agent Skills 接口 (`/api/v1/agent-skills`)
| 端点           | 方法 | 说明                  |
| -------------- | ---- | --------------------- |
| `/list`        | GET  | 列出所有 Agent Skills |
| `/scan`        | POST | 扫描自定义 Skill      |
| `/import`      | POST | 从路径导入 Skill      |
| `/create`      | POST | 创建新 Skill          |
| `/upload`      | POST | 上传 zip 包导入 Skill |
| `/reload`      | POST | 热重载 Skill          |
| `/remove`      | POST | 移除自定义 Skill      |
| `/{name}/info` | GET  | 获取 Skill 详情       |

#### 模块接口 (`/api/v1/modules`)
| 端点                  | 方法 | 说明                       |
| --------------------- | ---- | -------------------------- |
| `/agent_classes`      | GET  | 获取所有 Agent 类          |
| `/env_module_classes` | GET  | 获取所有环境模块类         |
| `/all`                | GET  | 获取所有模块（一次性返回） |

#### 预填充参数接口 (`/api/v1/prefill-params`)
| 端点                         | 方法 | 说明                   |
| ---------------------------- | ---- | ---------------------- |
| `/`                          | GET  | 获取全局预填充参数     |
| `/{class_kind}/{class_name}` | GET  | 获取特定类的预填充参数 |

#### 实验数据接口 (`/api/v1/experiments`)
| 端点                                                | 方法 | 说明             |
| --------------------------------------------------- | ---- | ---------------- |
| `/{hypothesis_id}/{experiment_id}/info`             | GET  | 获取实验信息     |
| `/{hypothesis_id}/{experiment_id}/artifacts`        | GET  | 获取产出文件列表 |
| `/{hypothesis_id}/{experiment_id}/artifacts/{name}` | GET  | 获取产出文件内容 |

#### 回放数据接口 (`/api/v1/replay`)
| 端点                                                | 方法 | 说明                |
| --------------------------------------------------- | ---- | ------------------- |
| `/{hypothesis_id}/{experiment_id}/info`             | GET  | 获取实验基本信息    |
| `/{hypothesis_id}/{experiment_id}/timeline`         | GET  | 获取时间线数据      |
| `/{hypothesis_id}/{experiment_id}/agents`           | GET  | 获取所有 Agent 列表 |
| `/{hypothesis_id}/{experiment_id}/agent/{agent_id}` | GET  | 获取 Agent 详情     |

#### 自定义模块接口 (`/api/v1/custom`)
| 端点      | 方法 | 说明                   |
| --------- | ---- | ---------------------- |
| `/scan`   | POST | 扫描自定义模块         |
| `/clean`  | POST | 清理自定义模块配置     |
| `/test`   | POST | 测试自定义模块         |
| `/list`   | GET  | 列出已注册的自定义模块 |
| `/status` | GET  | 获取自定义模块状态     |

## React Webview 开发

### 技术栈

- React 18
- Ant Design 6
- @ant-design/x-markdown
- TypeScript
- Webpack

### 与扩展通信

**发送消息到扩展：**

```tsx
vscode.postMessage({
  command: 'openCommand',
  commandId: 'aiSocialScientist.openConfigPage'
});
```

**接收扩展的消息：**

```tsx
React.useEffect(() => {
  const handleMessage = (event: MessageEvent) => {
    const message = event.data;
    switch (message.command) {
      case 'initialConfig':
        // 处理消息
        break;
    }
  };
  
  window.addEventListener('message', handleMessage);
  return () => window.removeEventListener('message', handleMessage);
}, []);
```

### 主题适配

使用 `useVscodeTheme` Hook 适配 VSCode 主题：

```tsx
import { useVscodeTheme } from '../theme';

const { isDark, palette, themeConfig } = useVscodeTheme();

// 使用主题颜色
<div style={{
  background: palette.editorBackground,
  color: palette.editorForeground,
  border: `1px solid ${palette.panelBorder}`,
}}>
  {/* 内容 */}
</div>
```

### 可用主题颜色

| 变量                    | 说明         |
| ----------------------- | ------------ |
| `editorBackground`      | 编辑器背景色 |
| `editorForeground`      | 编辑器前景色 |
| `panelBorder`           | 面板边框色   |
| `linkForeground`        | 链接颜色     |
| `descriptionForeground` | 描述文字颜色 |
| `successForeground`     | 成功状态颜色 |
| `errorForeground`       | 错误状态颜色 |

## 帮助页面维护

帮助页主内容来自 ReadTheDocs，请在 `packages/agentsociety2/docs/` 修改并发布 RTD。插件内仅保留无法联网时的简短回退文案（`helpPageViewProvider.ts` 中的 `offlineHelpContent()`）。

### 添加离线回退入口

在 `offlineHelpContent()` 里增加 `command:` 链接即可：

```markdown
| 页面     | 说明         | 快捷入口                                         |
| -------- | ------------ | ------------------------------------------------ |
| 配置页面 | 配置 LLM API | [打开](command:aiSocialScientist.openConfigPage) |
```

## 打包发布

### 本地检查与打包

```bash
npm ci
npm run check            # lint + test:gateway + build
npm run package          # 产出 ai-social-scientist.vsix
# 或一步完成：
npm run package:check
```

本地安装：

```bash
code --install-extension ai-social-scientist.vsix
# 或在 Cursor / 远程窗口中：Extensions → Install from VSIX…
```

仓库根目录也可用：`make package-extension`（等同 `npm run package:check`）。

许可证与归属文件 `LICENSE`、`NOTICE`、`README.md` 会随 VSIX 一并打包；`docs/`、`test/`、`scripts/`、`.nvmrc` 等不会进入包。

### README 与远程演示素材

Marketplace 要求 README 图片最终解析为 HTTPS 地址。`package.json` 中的 `vsce.baseImagesUrl` / `baseContentUrl` 会把相对路径改写到公开 GitHub 镜像的 `main/extension/`：

- 七阶段架构图和 AI Social Scientist 主演示直接显示在 README。
- `resources/readme/` 与 `resources/walkthrough/images/gif/init-0*.gif` 保留在 Git 仓库，但通过 `.vscodeignore` 排除出 VSIX。
- 工作区初始化和 Gateway 等辅助长动图以链接形式按需打开。

**必须先把这些素材推送到公开 GitHub `main`，再构建或发布 Marketplace 版本。** 否则已打包 README 中的远程图片地址会暂时显示为破图。

### 正式发版（GitHub Release）

扩展**不单独**走 `vsce publish` 上架 Marketplace。正式发布与 Python SDK 共用标签流程（见仓库根 [CONTRIBUTING.md](../../CONTRIBUTING.md)）：

1.  bump `extension/package.json` 的 `version`
2. 在根 [CHANGELOG.md](../../CHANGELOG.md) 追加 `**extension**` 条目（本目录 [CHANGELOG.md](../CHANGELOG.md) 仅为入口说明）
3. 打标签 `agentsociety2-vX.Y.Z` 并推送
4. `agentsociety2-publish` workflow 构建 VSIX 并挂到 GitHub Release

## 代码规范

### Linting

```bash
npm run lint
```

### 注释规范

文件头部注释格式：

```typescript
/**
 * 模块说明
 *
 * 关联文件：
 * - @extension/src/xxx.ts - 说明
 *
 * 后端API：
 * - @packages/agentsociety2/agentsociety2/backend/xxx.py - 说明
 */
```

函数注释格式：

```typescript
/**
 * 函数说明
 * @param param1 参数说明
 * @returns 返回值说明
 */
```

### 命名约定

- 文件名：小写驼峰 (`configPageViewProvider.ts`)
- 类名：大写驼峰 (`ConfigPageViewProvider`)
- 接口名：大写驼峰，可带 `I` 前缀
- 常量：全大写下划线 (`DEFAULT_VALUES`)
- 私有成员：下划线前缀 (`_panel`)

## 参考资料

- [VSCode Extension API](https://code.visualstudio.com/api)
- [VSCode Extension Samples](https://github.com/Microsoft/vscode-extension-samples)
- [React Documentation](https://react.dev/)
- [Ant Design Documentation](https://ant.design/)
- [Ant Design X Documentation](https://x.ant.design/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [AgentSociety2 Documentation](../../packages/agentsociety2/README.md)
