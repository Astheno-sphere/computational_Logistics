"""Tests for the double pre_step/post_step bug (issue #222).

When a subclass defines only step() and is executed via astep() during
parallel stepping, pre_step/post_step should be called exactly once —
not twice.
"""

import pytest
from mesa.model import Model

from mesa_llm.llm_agent import LLMAgent
from mesa_llm.memory.memory import Memory
from mesa_llm.memory.st_lt_memory import STLTMemory


class DummyModel(Model):
    def __init__(self):
        super().__init__(seed=42)


class CallCountMemory(Memory):
    """Memory that counts pre/post step calls instead of doing real work."""

    def __init__(self, agent):
        # Skip ModuleLLM initialization — no LLM needed for counting
        self.agent = agent
        self.display = False
        self.step_content = {}
        self.last_observation = {}

        self.pre_step_count = 0
        self.post_step_count = 0

    def process_step(self, pre_step=False):
        if pre_step:
            self.pre_step_count += 1
        else:
            self.post_step_count += 1

    async def aprocess_step(self, pre_step=False):
        if pre_step:
            self.pre_step_count += 1
        else:
            self.post_step_count += 1

    def get_prompt_ready(self):
        return ""

    def get_communication_history(self):
        return ""


class StepOnlyAgent(LLMAgent):
    """Agent that defines only step(), no astep()."""

    def __init__(self, model):
        super().__init__(
            model, reasoning=_DummyReasoning, llm_model="gemini/gemini-2.0-flash"
        )
        # Replace memory with our counting version
        self.memory = CallCountMemory(self)
        self.user_step_called = False

    def step(self):
        self.user_step_called = True


class AsyncOnlyAgent(LLMAgent):
    """Agent that defines only astep(), no step()."""

    def __init__(self, model):
        super().__init__(
            model, reasoning=_DummyReasoning, llm_model="gemini/gemini-2.0-flash"
        )
        self.memory = CallCountMemory(self)
        self.user_astep_called = False

    async def astep(self):
        self.user_astep_called = True


class BothAgent(LLMAgent):
    """Agent that defines both step() and astep()."""

    def __init__(self, model):
        super().__init__(
            model, reasoning=_DummyReasoning, llm_model="gemini/gemini-2.0-flash"
        )
        self.memory = CallCountMemory(self)
        self.user_step_called = False
        self.user_astep_called = False

    def step(self):
        self.user_step_called = True

    async def astep(self):
        self.user_astep_called = True


class _DummyReasoning:
    """Minimal reasoning stub — no LLM calls needed."""

    def __init__(self, agent):
        self.agent = agent

    def plan(self, **kwargs):
        pass

    async def aplan(self, **kwargs):
        pass


@pytest.mark.asyncio
async def test_astep_calls_pre_post_once_for_step_only_agent():
    """Core regression test for issue #222."""
    m = DummyModel()
    agent = StepOnlyAgent(m)

    await agent.astep()

    assert agent.user_step_called
    assert agent.memory.pre_step_count == 1, (
        f"pre_step called {agent.memory.pre_step_count} times, expected 1"
    )
    assert agent.memory.post_step_count == 1, (
        f"post_step called {agent.memory.post_step_count} times, expected 1"
    )


@pytest.mark.asyncio
async def test_astep_calls_pre_post_once_for_async_only_agent():
    m = DummyModel()
    agent = AsyncOnlyAgent(m)

    await agent.astep()

    assert agent.user_astep_called
    assert agent.memory.pre_step_count == 1
    assert agent.memory.post_step_count == 1


@pytest.mark.asyncio
async def test_astep_calls_pre_post_once_for_both_agent():
    m = DummyModel()
    agent = BothAgent(m)

    await agent.astep()

    assert agent.user_astep_called
    assert agent.memory.pre_step_count == 1
    assert agent.memory.post_step_count == 1


def test_sync_step_calls_pre_post_once():
    """Direct step() call should also have exactly one pre/post."""
    m = DummyModel()
    agent = StepOnlyAgent(m)

    agent.step()

    assert agent.user_step_called
    assert agent.memory.pre_step_count == 1
    assert agent.memory.post_step_count == 1


@pytest.mark.asyncio
async def test_multiple_asteps_no_accumulation():
    """After N astep() calls, counts should be exactly N, not 2N."""
    m = DummyModel()
    agent = StepOnlyAgent(m)

    for _ in range(5):
        agent.user_step_called = False
        await agent.astep()
        assert agent.user_step_called

    assert agent.memory.pre_step_count == 5
    assert agent.memory.post_step_count == 5


@pytest.mark.asyncio
async def test_no_orphaned_entries_with_default_stlt_memory():
    """With real STLTMemory, no entries with step=None should persist."""
    m = DummyModel()
    # Use a step-only agent but keep the default STLTMemory
    # We need a subclass that doesn't replace memory
    agent = StepOnlyAgent(m)
    # Restore default STLTMemory for this test
    agent.memory = STLTMemory(
        agent=agent,
        short_term_capacity=5,
        consolidation_capacity=2,
        llm_model="gemini/gemini-2.0-flash",
    )

    # Simulate 3 astep() calls
    for _ in range(3):
        await agent.astep()

    orphaned = [e for e in agent.memory.short_term_memory if e.step is None]
    assert len(orphaned) == 0, f"Found {len(orphaned)} orphaned entries with step=None"
