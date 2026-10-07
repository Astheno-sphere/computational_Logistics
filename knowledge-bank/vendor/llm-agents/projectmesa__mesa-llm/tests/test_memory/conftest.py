import pytest


@pytest.fixture
def episodic_mock_agent(mock_agent, llm_response_factory):
    """Create an episodic-memory-specific variant of the shared mock agent."""
    agent = mock_agent

    agent.llm.generate.return_value = llm_response_factory(content='{"grade": 3}')

    agent.model.steps = 100
    agent.model.events = []
    return agent
