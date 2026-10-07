"""
Run command for executing benchmark experiments
"""
import asyncio
import json
from pathlib import Path
from typing import Optional

import click
import requests
import yaml

from ..config import BenchmarkConfig
from agentsociety.configs import AgentConfig
from agentsociety_benchmark.runner import BenchmarkRunner


def load_benchmark_config(config_path: Path) -> BenchmarkConfig:
    """
    Load configuration file, supports JSON and YAML formats
    
    Args:
        config_path (str): Path to the configuration file
        
    Returns:
        BenchmarkConfig: Configuration data
    """
    if not config_path.exists():
        raise click.BadParameter(f"Benchmark config file {config_path} does not exist")
    
    file_ext = config_path.suffix.lower()
    if file_ext in [".json"]:
        try:
            with open(config_path, "r") as f:
                return BenchmarkConfig.model_validate(json.load(f))
        except json.JSONDecodeError as e:
            raise click.BadParameter(f"Failed to parse JSON benchmark config file: {e}")
    elif file_ext in [".yaml", ".yml"]:
        try:
            with open(config_path, "r") as f:
                return BenchmarkConfig.model_validate(yaml.safe_load(f))
        except yaml.YAMLError as e:
            raise click.BadParameter(f"Failed to parse YAML benchmark config file: {e}")
    else:
        raise click.BadParameter(f"Unsupported benchmark config file format: {file_ext}")


def load_agent_config(agent_path: Path) -> AgentConfig:
    """
    Load agent configuration from agent file
    
    Args:
        agent_path (Path): Path to the agent implementation file
        
    Returns:
        AgentConfig: Agent configuration object
    """
    file_ext = agent_path.suffix.lower()
    if file_ext in [".json"]:
        try:
            with open(agent_path, "r") as f:
                return AgentConfig.model_validate(json.load(f))
        except json.JSONDecodeError as e:
            raise click.BadParameter(f"Failed to parse JSON agent config file: {e}")
    elif file_ext in [".yaml", ".yml"]:
        try:
            with open(agent_path, "r") as f:
                return AgentConfig.model_validate(yaml.safe_load(f))
        except yaml.YAMLError as e:
            raise click.BadParameter(f"Failed to parse YAML agent config file: {e}")
    elif file_ext in [".py"]:
        return AgentConfig(
            agent_class=str(agent_path),
            number=1,
        )
    else:
        raise click.BadParameter(f"Unsupported agent config file format: {file_ext}")


def get_task_functions(task_name: str):
    """
    Get task functions from the benchmarks module mapping
    
    Args:
        task_name (str): Name of the task
        
    Returns:
        dict: Dictionary containing task functions (prepare_config, entry, evaluation)
    """
    try:
        from agentsociety_benchmark.benchmarks import get_task_config # type: ignore
        
        task_config = get_task_config(task_name)
        if not task_config:
            return None
            
        functions = {}
        
        # Get prepare_config function (lazy loading)
        if "prepare_config_func" in task_config:
            functions["prepare_config"] = task_config["prepare_config_func"]
                
        # Get entry function (lazy loading)
        if "entry" in task_config:
            functions["entry"] = task_config["entry"]
                
        # Get evaluation function (lazy loading)
        if "evaluation_func" in task_config:
            functions["evaluation"] = task_config["evaluation_func"]
                
        return functions
        
    except ImportError as e:
        raise ValueError(f"Could not import benchmarks module: {e}")
    except Exception as e:
        raise ValueError(f"Failed to get task functions: {e}")


def find_task_config(task_dir: Path) -> Optional[Path]:
    """
    Find configuration file in task directory
    
    Args:
        task_dir (Path): Task directory to search
        
    Returns:
        Optional[Path]: Path to configuration file if found
    """
    config_patterns = ["config.yaml", "config.yml", "config.json", "benchmark.yaml", "benchmark.yml", "benchmark.json"]
    
    for pattern in config_patterns:
        config_file = task_dir / pattern
        if config_file.exists():
            return config_file
    
    return None





@click.command()
@click.argument("task", type=str)
@click.option(
    "--config",
    "-c",
    required=True,
    help="Path to configuration file (required)",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
)
@click.option(
    "--agent",
    "-a",
    required=True,
    help="The agent configuration file or .py file (required)",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
)
@click.option(
    "--datasets",
    "-d",
    required=False,
    help="Path to datasets directory (required if you clone datasets into non-default directory)",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
)
@click.option(
    "--official",
    is_flag=True,
    help="Official validation",
)
@click.option(
    "--mode",
    "-m",
    required=False,
    help="Execution mode: 'test' runs full pipeline including evaluation, 'inference' skips evaluation and saves results",
    type=click.Choice(["test", "inference"]),
    default="test",
)
@click.option("--tenant-id", default="", help="Specify tenant ID")
@click.option("--callback-url", default="", help="Specify callback URL (POST)")
@click.pass_context
def run(ctx: click.Context, 
        task: str, 
        config: str, 
        agent: str, 
        datasets: str,
        tenant_id: str,
        callback_url: str,
        official: bool,
        mode: str,
    ):
    """
    Run a benchmark experiment with custom configuration and agent
    
    TASK: Name of the task to run (e.g., BehaviorModeling, HurricaneMobility)
    """    
    # Validate config, agent, and datasets files
    benchmark_config_path = Path(config)
    agent_config_path = Path(agent)
    if datasets:
        datasets_path = Path(datasets)
    else:
        datasets_path = Path(ctx.obj["home_dir"]) / "datasets" / task
    
    if not benchmark_config_path.exists():
        click.echo(f"Error: Config file '{config}' does not exist")
        return
    
    if not agent_config_path.exists():
        click.echo(f"Error: Agent file '{agent}' does not exist")
        return
    
    if not datasets_path.exists():
        click.echo(f"Error: Datasets directory '{datasets}' does not exist")
        return
    
    if not datasets_path.is_dir():
        click.echo(f"Error: Datasets path '{datasets}' is not a directory")
        return
    
    # Load configuration data
    try:
        benchmark_config = load_benchmark_config(benchmark_config_path)
    except Exception as e:
        click.echo(f"Error loading configuration: {e}")
        return
    
    # Load agent configuration
    agent_config = load_agent_config(agent_config_path)

    # Run benchmark using BenchmarkRunner
    async def run_benchmark_with_runner():
        try:
            # Initialize BenchmarkRunner
            runner = BenchmarkRunner(
                config=benchmark_config,
            )
            
            click.echo(f"Running benchmark task: {task} using BenchmarkRunner")
            
            # Run benchmark
            result = await runner.run(
                task_name=task,
                tenant_id=tenant_id,
                agent_config=agent_config,
                datasets_path=datasets_path,
                mode=mode,
                official_validated=official,
                save_results=True,
                agent_filename=f"{agent}"
            )
            
            click.echo("Benchmark task completed successfully")
            click.echo(f"Results file: {result.get('result_filename', 'N/A')}")
            
            if result.get('evaluation'):
                click.echo(f"Evaluation completed: {result['evaluation']}")
            
            return result
            
        except Exception as e:
            error_msg = f"Error during benchmark execution: {str(e)}"
            click.echo(f"Error: {error_msg}")
            raise e
    
    # Run the benchmark using BenchmarkRunner
    asyncio.run(run_benchmark_with_runner())
    
    if callback_url:
        requests.post(callback_url)


@click.command()
@click.pass_context
def list_installed(ctx: click.Context):
    """
    List downloaded benchmark datasets
    """
    home_dir = ctx.obj["home_dir"]
    datasets_dir = home_dir / "datasets"
    
    if not datasets_dir.exists():
        click.echo("No datasets downloaded yet")
        click.echo("Use 'asbench clone <task>' to download datasets")
        return
    
    downloaded_datasets = [d for d in datasets_dir.iterdir() if d.is_dir()]
    
    if not downloaded_datasets:
        click.echo("No datasets downloaded yet")
        click.echo("Use 'asbench clone <task>' to download datasets")
        return
    
    click.echo("Downloaded benchmark datasets:")
    click.echo()
    
    for dataset_dir in downloaded_datasets:
        task_name = dataset_dir.name
        
        click.echo(f"  {click.style(task_name, fg='green', bold=True)}")
        click.echo(f"    Location: {dataset_dir}")
        click.echo(f"    Config: {click.style('User-provided (--config)', fg='blue')}")
        click.echo(f"    Agent: {click.style('User-provided (--agent)', fg='blue')}")
        click.echo(f"    Datasets: {click.style('User-provided (--datasets)', fg='blue')}")
        click.echo()