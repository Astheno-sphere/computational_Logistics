#!/usr/bin/env python3
"""Run experiment CLI script

This script manages experiment execution by:
1. Reading experiment configuration from init/init_config.json
2. Reading execution steps from init/steps.yaml
3. Running the experiment and storing all output in run/

The simplified structure means config files are directly in init/:
- init/config_params.py - Parameter generation script
- init/init_config.json - Experiment configuration
- init/steps.yaml - Execution steps

All experiment output (logs, replay data, etc.) is stored in run/:
- run/replay/ - Replay datasets (_schema.json + sharded JSONL)
- run/stdout.log - Standard output
- run/stderr.log - Standard error
- run/pid.json - Process ID file
"""

import asyncio
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv


def _validate_init_config(init_config_path: Path) -> tuple[bool, str, dict]:
    """Validate init_config.json file

    Returns:
        (is_valid, error_message, config_dict)
    """
    if not init_config_path.exists():
        return False, f"init_config.json not found: {init_config_path}", {}

    try:
        config = json.loads(init_config_path.read_text(encoding="utf-8"))

        # Basic validation
        required_keys = ["agents", "env_modules"]
        missing_keys = [k for k in required_keys if k not in config]
        if missing_keys:
            return False, f"Missing required keys in init_config.json: {missing_keys}", {}

        return True, "", config
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON in init_config.json: {e}", {}
    except Exception as e:
        return False, f"Error reading init_config.json: {e}", {}


def _validate_steps_yaml(steps_path: Path) -> tuple[bool, str]:
    """Validate steps.yaml file

    Returns:
        (is_valid, error_message)
    """
    if not steps_path.exists():
        return False, f"steps.yaml not found: {steps_path}"

    try:
        content = steps_path.read_text(encoding="utf-8")

        # Basic validation: check for required fields
        if "steps:" not in content and "steps\n" not in content:
            return False, f"steps.yaml must contain 'steps:' key"

        if "start_t:" not in content:
            return False, f"steps.yaml must contain 'start_t:' key"

        return True, ""
    except Exception as e:
        return False, f"Error reading steps.yaml: {e}"


def _ensure_run_dir(experiment_dir: Path) -> Path:
    """Ensure run directory exists and return its path

    Args:
        experiment_dir: Path to experiment directory

    Returns:
        Path to run directory
    """
    run_dir = experiment_dir / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _save_pid(
    run_dir: Path,
    pid: int,
    *,
    status: str,
    experiment_id: str | None = None,
) -> None:
    """Save process ID to pid.json

    Args:
        run_dir: Path to run directory
        pid: Process ID
    """
    pid_file = run_dir / "pid.json"
    pid_data = {
        "pid": pid,
        "status": status,
        "start_time": datetime.now().isoformat(),
    }
    if experiment_id:
        pid_data["experiment_id"] = experiment_id
    pid_file.write_text(json.dumps(pid_data, indent=2), encoding="utf-8")


def _get_default_paths(experiment_dir: Path) -> dict:
    """Get default paths for config files

    Args:
        experiment_dir: Path to experiment directory

    Returns:
        Dictionary with default paths
    """
    return {
        "init_config": experiment_dir / "init" / "init_config.json",
        "steps": experiment_dir / "init" / "steps.yaml",
        "run_dir": experiment_dir / "run",
    }


def _load_workspace_env(workspace_path: Path) -> None:
    """从工作区 ``.env`` 加载环境变量（覆盖已有 shell 值）。"""
    env_file = workspace_path / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=True)


async def main():
    parser = argparse.ArgumentParser(
        description="Run experiment commands",
        epilog="""
Examples:
  # List all experiments
  $PYTHON_PATH .agentsociety/bin/ags.py run-experiment list

  # Start an experiment (uses default init/ paths)
  $PYTHON_PATH .agentsociety/bin/ags.py run-experiment start --hypothesis-id 1 --experiment-id 1

  # Start with custom config paths
  $PYTHON_PATH .agentsociety/bin/ags.py run-experiment start --hypothesis-id 1 --experiment-id 1 \\
      --init-config /path/to/init_config.json \\
      --steps /path/to/steps.yaml

  # Check status
  $PYTHON_PATH .agentsociety/bin/ags.py run-experiment status --hypothesis-id 1 --experiment-id 1

  # Stop a running experiment
  $PYTHON_PATH .agentsociety/bin/ags.py run-experiment stop --hypothesis-id 1 --experiment-id 1
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "action", choices=["start", "stop", "status", "list"], help="Action to perform"
    )
    parser.add_argument("--hypothesis-id", help="Hypothesis ID")
    parser.add_argument("--experiment-id", help="Experiment ID")
    parser.add_argument("--run-id", default="run", help="Run ID (default: run)")
    parser.add_argument("--workspace", default=".", help="Workspace path")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument(
        "--foreground",
        action="store_true",
        help="Run in foreground instead of the default background mode",
    )
    parser.add_argument(
        "--init-config",
        type=Path,
        help="Path to init_config.json (default: init/init_config.json)",
    )
    parser.add_argument(
        "--steps",
        type=Path,
        help="Path to steps.yaml (default: init/steps.yaml)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume an interrupted run from run_dir/SOCIETY.json + SOCIETY_STEP.json",
    )

    args = parser.parse_args()

    workspace_path = Path(args.workspace).resolve()
    _load_workspace_env(workspace_path)

    from agentsociety2.logger import get_logger
    from agentsociety2.skills.experiment import (
        get_experiment_status,
        list_experiments,
        stop_experiment,
    )
    from agentsociety2.society.cli import ExperimentRunner

    logger = get_logger()

    if args.action == "list":
        experiments = await list_experiments(workspace_path)

        if args.json:
            output = [exp.model_dump() for exp in experiments]
            print(json.dumps(output, indent=2))
        else:
            print(f"Found {len(experiments)} experiment(s):")
            for exp in experiments:
                status_marker = (
                    "🏃"
                    if exp.is_running
                    else ("✅" if exp.status == "completed" else "❓")
                )
                print(
                    f"{status_marker} hypothesis_{exp.hypothesis_id}/experiment_{exp.experiment_id}"
                )
                print(
                    f"   init: {'✓' if exp.has_init else '✗'}  run: {'✓' if exp.has_run else '✗'}"
                )
                if exp.pid:
                    print(f"   PID: {exp.pid}")
        return 0

    # Other actions require hypothesis_id and experiment_id
    if not args.hypothesis_id or not args.experiment_id:
        print("Error: --hypothesis-id and --experiment-id are required")
        return 1

    # Get experiment directory
    exp_dir = (
        workspace_path / f"hypothesis_{args.hypothesis_id}" / f"experiment_{args.experiment_id}"
    )
    default_paths = _get_default_paths(exp_dir)
    experiment_key = f"{args.hypothesis_id}_{args.experiment_id}"

    # Use provided paths or defaults
    init_config_path = args.init_config or default_paths["init_config"]
    steps_path = args.steps or default_paths["steps"]

    if args.action == "start":
        # Validate config files exist
        is_valid, error_msg, _ = _validate_init_config(init_config_path)
        if not is_valid:
            print(f"Error: {error_msg}")
            return 1

        is_valid, error_msg = _validate_steps_yaml(steps_path)
        if not is_valid:
            print(f"Error: {error_msg}")
            return 1

        # Ensure run directory exists
        run_dir = _ensure_run_dir(exp_dir)
        stdout_log = run_dir / "stdout.log"
        stderr_log = run_dir / "stderr.log"

        print(
            f"Starting experiment hypothesis_{args.hypothesis_id}/experiment_{args.experiment_id}..."
        )
        print(f"  Config: {init_config_path}")
        print(f"  Steps: {steps_path}")
        print(f"  Output: {run_dir}")
        print(f"  Stdout Log: {stdout_log}")
        print(f"  Stderr Log: {stderr_log}")
        print(f"  Mode: {'foreground' if args.foreground else 'background'}")
        print()

        cli_command = [
            sys.executable,
            "-m",
            "agentsociety2.society.cli",
            "--config",
            str(init_config_path),
            "--steps",
            str(steps_path),
            "--run-dir",
            str(run_dir),
            "--experiment-id",
            experiment_key,
            "--log-level",
            "INFO",
        ]
        if args.resume:
            cli_command.append("--resume")

        if args.foreground:
            try:
                runner = ExperimentRunner(run_dir=run_dir)
                await runner.run(
                    config_path=init_config_path,
                    steps_path=steps_path,
                    experiment_id=experiment_key,
                    resume=args.resume,
                )

                print("\n✓ Experiment completed successfully!")
                return 0
            except KeyboardInterrupt:
                print("\n⚠ Experiment interrupted by user")
                return 130
            except Exception as e:
                print(f"\n✗ Experiment failed: {e}")
                logger.error(f"Experiment error: {e}", exc_info=True)
                return 1

        try:
            with open(stdout_log, "w", encoding="utf-8") as stdout_handle, open(
                stderr_log, "w", encoding="utf-8"
            ) as stderr_handle:
                process = subprocess.Popen(
                    cli_command,
                    cwd=workspace_path,
                    env=os.environ.copy(),
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                    start_new_session=True,
                    close_fds=True,
                )

            _save_pid(
                run_dir,
                process.pid,
                status="running",
                experiment_id=experiment_key,
            )
            print(f"✓ Experiment started in background (PID: {process.pid})")
            return 0
        except Exception as e:
            print(f"\n✗ Failed to start experiment in background: {e}")
            logger.error(f"Experiment start error: {e}", exc_info=True)
            return 1

    elif args.action == "stop":
        result = await stop_experiment(
            workspace_path=workspace_path,
            hypothesis_id=args.hypothesis_id,
            experiment_id=args.experiment_id,
            run_id=args.run_id,
        )
        print(result.get("content", result.get("error", "Done")))
        return 0 if result.get("success") else 1

    elif args.action == "status":
        status = await get_experiment_status(
            workspace_path=workspace_path,
            hypothesis_id=args.hypothesis_id,
            experiment_id=args.experiment_id,
            run_id=args.run_id,
        )

        if args.json:
            print(json.dumps(status.model_dump(), indent=2))
        else:
            print(f"Experiment: hypothesis_{status.hypothesis_id}/experiment_{status.experiment_id}")
            print(f"Status: {status.status}")
            if status.is_running:
                print(f"Running: Yes (PID: {status.pid})")
            else:
                print(f"Running: No")
            if status.start_time:
                print(f"Start Time: {status.start_time}")
            print(f"\nConfig files:")
            print(f"  init_config.json: {default_paths['init_config']}")
            print(f"  steps.yaml: {default_paths['steps']}")
            print(f"  run_dir: {default_paths['run_dir']}")

            # Check file existence
            init_config_exists = default_paths["init_config"].exists()
            steps_exists = default_paths["steps"].exists()
            replay_schema_exists = (
                default_paths["run_dir"] / "replay" / "_schema.json"
            ).exists()

            print(f"\nFiles:")
            print(f"  init/init_config.json: {'✓' if init_config_exists else '✗'}")
            print(f"  init/steps.yaml: {'✓' if steps_exists else '✗'}")
            print(f"  run/replay/_schema.json: {'✓' if replay_schema_exists else '✗'}")

        return 0

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
