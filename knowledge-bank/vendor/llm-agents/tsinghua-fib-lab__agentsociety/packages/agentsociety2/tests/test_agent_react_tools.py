from datetime import datetime
from pathlib import Path

from agentsociety2.agent.base.agent import AgentBase


class _DummySkillRuntime:
    def activate_skill(self, skill_name: str):
        return False, "", ""


class _DummyAgent(AgentBase):
    @classmethod
    def create(cls, workspace_path: Path, profile: dict, config: dict) -> None:
        raise NotImplementedError

    @classmethod
    async def from_workspace(cls, workspace_path: Path, service_proxy):
        raise NotImplementedError

    def to_workspace(self) -> dict:
        raise NotImplementedError

    async def ask(self, question: str, readonly: bool = True) -> str:
        raise NotImplementedError

    async def step(self, tick: int, t: datetime) -> str:
        raise NotImplementedError


async def test_activate_skill_failure_reports_reason():
    agent = _DummyAgent()
    agent.skill_runtime = _DummySkillRuntime()

    result = await agent.dispatch_react_tool(
        "activate_skill",
        {"skill_name": "does-not-exist"},
    )

    assert result.ok is False
    assert result.observation
    assert "does-not-exist" in result.observation
    assert result.data["error"]
