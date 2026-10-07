# Unfour 代码 Review 报告

- 日期：2026-07-12
- 范围：当前工作区未提交改动 + 架构/安全/规模抽查
- 模式：**仅 review，未修改任何代码**

## 总体结论

未提交的改动（10 个文件，+162 / -234）是一个**方向正确、结构良好**的重构 + 测试增强：

- 把宿主应用里的 shell 级样式迁移到 `packages/app-shell`，并加守卫脚本防止宿主重复定义；
- 给共享 i18n 增加“外部资源注入”能力，配套测试与单测全绿；
- 未触碰 Rust 后端调用链、未改动 MCP 工具策略、未新增依赖。

抽查结果：包边界规则未被破坏；脱敏体系完善且有单测；检查脚本通过；i18n 测试通过；大文件检查无新增违规。**未发现阻断性 bug**，仅有若干低/中优先级的小问题。

---

## 一、未提交改动概览

| 文件 | 改动 |
| --- | --- |
| `packages/ui/src/i18n/messages.ts` | 新增并导出 `I18nResources` / `TranslationTree` 类型；`translate`/`createTranslator` 支持 `resources` 深度合并外部翻译资源 |
| `packages/ui/src/i18n/provider.tsx` | `I18nProvider` 新增 `resources` 属性，透传给 translator |
| `packages/ui/src/i18n/provider.test.tsx` | 新增 5 个用例（外部资源插值、按 locale 切换、缺失 key 回退、深度合并覆盖内置 key），共 7 passed |
| `packages/ui/src/i18n/index.ts` / `packages/ui/src/index.ts` | 重新导出新增类型 |
| `packages/app-shell/src/styles/*`（新增，未跟踪） | `index.css` / `host.css` / `animations.css`，承载原宿主 223 行 shell 样式 |
| `packages/app-shell/package.json` | 新增 `"./styles.css": "./src/styles/index.css"` 导出 |
| `apps/desktop/src/main.tsx` | 增加 `import "@unfour/app-shell/styles.css"` |
| `apps/desktop/src/styles.css` | 删除 223 行，精简为 `@import "tailwindcss"` + `@source` |
| `scripts/check-shared-tokens.mjs` | 升级为“共享样式归属”校验：校验 app-shell 样式入口、`exports["./styles.css"]`，并检测宿主重复定义 ≥3 个 app-shell 选择器 |

---

## 二、正面评价

1. **样式归属符合 `package-boundaries.md`**：shell 级样式归 `app-shell`，宿主只保留 Tailwind 入口，边界更清晰。
2. **避免平行 i18n 系统**：用“注入式 `resources`”而非在 app-shell 另写一套 provider，符合 AGENTS.md “统一共享 i18n provider”的要求。
3. **有测试与 CI 级守卫**：配套单测 + 静态检查脚本，把规范落到可执行验证。
4. **脱敏体系完善**：`unfour-core/src/redaction.rs` 统一实现，被 `unfour-diag`、`unfour-mcp/src/sanitize.rs`、`http-engine`、`ssh-engine`、`database-engine`、`local-storage` 复用，且有覆盖 JSON body / URL query / 连接串 / 终端输出的单测。
5. **验证全绿**：`check-shared-tokens` OK、`check-large-files` 0 blocking、i18n 测试 7 passed。

---

## 三、问题清单（按严重度）

### 中优先级

**1. 外部 `resources` 可覆盖内置 product 级 key（治理/可维护性）**
- `mergeTranslationTrees` 允许外部资源覆盖任意内置 key，测试里 `app.nav.database` 被覆盖成 `"Host Database"`。
- 桌面宿主是可信的，风险有限；但这意味着宿主能**静默改变产品级导航文案**。若未来引入第三方/插件资源，存在误改核心文案风险。
- 建议：约定 `resources` 只允许新增 `host.*` 等宿主命名空间；或在 deep-merge 时对内置 `app.*` key 做“保留、不覆盖”；至少在文档中写明允许覆盖的边界。

### 低优先级

**2. `resources` 对象引用稳定性（性能）**
- `I18nProvider` 的 `t` 依赖 `[locale, resources]`。若宿主在 JSX 中以字面量传入 `resources`，每次渲染都会生成新引用，导致 `t` 每次重建。
- 影响有限（桌面入口只在根渲染一次），但作为公共组件应更健壮：建议在调用处 `useMemo` 固定 `resources`，或在 provider 内部按内容做稳定化。

**3. CSS 引入顺序（潜在级联差异）**
- `main.tsx` 顺序为 `ui → app-shell → 宿主(tailwind preflight)`。重构前 223 行与 tailwind 同文件、tailwind 在前；现在 app-shell 的 class 样式在 tailwind `@import` 之前。
- class 选择器特异性高于 preflight 元素选择器，一般不会被覆盖；`body` 级规则（`app-shell` 里的 `body{min-height:680px;overflow:hidden}`）与 preflight 同特异性且在前，理论上 preflight 的 `body{margin:0}` 会晚于它——两者 margin 均为 0，无实际差异。
- 建议：在浏览器中回归确认 shell 布局（状态栏、侧边栏、滚动条、dialog 遮罩）与重构前视觉一致。

**4. `check-shared-tokens.mjs` 的 `APP_SHELL_SELECTORS` 为硬编码列表**
- 守卫依赖手工维护的选择器清单。app-shell 后续新增 `.xxx` 选择器而列表未同步时，宿主复制该新选择器不会被检出。
- 建议：从 `packages/app-shell/src/styles` 自动提取选择器集合，降低维护漂移。

### 信息 / 非问题

**5. 大文件均为“已基线豁免”**
- `database.rs`(3544)、`ssh.rs`(2402)、`command-bus/lib.rs`(1726)、`api_client.rs`(1722)、`DatabasePage.tsx`(1686)、`mcp/tools/api.rs`(1447) 等均已登记在 `scripts/large-files-baseline.json`，本次**未引入新的超阈值文件**，无阻断项。
- 建议把它们列入后续拆分 backlog（脚本已给出建议拆分边界：driver / query-safety / table-operation、session-lifecycle / transport / persistence / diagnostics 等）。

**6. 变更集最小**
- 未改 Rust 后端调用链、未改 MCP 工具策略、未新增依赖（`app-shell/package.json` 仅改 exports）。符合 AGENTS.md “最小变更集”原则。

---

## 四、建议人工复核点

- app-shell 注入的 `host.*` 命名空间资源实际内容，确认宿主文案确实走 i18n 而非硬编码。
- 浏览器回归 shell 布局，确认样式迁移后视觉一致（见第 3 条）。
- `resources` 覆盖内置 key 的策略是否需收紧（见第 1 条）。

---

## 五、验证命令与结果

| 命令 | 结果 |
| --- | --- |
| `node scripts/check-shared-tokens.mjs` | OK — 无宿主重定义共享 token |
| `node scripts/check-large-files.mjs` | 0 blocking — 均为基线豁免文件 |
| `npx vitest run packages/ui/src/i18n/provider.test.tsx` | 7 passed |
| 边界 grep（feature→app-shell / ui→feature / command-client→feature / feature→feature / feature→workspace-local） | 均无违规 |
| `app-shell/src/styles` 是否定义 `--u-`/`--panel-`/`--app-` token | 否（仅消费共享 token） |

**未执行**：`pnpm run build` 全量构建、`cargo`/Rust 编译与测试。
原因：本次未改动 Rust 后端；全量构建与 Rust 编译耗时且非必要的 review 动作。如需补跑，可单独执行。
