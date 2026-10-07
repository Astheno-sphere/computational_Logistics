"""Experiment data models

Pydantic models for experiment configuration and execution.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ExperimentConfig(BaseModel):
    """Experiment configuration model

    Basic configuration for an experiment run.
    """

    model_config = ConfigDict(extra="allow")

    hypothesis_id: str = Field(..., description="Hypothesis ID (e.g., '1', '2')")
    experiment_id: str = Field(..., description="Experiment ID (e.g., '1', '2')")
    run_id: str = Field(default="run", description="Run ID (default: 'run')")

    agent_classes: list[str] = Field(
        default_factory=list, description="List of agent class types to use"
    )
    env_modules: list[str] = Field(
        default_factory=list, description="List of environment module types to use"
    )

    user_instructions: str | None = Field(
        None, description="Additional user instructions for configuration"
    )


class ExperimentStatus(BaseModel):
    """Experiment execution status model

    Represents the current status of a running or completed experiment.
    """

    model_config = ConfigDict(extra="allow")

    hypothesis_id: str = Field(..., description="Hypothesis ID")
    experiment_id: str = Field(..., description="Experiment ID")
    run_id: str = Field(..., description="Run ID")

    status: str = Field(
        ..., description="Status: starting, running, completed, failed, stopped"
    )
    pid: int | None = Field(None, description="Process ID if running")

    start_time: str | None = Field(None, description="Start time (ISO format)")
    end_time: str | None = Field(None, description="End time (ISO format)")

    stdout_log: str | None = Field(None, description="Path to stdout log file")
    stderr_log: str | None = Field(None, description="Path to stderr log file")

    is_running: bool = Field(
        default=False, description="Whether the process is currently running"
    )


class ExperimentInfo(BaseModel):
    """Information about an experiment

    Summary of an experiment's configuration and status.
    """

    model_config = ConfigDict(extra="allow")

    hypothesis_id: str
    experiment_id: str
    run_id: str = "run"

    has_init: bool = Field(
        default=False, description="Whether init configuration exists"
    )
    has_run: bool = Field(default=False, description="Whether run directory exists")

    status: str | None = Field(None, description="Current status")
    pid: int | None = Field(None, description="Process ID if running")
    is_running: bool = Field(default=False, description="Whether process is running")
