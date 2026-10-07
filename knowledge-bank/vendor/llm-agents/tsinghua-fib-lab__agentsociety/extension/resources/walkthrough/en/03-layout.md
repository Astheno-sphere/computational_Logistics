## Meet the Layout

Click the **AI Social Scientist** icon in the activity bar. Numbered regions match the red boxes:

![Layout overview with numbered regions](../images/vscode-layout-overview.png)

| # | Name | What it does |
|---|------|--------------|
| **1** | **Activity Bar** | Switch Explorer, Search, Git, Extensions, AI Social Scientist, and other views. |
| **2** | **AI Social Scientist sidebar** | Project tree: AI Chat, skill management (Agent / Claude / Marketplace), environments & agents, research topic (`TOPIC.md`), literature, user data, datasets, custom modules. |
| **3** | **Editor** | Config pages, Markdown, experiment files, Claude Code, replay, and more; idle view shows useful shortcuts. |
| **4** | **AI Chat** | Right-side chat: pick Agent / model, describe a task, attach file context. |
| **5** | **Status Bar** | Git, diagnostics, backend port (e.g. `8001`), active model; click to manage backend and gateway. |
| **6** | **Accounts / Settings** | Bottom of the activity bar: account sync and VS Code settings, keybindings, themes. |
| **7** | **Title bar / breadcrumbs** | Current path and layout controls; quick access to chat or panel layout. |

### A human-steered research workspace

The interface implements the paper's **Interactive Research Environment (IRE)**: the researcher keeps high-level control over questions, assumptions, interventions, and interpretation, while the AI Social Scientist carries out lower-level operations across files, agents, artifacts, simulation, and experiment execution.

![Human-steered IRE: high-level researcher guidance and low-level AI Social Scientist execution](../images/agentsociety2-human-steered-ire.png)

*Conceptual architecture adapted from Figure 4 of the [AgentSociety 2 paper](https://arxiv.org/abs/2607.11895).*

### Sidebar actions

| Button | Function |
|--------|----------|
| 🔄 Refresh | Reload the project tree |
| 🧩 Skills | Open skill management |
| ⬇️ Export | Pack this research project to send to someone else |
| ⬆️ Import | Open a project archive someone shared with you |
| ⚙️ Config | Open LLM / API settings |
| 📖 Help | Open the user guide |

### Typical folders

```
workspace-root/
├── TOPIC.md
├── papers/          # Literature
├── datasets/        # Datasets
├── user_data/       # User data
├── custom/          # Custom modules and agent skills
├── .claude/skills/  # Claude / Codex skills
├── hypothesis_*/    # Hypotheses and experiments
├── presentation/    # Analysis reports and assets
├── synthesis/       # Cross-hypothesis synthesis
└── paper/           # Paper workspace
```

[Open Sidebar](command:projectStructureView.focus)
