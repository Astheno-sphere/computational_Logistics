"""
TaskLoader module for loading and managing tasks from JSON/JSONL files.

This module provides a PyTorch DataLoader-like interface for task management,
supporting task loading, extraction, and state tracking.
"""

import json
import os
from typing import Any, List, Optional, Union
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from ..logger import get_logger


class TaskStatus(Enum):
    """Task execution status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"


@dataclass
class Task:
    """
    Represents a single task with context, status, and results.
    
    - **Description**:
        A task object that contains execution context, status tracking,
        ground truth data, and result storage capabilities.
    
    - **Args**:
        - `ground_truth` (Any): Ground truth data for the task
        - `task_id` (int): Unique identifier for the task
        - `status` (TaskStatus): Current execution status of the task
        - `result` (Optional[Any]): Execution result of the task
        - `assigned_agent_id` (Optional[int]): ID of the agent assigned to this task
    """
    
    ground_truth: Any
    task_id: int
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None
    assigned_agent_id: Optional[int] = None

    def get_task_context(self) -> dict[str, Any]:
        """
        Returns the task information excluding basic fields.
        
        - **Description**:
            Returns all task information except for ground_truth, task_id, status, and result.
            This method dynamically includes all fields from the task object and its subclasses.
        
        - **Returns**:
            - `dict[str, Any]`: Task information dictionary
        """
        # Get all fields from the dataclass
        task_info = {}
        
        # Get all fields from the dataclass, excluding the basic ones
        excluded_fields = {'ground_truth', 'task_id', 'status', 'result'}
        
        # Use dataclasses.fields to get all fields dynamically
        from dataclasses import fields
        
        for field in fields(self):
            field_name = field.name
            if field_name not in excluded_fields:
                field_value = getattr(self, field_name)
                task_info[field_name] = field_value
        
        return task_info
    
    def set_result(self, result: Any) -> None:
        """
        Sets the task result and marks it as completed.
        
        - **Description**:
            Updates the task result and automatically changes status to completed.
        
        - **Args**:
            - `result` (Any): The execution result to store
        """
        self.result = result
        self.status = TaskStatus.COMPLETED
    
    def set_running(self) -> None:
        """
        Marks the task as running.
        
        - **Description**:
            Changes the task status to running when execution begins.
        """
        self.status = TaskStatus.RUNNING
    
    def reset(self) -> None:
        """
        Resets the task to pending status and clears results.
        
        - **Description**:
            Resets the task to its initial state for re-execution.
        """
        self.status = TaskStatus.PENDING
        self.result = None

    def assign_to_agent(self, agent_id: int) -> None:
        """
        Assigns this task to a specific agent.
        
        - **Description**:
            Sets the assigned_agent_id field to track which agent is responsible
            for executing this task.
        
        - **Args**:
            - `agent_id` (int): The ID of the agent assigned to this task
        """
        self.assigned_agent_id = agent_id


class TaskLoader:
    """
    A PyTorch DataLoader-like class for loading and managing tasks from JSON/JSONL files.
    
    - **Description**:
        Loads tasks from JSON or JSONL files and provides methods to extract
        tasks for execution. Supports task state management and result tracking.
    
    - **Args**:
        - `file_path` (str): Path to the JSON/JSONL file containing tasks
        - `shuffle` (bool): Whether to shuffle tasks when loading
        - `max_tasks` (Optional[int]): Maximum number of tasks to load
    """
    
    def __init__(self, task_type: type[Task], file_path: str, shuffle: bool = False, max_tasks: Optional[int] = None):
        self.file_path = file_path
        self.shuffle = shuffle
        self.max_tasks = max_tasks
        self.task_type = task_type
        get_logger().info(f"Loading tasks from {self.file_path}, Task type: {self.task_type}")
        self.tasks: List[Task] = []
        self.current_index = 0
        self._collected_task_ids: set = set()  # Track which tasks have been collected
        self._load_tasks()
    
    def _load_tasks(self) -> None:
        """
        Loads tasks from the specified file.
        
        - **Description**:
            Reads the JSON/JSONL file and converts each entry into a Task object.
            Supports both JSON (list of tasks) and JSONL (one task per line) formats.
        """
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"Task file not found: {self.file_path}")
        
        tasks_data = []
        
        # Determine file format and load data
        if self.file_path.endswith('.jsonl'):
            # JSONL format: one JSON object per line
            with open(self.file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line:
                        try:
                            task_data = json.loads(line)
                            tasks_data.append(task_data)
                        except json.JSONDecodeError as e:
                            get_logger().warning(f"Invalid JSON at line {line_num}: {e}")
        else:
            # JSON format: single JSON object (usually a list)
            with open(self.file_path, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                    if isinstance(data, list):
                        tasks_data = data
                    else:
                        tasks_data = [data]
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON file: {e}")
        
        # Convert to Task objects
        self.tasks = []
        for i, task_data in enumerate(tasks_data):
            if self.max_tasks and len(self.tasks) >= self.max_tasks:
                break
            
            task = self.task_type(**task_data)
            self.tasks.append(task)
        
        if self.shuffle:
            import random
            random.shuffle(self.tasks)
        
        get_logger().info(f"Loaded {len(self.tasks)} tasks from {self.file_path}")
    
    def next(self, n: int = 1) -> Optional[Union[Task, List[Task]]]:
        """
        Extracts the next N tasks for execution.
        
        - **Description**:
            Returns the next N pending tasks and marks them as running.
            If only one task is requested, returns a single Task object.
            If multiple tasks are requested, returns a list of Task objects.
            Returns None if no pending tasks are available.
        
        - **Args**:
            - `n` (int): Number of tasks to extract (default: 1)
        
        - **Returns**:
            - `Optional[Union[Task, List[Task]]]`: Single task, list of tasks, or None
        """
        if n <= 0:
            raise ValueError("n must be positive")
        
        pending_tasks = [task for task in self.tasks if task.status == TaskStatus.PENDING]
        
        if not pending_tasks:
            if n == 1:
                return None
            else:
                return []
        
        # Extract up to n tasks
        extracted_tasks = pending_tasks[:n]
        
        # Mark tasks as running
        for task in extracted_tasks:
            task.set_running()
        
        # Return single task or list based on n
        if n == 1:
            return extracted_tasks[0]
        else:
            return extracted_tasks
    
    def get_pending_count(self) -> int:
        """
        Returns the number of pending tasks.
        
        - **Description**:
            Counts tasks that are still in pending status.
        
        - **Returns**:
            - `int`: Number of pending tasks
        """
        return sum(1 for task in self.tasks if task.status == TaskStatus.PENDING)
    
    def get_completed_count(self) -> int:
        """
        Returns the number of completed tasks.
        
        - **Description**:
            Counts tasks that have been completed.
        
        - **Returns**:
            - `int`: Number of completed tasks
        """
        return sum(1 for task in self.tasks if task.status == TaskStatus.COMPLETED)
    
    def get_running_count(self) -> int:
        """
        Returns the number of running tasks.
        
        - **Description**:
            Counts tasks that are currently running.
        
        - **Returns**:
            - `int`: Number of running tasks
        """
        return sum(1 for task in self.tasks if task.status == TaskStatus.RUNNING)
    
    def reset_all(self) -> None:
        """
        Resets all tasks to pending status and clears collection tracking.
        
        - **Description**:
            Resets all tasks to their initial state for re-execution
            and clears the collection tracking set.
        """
        for task in self.tasks:
            task.reset()
        self._collected_task_ids.clear()  # Clear collection tracking
        get_logger().info("All tasks reset to pending status")
    
    def get_task_by_id(self, task_id: str) -> Optional[Task]:
        """
        Retrieves a task by its ID.
        
        - **Description**:
            Finds and returns a specific task using its unique identifier.
        
        - **Args**:
            - `task_id` (str): The unique identifier of the task
        
        - **Returns**:
            - `Optional[Task]`: The task if found, None otherwise
        """
        for task in self.tasks:
            if task.task_id == task_id:
                return task
        return None
    
    def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """
        Returns all tasks with the specified status.
        
        - **Description**:
            Filters tasks by their execution status.
        
        - **Args**:
            - `status` (TaskStatus): The status to filter by
        
        - **Returns**:
            - `List[Task]`: List of tasks with the specified status
        """
        return [task for task in self.tasks if task.status == status]
    
    def __len__(self) -> int:
        """
        Returns the total number of tasks.
        
        - **Description**:
            Returns the total count of all tasks in the loader.
        
        - **Returns**:
            - `int`: Total number of tasks
        """
        return len(self.tasks)
    
    def __iter__(self):
        """
        Makes TaskLoader iterable.
        
        - **Description**:
            Allows TaskLoader to be used in for loops, yielding pending tasks.
        """
        return self
    
    def __next__(self) -> Task:
        """
        Returns the next pending task in iteration.
        
        - **Description**:
            Returns the next pending task and marks it as running.
            Raises StopIteration when no more pending tasks are available.
        
        - **Returns**:
            - `Task`: The next pending task
        
        - **Raises**:
            - `StopIteration`: When no more pending tasks are available
        """
        result = self.next(1)
        if result is None:
            raise StopIteration
        return result  # type: ignore

    def get_task_results(self):
        """
        Extracts newly completed tasks and converts them to StorageTaskResult format.
        
        - **Description**:
            Retrieves only the newly completed tasks (not previously collected)
            and converts them to StorageTaskResult format for storage.
            Uses the assigned_agent_id from each task to determine the agent.
        
        - **Args**:
            - `agent_id` (int): The ID of the agent that executed the tasks
        
        - **Returns**:
            - `List[StorageTaskResult]`: List of new task results in storage format
        """
        from ..storage.type import StorageTaskResult
        
        completed_tasks = self.get_tasks_by_status(TaskStatus.COMPLETED)
        task_results = []
        
        for task in completed_tasks:
            # Skip if this task has already been collected
            if task.task_id in self._collected_task_ids:
                continue
                
            # Skip if task doesn't have an assigned agent
            if task.assigned_agent_id is None:
                get_logger().warning(f"Task {task.task_id} completed but has no assigned agent")
                continue
                
            # Convert task data to StorageTaskResult format
            task_result = StorageTaskResult(
                id=task.task_id,
                agent_id=task.assigned_agent_id,
                context=task.get_task_context(),
                ground_truth=task.ground_truth if task.ground_truth else {},
                result=task.result if task.result else {},
                created_at=datetime.now()
            )
            task_results.append(task_result)
            
            # Mark this task as collected
            if task.task_id:
                self._collected_task_ids.add(task.task_id)
        
        return task_results
    
    def get_uncollected_completed_count(self) -> int:
        """
        Returns the number of completed tasks that haven't been collected yet.
        
        - **Description**:
            Counts completed tasks that haven't been collected by getTaskResults yet.
        
        - **Returns**:
            - `int`: Number of uncollected completed tasks
        """
        completed_tasks = self.get_tasks_by_status(TaskStatus.COMPLETED)
        uncollected_count = 0
        
        for task in completed_tasks:
            if task.task_id not in self._collected_task_ids:
                uncollected_count += 1
        
        return uncollected_count
