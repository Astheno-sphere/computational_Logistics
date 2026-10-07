"""
Main CLI entry point for agentsociety-benchmark
"""
import importlib.metadata
from pathlib import Path

import click

from .commands import clone, list_tasks, run, list_installed, update_benchmarks, evaluate, list_evaluatable_tasks

version_string_of_agentsociety_benchmark = importlib.metadata.version("agentsociety-benchmark")

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


def get_default_home_dir() -> str:
    """Get default home directory for benchmark data"""
    # Use current working directory instead of home directory
    return str(Path.cwd() / ".agentsociety-benchmark")


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(version=version_string_of_agentsociety_benchmark, prog_name="AgentSociety Benchmark")
@click.option(
    "--home-dir",
    default=get_default_home_dir(),
    help="Home directory for benchmark data and configurations",
    type=click.Path(file_okay=False, dir_okay=True, writable=True),
)
@click.pass_context
def cli(ctx: click.Context, home_dir: str):
    """
    AgentSociety Benchmark CLI tool
    
    A comprehensive tool for running and managing agent benchmark experiments.
    
    Workflow:
    1. Use 'asbench list-tasks' to see available benchmark tasks
    2. Use 'asbench clone <task>' to download datasets from Git repositories (HuggingFace/GitHub)
    3. Use 'asbench run <task>' to run benchmark experiments with your config and agent
    4. Use 'asbench evaluate <task> <results_file>' to evaluate results independently
    """
    # Ensure context object exists
    ctx.ensure_object(dict)
    ctx.obj["home_dir"] = Path(home_dir)
    
    # Create home directory if it doesn't exist
    ctx.obj["home_dir"].mkdir(parents=True, exist_ok=True)


# Add subcommands
cli.add_command(clone)
cli.add_command(list_tasks)
cli.add_command(run)
cli.add_command(list_installed)
cli.add_command(update_benchmarks)
cli.add_command(evaluate)
cli.add_command(list_evaluatable_tasks)


if __name__ == "__main__":
    cli() 