"""
简单 Agent 示例

这是一个基础的 Agent 示例，展示如何创建自定义 Agent（workspace 契约）。

创建完成后：
1. 将文件复制到 custom/agents/ 目录（不要放在 examples/ 中）
2. 运行 VSCode 命令 "扫描自定义模块"
3. 运行 VSCode 命令 "测试自定义模块" 验证
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from agentsociety2.agent.base import AgentBase


class SimpleAgent(AgentBase):
    """
    简单的 LLM 驱动 Agent

    这是一个用于演示的简单 Agent，展示基本的 Agent 功能。
    """

    @classmethod
    def description(cls) -> str:
        """返回 Agent 短说明。"""
        return "简单的 LLM 驱动 Agent 示例。"

    @classmethod
    def init_description(cls) -> str:
        """
        返回 Agent 初始化参数说明。
        """
        return """SimpleAgent: 简单的 LLM 驱动 Agent 示例

这是一个基础的 Agent 示例，用于演示如何创建自定义 Agent（workspace 契约）。

**Profile 字段:**
- name (str): Agent 的名称
- personality (str): Agent 的个性特征

**初始化配置示例:**
```json
{
  "id": 0,
  "profile": {
    "name": "张三",
    "personality": "友好开朗"
  },
  "config": {}
}
```
"""

    # ==================== Workspace 契约 ====================

    @classmethod
    def create(cls, workspace_path: Path, profile: dict, config: dict) -> None:
        """Create the initial agent workspace."""
        workspace_path = Path(workspace_path)
        workspace_path.mkdir(parents=True, exist_ok=True)
        (workspace_path / "config.json").write_text(
            json.dumps(config or {}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        agent_id = int(profile.get("id", 0))
        name = str(profile.get("name")) if profile.get("name") else f"Agent_{agent_id}"
        (workspace_path / "AGENT.json").write_text(
            json.dumps(
                {
                    "id": agent_id,
                    "name": name,
                    "profile": profile,
                    "step_count": 0,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    @classmethod
    async def from_workspace(
        cls, workspace_path: Path, service_proxy: Any
    ) -> "SimpleAgent":
        """Reconstruct a ready SimpleAgent from its workspace."""
        agent = cls()
        await agent.restore(workspace_path, service_proxy)
        return agent

    async def restore(self, workspace_path: Path, service_proxy: Any) -> None:
        """Restore agent state from AGENT.json (no super() — example agents
        don't use the skill/workspace runtime that AgentBase.restore binds)."""
        workspace_path = Path(workspace_path)
        meta = json.loads((workspace_path / "AGENT.json").read_text(encoding="utf-8"))
        self._id = int(meta.get("agent_id", meta.get("id", 0)))
        self._profile = meta.get("profile", {"name": meta.get("name")})
        self._name = meta.get("name") or f"Agent_{self._id}"
        self._config = {}
        self._bind_services(service_proxy)
        self._step_count = int(meta.get("step_count", 0))

    async def to_workspace(self, workspace_path: Path) -> None:
        """Write current dynamic state back to the workspace."""
        workspace_path = Path(workspace_path)
        (workspace_path / "AGENT.json").write_text(
            json.dumps(
                {
                    "id": self._id,
                    "name": self._name,
                    "profile": self.get_profile(),
                    "step_count": getattr(self, "_step_count", 0),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    async def ask(self, message: str, readonly: bool = True) -> str:
        """
        回答来自环境的问题

        :param message: 问题内容
        :param readonly: 是否只读

        :returns: 答案内容
        """
        # 构建提示词
        prompt = f"""你是一个真实的人。你的个人资料：{self.get_profile()}

问题：{message}

请根据你的个人资料和个性来回答这个问题。"""

        try:
            response = await self.acompletion([{"role": "user", "content": prompt}])
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"抱歉，我无法回答这个问题：{e!s}"

    async def step(self, tick: int, t: datetime) -> str:
        """
        执行一个仿真步骤

        :param tick: 时间刻度（秒）
        :param t: 当前仿真时间

        :returns: 步骤描述
        """
        self._step_count += 1
        # 查询环境状态
        try:
            _, observation = await self.ask_env(
                {"variables": {}}, "当前环境状态是什么？", readonly=True
            )
        except Exception as e:
            observation = f"无法获取环境状态：{e!s}"

        # 记录状态
        action = f"Agent {self.name} 观察到：{observation}，继续活动"
        return action
