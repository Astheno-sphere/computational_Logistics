# AgentSociety 2 文档指南

AgentSociety 2 的 ReadTheDocs 站点使用 **Sphinx + Furo + MyST** 构建，默认语言为中文，并通过 Sphinx i18n 维护英文翻译。它不是 Google Docs 风格的文档站；视觉和导航均以 Sphinx/Furo 主题为准。

本仓库有多套 ReadTheDocs 站点。仓库根目录的 `.readthedocs.yaml` 保留给 `packages/agentsociety/docs/` 旧版文档；AgentSociety 2 的独立配置放在 `packages/agentsociety2/.readthedocs.yaml`，构建入口为 `packages/agentsociety2/docs/conf.py`。在 ReadTheDocs 的 AgentSociety 2 项目设置中，应把 config file 指向这份包内配置，避免影响旧站点。

## 文档结构

```text
packages/agentsociety2/docs/
├── conf.py              # Sphinx 配置文件
├── index.rst            # 主文档入口（中文，默认语言）
├── locale/              # 国际化翻译文件
│   ├── en/              # 英文翻译
│       └── LC_MESSAGES/
│           ├── index.po
│           └── ...
├── _static/             # 静态资源（图片、CSS等）
├── _templates/          # Sphinx 模板
├── _build/              # 构建输出目录
├── requirements.txt     # Python 依赖
├── agents.rst           # Agent / PersonAgent / create-agent 技能说明
├── agent_skills.rst     # PersonAgent skills-first 架构
├── skills.rst           # 研究技能、实验/分析/文献检索工作流
├── api/                 # API 参考
└── ...
```

## 支持的语言

- **中文（zh）**: 默认语言，主要文档语言
- **英文（en）**: 翻译语言

## 文档编写工作流

### 1. 编写新文档

所有新文档应该用中文编写，使用 reStructuredText (.rst) 或 Markdown (.md) 格式：

```bash
# 在 v2 文档目录下创建新文档
packages/agentsociety2/docs/new-feature.rst
```

### 2. 提取翻译文本

在编写或修改文档后，运行以下命令提取需要翻译的文本：

```bash
# 推荐在 v2 文档目录执行
cd packages/agentsociety2/docs
make gettext
```

这会在 `packages/agentsociety2/docs/_build/gettext/` 目录下生成 `.pot` 文件。

### 3. 更新翻译文件

更新或创建翻译文件：

```bash
cd packages/agentsociety2/docs
make update-po
```

这会在 `packages/agentsociety2/docs/locale/en/LC_MESSAGES/` 目录下创建或更新 `.po` 文件。

### 4. 翻译文档

编辑 `.po` 文件进行翻译：

```bash
# 编辑英文翻译
vim packages/agentsociety2/docs/locale/en/LC_MESSAGES/index.po
```

示例 `.po` 文件内容：

```po
# Chinese translations for AgentSociety project.
msgid ""
msgstr ""
"Project-Id-Version: AgentSociety 2 2.3.0\n"
"Language: en\n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=UTF-8\n"

#: ../../index.rst:4
msgid "AgentSociety 2"
msgstr "AgentSociety 2"

#: ../../index.rst:6
msgid "**AgentSociety 2** 是一个现代化的、LLM 原生的智能体模拟平台..."
msgstr "**AgentSociety 2** is a modern, LLM-native agent simulation platform..."
```

### 5. 构建文档

构建不同语言版本的文档：

```bash
cd packages/agentsociety2/docs

# 构建中文文档（默认）
make html
# 或
make html-zh

# 构建英文文档
make html-en

# 构建所有语言版本
make html-all
```

构建的文档将保存在：
- 中文版本：`packages/agentsociety2/docs/_build/html/zh/`
- 英文版本：`packages/agentsociety2/docs/_build/html/en/`

## Makefile 命令说明

| 命令 | 描述 |
|------|------|
| `make help` | 显示帮助信息 |
| `make gettext` | 提取可翻译的文本 |
| `make update-po` | 更新翻译文件 |
| `make build-po` | 编译翻译文件 |
| `make html` | 构建中文文档（默认） |
| `make html-zh` | 构建中文文档 |
| `make html-en` | 构建英文文档 |
| `make html-all` | 构建所有语言版本 |
| `make clean` | 清理构建文件 |

## ReadTheDocs 配置

项目已配置为在 ReadTheDocs 上构建 AgentSociety 2 文档：

1. **主项目**：`agentsociety2.readthedocs.io`，中文文档（默认）
2. **英文翻译**：如需英文站点，可在 ReadTheDocs 上设置 translation 项目

`packages/agentsociety2/.readthedocs.yaml` 的关键配置：

```yaml
python:
  install:
    - requirements: docs/requirements.txt
    - method: pip
      path: .
      extra_requirements:
        - docs

sphinx:
  configuration: docs/conf.py
```

### ReadTheDocs 多语言设置步骤

1. 在 ReadTheDocs 上创建主项目（中文）
2. 在项目设置中添加翻译：
   - 进入项目管理界面
   - 选择 "翻译" 或 "Translations"
   - 添加英文翻译项目
3. ReadTheDocs 会自动为每种语言创建单独的子域名：
   - 中文：`https://agentsociety2.readthedocs.io/zh/latest/`
   - 英文：`https://agentsociety2.readthedocs.io/en/latest/`

## 文档编写规范

### 1. 文件命名

- 使用小写字母和连字符
- 中文文档直接使用描述性名称
- 例：`quickstart.rst`, `configuration-guide.rst`

### 2. 图片和静态资源

- 所有图片放在 `packages/agentsociety2/docs/_static/` 目录下
- 使用相对路径引用：`_static/image.png`
- 提供替代文本（alt text）

### 3. MyST Markdown 编写规范

#### 3.1 基本语法

MyST (Markedly Structured Text) 是 Sphinx 的 Markdown 扩展，支持标准 Markdown 语法以及 Sphinx 的特殊功能。

**文件扩展名**：使用 `.md` 扩展名

**基本结构**：
```markdown
---
title: 文档标题
description: 文档描述
---

# 主标题

## 二级标题

### 三级标题

正文内容...
```

#### 3.2 标题和层级

- 使用 `#` 创建标题，最多支持 6 级标题
- 标题层级要合理，避免跳过层级
- 每个文档应该只有一个一级标题

```markdown
# 一级标题（文档标题）
## 二级标题（章节）
### 三级标题（小节）
#### 四级标题（子小节）
```

#### 3.3 链接和引用

**内部链接**：
```markdown
[链接文本](path/to/file.md)
[链接文本](path/to/file.md#section-id)
```

**外部链接**：
```markdown
[链接文本](https://example.com)
```

**脚注**：
```markdown
这里是一个脚注[^1]。

[^1]: 这是脚注的内容。
```

#### 3.4 代码块

**行内代码**：
```markdown
使用 `code` 标记行内代码
```

**代码块**：
````markdown
```python
def hello_world():
    print("Hello, World!")
```
````

**语法高亮**：支持多种编程语言
````markdown
```bash
# 命令行示例
pip install myst-parser
```

```yaml
# 配置文件示例
version: "3.8"
extensions:
  - myst_parser
```
````

#### 3.5 表格

**简单表格**：
```markdown
| 列1 | 列2 | 列3 |
|-----|-----|-----|
| 内容1 | 内容2 | 内容3 |
| 内容4 | 内容5 | 内容6 |
```

**对齐表格**：
```markdown
| 左对齐 | 居中 | 右对齐 |
|:-------|:----:|-------:|
| 内容   | 内容 | 内容   |
```

#### 3.6 列表

**无序列表**：
```markdown
- 项目1
- 项目2
  - 子项目2.1
  - 子项目2.2
- 项目3
```

**有序列表**：
```markdown
1. 第一步
2. 第二步
   1. 子步骤2.1
   2. 子步骤2.2
3. 第三步
```

#### 3.7 引用和警告

**引用块**：
```markdown
> 这是一个引用块
> 可以包含多行内容
```

**警告和提示**：
```markdown
```{warning}
这是一个警告信息
```

```{note}
这是一个提示信息
```

```{tip}
这是一个技巧提示
```
```

#### 3.8 数学公式

**行内公式**：
```markdown
行内公式：$E = mc^2$
```

**块级公式**：
```markdown
$$
\int_{-\infty}^{\infty} e^{-x^2} dx = \sqrt{\pi}
$$
```

#### 3.9 图片

**基本图片**：
```markdown
![图片描述](_static/image.png)
```

**带标题的图片**：
```markdown
```{figure} _static/image.png
:name: fig-example
:alt: 图片描述

图片标题
```
```

#### 3.10 交叉引用

**引用其他文档**：
```markdown
{ref}`target-document`
{ref}`target-document#section`
```

**引用图片**：
```markdown
{numref}`fig-example`
```

**引用代码块**：
```markdown
{code}`example-code-block`
```

#### 3.11 最佳实践

1. **一致性**：保持文档风格和格式的一致性
2. **可读性**：使用清晰的标题层级和段落结构
3. **链接检查**：确保所有链接都是有效的
4. **图片优化**：使用适当大小的图片，提供替代文本
5. **代码示例**：提供完整、可运行的代码示例
6. **国际化**：为所有用户可见的文本提供翻译

#### 3.12 常见错误避免

- 避免使用 HTML 标签（除非必要）
- 避免过度嵌套的列表
- 避免过长的行（建议不超过 80 字符）
- 避免使用绝对路径引用文件
- 避免在代码块中使用制表符（使用空格）

## 常见问题

### 1. 翻译文件更新问题

如果翻译文件没有正确更新，尝试：

```bash
cd packages/agentsociety2/docs
make clean-docs
make gettext
make update-po
```

### 2. 构建错误

检查文档语法：

```bash
cd packages/agentsociety2/docs
sphinx-build -b dummy . _build/dummy
```

### 3. 图片显示问题

确保图片路径正确且文件存在：

```bash
ls packages/agentsociety2/docs/_static/
```

## 贡献指南

1. **编写新文档**：使用中文编写，遵循现有文档结构
2. **提交翻译**：英文翻译通过编辑 `.po` 文件完成
3. **测试构建**：提交前确保文档能正确构建
4. **更新索引**：新文档需要添加到相应的 `index.md` 文件中

## 技术支持

如有问题，请：

1. 检查本文档的常见问题部分
2. 查看 [Sphinx 官方文档](https://www.sphinx-doc.org/)
3. 查看 [sphinx-intl 文档](https://sphinx-intl.readthedocs.io/)
4. 联系文档维护团队
