from agentsociety.taskloader import Task
from typing import Optional
from dataclasses import dataclass


@dataclass
class BehaviorModelingTask(Task):
    target: str = ""
    user_id: str = ""
    candidate_category: Optional[str] = None
    candidate_list: Optional[list[str]] = None
    item_id: Optional[str] = None
