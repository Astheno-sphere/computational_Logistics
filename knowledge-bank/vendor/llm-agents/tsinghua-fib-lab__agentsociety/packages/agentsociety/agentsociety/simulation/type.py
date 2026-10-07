import enum
from dataclasses import dataclass
from typing import Any

__all__ = ["ExperimentStatus", "Logs"]


class ExperimentStatus(enum.IntEnum):
    """Experiment status"""

    NOT_STARTED = 0  # The experiment is not started
    RUNNING = 1  # The experiment is running
    FINISHED = 2  #  The experiment is finished
    ERROR = 3  # The experiment has error and stopped


@dataclass
class Logs:
    llm_log: list[Any]
    simulator_log: list[Any]
    agent_time_log: list[Any]

    def append(self, other: "Logs"):
        self.llm_log += other.llm_log
        self.simulator_log += other.simulator_log
        self.agent_time_log += other.agent_time_log
