from unittest.mock import AsyncMock, patch

import pytest

from mesa_llm.memory.lt_memory import LongTermMemory
from mesa_llm.memory.memory import MemoryEntry


class TestLTMemory:
    """Test the Memory class core functionality"""

    def test_memory_initialization(self, mock_agent):
        """Test Memory class initialization with defaults and custom values"""
        memory = LongTermMemory(
            agent=mock_agent,
            llm_model="provider/test_model",
        )

        assert memory.agent == mock_agent
        assert memory.long_term_memory == ""
        assert memory.llm.system_prompt is not None

    def test_update_long_term_memory(self, mock_agent, mock_llm, llm_response_factory):
        """Check that long_term_memory gets the actual text, not the whole response object."""
        mock_llm.generate.return_value = llm_response_factory(
            "Updated long-term memory"
        )

        memory = LongTermMemory(agent=mock_agent, llm_model="provider/test_model")
        memory.llm = mock_llm
        memory.long_term_memory = "Previous memory"

        memory.buffer = MemoryEntry(
            agent=mock_agent,
            content={"message": "Test message"},
            step=1,
        )

        memory._update_long_term_memory()

        call_args = mock_llm.generate.call_args[0][0]
        assert "new memory entry" in call_args
        assert "Long term memory" in call_args

        assert isinstance(memory.long_term_memory, str)
        assert memory.long_term_memory == "Updated long-term memory"

    def test_long_term_memory_stores_string_not_response_object(
        self, mock_agent, mock_llm, llm_response_factory
    ):
        """Make sure long_term_memory is always a plain string.
        Before this fix, it was storing the whole LLM response object instead
        of just the text — which broke any prompt that used the memory.
        """
        mock_llm.generate.return_value = llm_response_factory(
            "This is the summary text"
        )

        memory = LongTermMemory(agent=mock_agent, llm_model="provider/test_model")
        memory.llm = mock_llm
        memory.buffer = MemoryEntry(
            agent=mock_agent, content={"observation": "test"}, step=1
        )

        memory._update_long_term_memory()

        assert isinstance(memory.long_term_memory, str), (
            "long_term_memory must be a string, not a ModelResponse object"
        )
        assert memory.long_term_memory == "This is the summary text"

    # process step test
    def test_process_step(self, mock_agent, llm_response_factory):
        """Test process_step functionality"""
        memory = LongTermMemory(agent=mock_agent, llm_model="provider/test_model")

        # Add some content
        memory.add_to_memory("observation", {"content": "Test observation"})
        memory.add_to_memory("plan", {"content": "Test plan"})

        # Process the step
        with (
            patch("rich.console.Console"),
            patch.object(
                memory.llm,
                "generate",
                return_value=llm_response_factory("mocked summary"),
            ),
        ):
            memory.process_step(pre_step=True)
            assert isinstance(memory.buffer, MemoryEntry)

            memory.process_step(pre_step=False)
            assert memory.long_term_memory == "mocked summary"

    # format memories test
    def test_format_long_term(self, mock_agent):
        """Test formatting long-term memory"""
        memory = LongTermMemory(agent=mock_agent, llm_model="provider/test_model")
        memory.long_term_memory = "Long-term summary"

        assert memory.format_long_term() == "Long-term summary"

    @pytest.mark.asyncio
    async def test_aupdate_long_term_memory(
        self, mock_agent, mock_llm, llm_response_factory
    ):
        """Same as above but for the async version — makes sure it also
        saves just the text, not the whole response object."""
        mock_llm.agenerate = AsyncMock(
            return_value=llm_response_factory("async summary")
        )

        memory = LongTermMemory(agent=mock_agent, llm_model="provider/test_model")
        memory.llm = mock_llm
        memory.buffer = "buffer"

        await memory._aupdate_long_term_memory()

        mock_llm.agenerate.assert_called_once()
        assert isinstance(memory.long_term_memory, str)
        assert memory.long_term_memory == "async summary"

    @pytest.mark.asyncio
    async def test_aprocess_step(self, mock_agent, llm_response_factory):
        """
        Test asynchronous aprocess_step functionality

        This test is performed in 2 parts ,
            - If pre_step = True then a new memory entry is created and this must be verified.
            - If pre_step = False then a according to the aprocess_step function the previous content is restored and this is set to as the new memory entry
              the check verifies this behavior.
        """
        memory = LongTermMemory(agent=mock_agent, llm_model="provider/test_model")

        # populate with content
        memory.add_to_memory("observation", {"content": "Test observation"})
        memory.add_to_memory("plan", {"content": "Test plan"})

        # Mock async LLM call
        memory.llm.agenerate = AsyncMock(
            return_value=llm_response_factory("mocked async summary")
        )

        with patch("rich.console.Console"):
            await memory.aprocess_step(pre_step=True)
            assert isinstance(memory.buffer, MemoryEntry)
            assert memory.buffer.step is None

            await memory.aprocess_step(pre_step=False)
            assert memory.long_term_memory == "mocked async summary"
            assert memory.step_content == {}
            assert memory.buffer.step is not None
