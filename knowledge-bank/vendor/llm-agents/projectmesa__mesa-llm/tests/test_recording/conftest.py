import json
import pickle
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from mesa_llm.recording.simulation_recorder import SimulationRecorder


@pytest.fixture
def temp_dir():
    """Create a temporary directory for recording test outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_model():
    """Create a mock Mesa model for recording tests."""
    model = Mock()
    model.__class__.__name__ = "TestModel"
    model.steps = 0
    model.agents = []
    return model


@pytest.fixture
def recorder(mock_model, temp_dir):
    """Create a SimulationRecorder instance for recording tests."""
    return SimulationRecorder(
        model=mock_model,
        output_dir=str(temp_dir),
        record_state_changes=True,
        auto_save_interval=None,
    )


@pytest.fixture
def sample_recording_data():
    """Create sample recording data for agent analysis tests."""
    return {
        "metadata": {
            "simulation_id": "test123",
            "start_time": "2024-01-01T10:00:00Z",
            "end_time": "2024-01-01T10:05:00Z",
            "model_class": "TestModel",
            "total_steps": 5,
            "total_events": 7,
            "total_agents": 2,
            "duration_minutes": 5.0,
            "completion_status": "completed",
        },
        "events": [
            {
                "event_id": "test123_000001",
                "timestamp": "2024-01-01T10:00:01Z",
                "step": 1,
                "agent_id": 123,
                "event_type": "observation",
                "content": {
                    "self_state": {
                        "location": [1, 2],
                        "internal_state": ["happy", "energetic"],
                    }
                },
                "metadata": {"source": "agent"},
            },
            {
                "event_id": "test123_000002",
                "timestamp": "2024-01-01T10:00:02Z",
                "step": 1,
                "agent_id": 123,
                "event_type": "plan",
                "content": {
                    "plan_content": {"content": "I will move north to explore"}
                },
                "metadata": {"source": "agent"},
            },
            {
                "event_id": "test123_000003",
                "timestamp": "2024-01-01T10:00:03Z",
                "step": 1,
                "agent_id": 123,
                "event_type": "action",
                "content": {"action_type": "move", "direction": "north"},
                "metadata": {"source": "agent"},
            },
            {
                "event_id": "test123_000004",
                "timestamp": "2024-01-01T10:00:04Z",
                "step": 1,
                "agent_id": 123,
                "event_type": "message",
                "content": {"message": "Hello, agent 456!", "recipient_ids": [456]},
                "metadata": {"source": "agent"},
            },
            {
                "event_id": "test123_000005",
                "timestamp": "2024-01-01T10:00:05Z",
                "step": 2,
                "agent_id": 456,
                "event_type": "message",
                "content": {
                    "message": "Hello back, agent 123!",
                    "recipient_ids": [123],
                },
                "metadata": {"source": "agent"},
            },
            {
                "event_id": "test123_000006",
                "timestamp": "2024-01-01T10:00:06Z",
                "step": 2,
                "agent_id": 456,
                "event_type": "observation",
                "content": {"data": "I see agent 123 nearby"},
                "metadata": {"source": "agent"},
            },
            {
                "event_id": "test123_000007",
                "timestamp": "2024-01-01T10:00:07Z",
                "step": 2,
                "agent_id": 456,
                "event_type": "state_change",
                "content": {"position": [2, 3], "energy": 95},
                "metadata": {"source": "agent"},
            },
        ],
        "agent_summaries": {
            "123": {
                "total_events": 4,
                "event_types": ["observation", "plan", "action", "message"],
                "active_steps": [1],
                "first_event": "2024-01-01T10:00:01Z",
                "last_event": "2024-01-01T10:00:04Z",
            },
            "456": {
                "total_events": 3,
                "event_types": ["message", "observation", "state_change"],
                "active_steps": [2],
                "first_event": "2024-01-01T10:00:05Z",
                "last_event": "2024-01-01T10:00:07Z",
            },
        },
    }


@pytest.fixture
def temp_recording_file(sample_recording_data):
    """Create temporary recording files for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = Path(tmpdir) / "test_recording.json"
        with open(json_path, "w") as f:
            json.dump(sample_recording_data, f)

        pkl_path = Path(tmpdir) / "test_recording.pkl"
        with open(pkl_path, "wb") as f:
            pickle.dump(sample_recording_data, f)

        yield json_path, pkl_path
