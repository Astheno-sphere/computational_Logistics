"""
Process-based task executor.

This module provides a process-based implementation of task execution,
similar to the Kubernetes executor but using local processes instead.
"""

import base64
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
import fcntl
import errno

from ..logger import get_logger

__all__ = ["ProcessExecutor"]


class ProcessExecutor:
    def __init__(self, home_dir: str):
        """Initialize the process executor.

        Args:
            home_dir (str): Base directory for storing process data and logs
        """
        self.home_dir = Path(home_dir) / "webui" / "executor"

        # Create necessary directories
        self.home_dir.mkdir(parents=True, exist_ok=True)

    def _get_status_file(self, exp_id: str, tenant_id: str) -> Path:
        """Get the path to the status file for a given experiment.

        Args:
            exp_id (str): Experiment ID
            tenant_id (str): Tenant ID

        Returns:
            Path: Path to the status file
        """
        os.makedirs(self.home_dir / tenant_id / exp_id, exist_ok=True)
        return self.home_dir / tenant_id / exp_id / "status.json"

    def _get_log_file(self, exp_id: str, tenant_id: str) -> Path:
        """Get the path to the log file for a given experiment.

        Args:
            exp_id (str): Experiment ID
            tenant_id (str): Tenant ID

        Returns:
            Path: Path to the log file
        """
        os.makedirs(self.home_dir / tenant_id / exp_id, exist_ok=True)
        return self.home_dir / tenant_id / exp_id / "log.txt"

    def _acquire_file_lock(self, file_path: Path):
        """Acquire an exclusive lock on a file.

        Args:
            file_path (Path): Path to the file to lock
        """
        lock_file = file_path.with_suffix(".lock")
        lock_fd = os.open(lock_file, os.O_CREAT | os.O_RDWR)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            return lock_fd
        except IOError as e:
            os.close(lock_fd)
            if e.errno == errno.EAGAIN:
                raise RuntimeError("Could not acquire lock on file")
            raise

    def _release_file_lock(self, lock_fd: int):
        """Release a file lock.

        Args:
            lock_fd (int): File descriptor of the lock
        """
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)

    async def create(
        self,
        config_base64: Optional[str] = None,
        config_path: Optional[str] = None,
        callback_url: str = "",
        callback_auth_token: str = "",
        tenant_id: str = "",
    ):
        """Create a new process for task execution.

        Args:
            config_base64 (Optional[str]): Base64 encoded configuration
            config_path (Optional[str]): Path to configuration file
            callback_url (str): URL to call when task completes
            callback_auth_token (str): Authentication token for callback
            tenant_id (str): Tenant ID
        """
        # Load configuration
        config_dict = None

        # Load configuration from file
        if config_path and not config_base64:
            if not os.path.exists(config_path):
                raise ValueError(f"Configuration file {config_path} does not exist")

            file_ext = Path(config_path).suffix.lower()
            if file_ext == ".json":
                with open(config_path, "r", encoding="utf-8") as f:
                    config_dict = json.load(f)
            elif file_ext in [".yaml", ".yml"]:
                import yaml

                with open(config_path, "r", encoding="utf-8") as f:
                    config_dict = yaml.safe_load(f)
            else:
                raise ValueError(f"Unsupported configuration file format: {file_ext}")

        # Load configuration from base64
        elif config_base64:
            try:
                config_dict = json.loads(base64.b64decode(config_base64).decode())
            except Exception as e:
                raise ValueError(f"Failed to decode base64 configuration: {e}")

        # Ensure configuration exists
        if not config_dict:
            raise ValueError("No configuration provided")

        exp_id = config_dict["exp"]["id"]
        status_file = self._get_status_file(exp_id, tenant_id)
        log_file = self._get_log_file(exp_id, tenant_id)

        # Start the process
        cmd = [
            sys.executable,
            "-m",
            "agentsociety.cli.cli",
            "run",
            "--config-base64",
            config_base64
            or base64.b64encode(json.dumps(config_dict).encode()).decode(),
            "--tenant-id",
            tenant_id,
        ]
        if callback_url != "":
            cmd += [
                "--callback-url",
                f"{callback_url}/api/run-experiments/{exp_id}/finish?callback_auth_token={callback_auth_token}",
            ]

        # Open log file
        with open(log_file, "w") as f:
            # Start process with output redirected to log file
            process = subprocess.Popen(
                cmd,
                stdout=f,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setpgrp,  # Create new process group
            )

        # Initialize status file
        status = {
            "command": " ".join(cmd),
            "status": "Running",
            "start_time": datetime.now().isoformat(),
            "pid": process.pid,
        }

        # Update status with PID
        lock_fd = self._acquire_file_lock(status_file)
        try:
            status["pid"] = process.pid
            with open(status_file, "w") as f:
                json.dump(status, f)
        finally:
            self._release_file_lock(lock_fd)

        get_logger().info(f"Created process: {process.pid} for experiment {exp_id}")

    async def delete(self, tenant_id: str, exp_id: str) -> None:
        """Delete a running process.

        Args:
            tenant_id (str): Tenant ID
            exp_id (str): Experiment ID

        Raises:
            Exception: If process not found or deletion fails
        """
        status_file = self._get_status_file(exp_id, tenant_id)

        if not status_file.exists():
            raise Exception("Experiment is not running")

        # Read status with lock
        lock_fd = self._acquire_file_lock(status_file)
        try:
            with open(status_file, "r") as f:
                status = json.load(f)
        finally:
            self._release_file_lock(lock_fd)

        if not status.get("pid"):
            raise Exception("Process ID not found")

        try:
            # Send SIGTERM to the process group
            os.killpg(os.getpgid(status["pid"]), signal.SIGTERM)

            # Wait for process to terminate
            for _ in range(10):  # Wait up to 10 seconds
                try:
                    os.kill(status["pid"], 0)
                    time.sleep(1)
                except OSError:
                    break
            else:
                # If process still exists, force kill
                os.killpg(os.getpgid(status["pid"]), signal.SIGKILL)

            # Update status
            lock_fd = self._acquire_file_lock(status_file)
            try:
                status["status"] = "Terminated"
                status["end_time"] = datetime.now().isoformat()
                with open(status_file, "w") as f:
                    json.dump(status, f)
            finally:
                self._release_file_lock(lock_fd)

        except ProcessLookupError:
            # Process already terminated
            pass

    async def get_logs(
        self, tenant_id: str, exp_id: str, line_limit: int = 1000
    ) -> str:
        """Get logs for a process.

        Args:
            tenant_id (str): Tenant ID
            exp_id (str): Experiment ID
            line_limit (int): Number of lines to return

        Returns:
            str: Process logs

        Raises:
            Exception: If logs not found
        """
        log_file = self._get_log_file(exp_id, tenant_id)

        if not log_file.exists():
            raise Exception("Log file not found")

        with open(log_file, "r") as f:
            return "\n".join(f.readlines()[-line_limit:])

    async def get_status(self, tenant_id: str, exp_id: str) -> str:
        """Get status of a process.

        Args:
            tenant_id (str): Tenant ID
            exp_id (str): Experiment ID

        Returns:
            str: Process status

        Raises:
            Exception: If status not found
        """
        status_file = self._get_status_file(exp_id, tenant_id)

        if not status_file.exists():
            raise Exception("Status file not found")

        # Read status with lock
        lock_fd = self._acquire_file_lock(status_file)
        try:
            with open(status_file, "r") as f:
                status = json.load(f)
        finally:
            self._release_file_lock(lock_fd)

        # Check if process is still running
        if status["status"] == "Running" and status.get("pid"):
            try:
                os.kill(status["pid"], 0)
            except OSError:
                # Process is no longer running
                status["status"] = "Terminated"
                status["end_time"] = datetime.now().isoformat()

                # Update status file
                lock_fd = self._acquire_file_lock(status_file)
                try:
                    with open(status_file, "w") as f:
                        json.dump(status, f)
                finally:
                    self._release_file_lock(lock_fd)

        return status["status"]
