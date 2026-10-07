"""
Evaluate command for executing benchmark evaluation independently
"""
import asyncio
from pathlib import Path

import click

from agentsociety_benchmark.runner import BenchmarkRunner

from .run import load_benchmark_config


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
        
        # Get evaluation function (lazy loading)
        if "evaluation_func" in task_config:
            functions["evaluation"] = task_config["evaluation_func"]
                
        return functions
        
    except ImportError as e:
        raise ValueError(f"Could not import benchmarks module: {e}")
    except Exception as e:
        raise ValueError(f"Failed to get task functions: {e}")


def load_results_file(results_path: Path):
    """
    Load results from file, supports JSON and PKL formats
    
    Args:
        results_path (Path): Path to the results file
        
    Returns:
        dict: Results data
    """
    if not results_path.exists():
        raise click.BadParameter(f"Results file {results_path} does not exist")
    
    try:
        import pickle
        with open(results_path, "rb") as f:
            data = pickle.load(f)
            return data["results"], data["metadata"]
    except Exception as e:
        raise click.BadParameter(f"Failed to parse PKL results file: {e}")


def load_results_from_file_object(file_object):
    """
    Load results from file object, supports JSON and PKL formats
    
    - **Description**:
        - Loads results data from a file object (bytes or file-like object)
        - Supports both JSON and PKL formats
        - Extracts results and metadata from the file content
        
    - **Args**:
        - `file_object` (bytes or file-like): File object containing results data
        
    - **Returns**:
        - `tuple`: (results, metadata) tuple containing the loaded data
    """
    try:
        import pickle
        from pathlib import Path
        class CrossPlatformUnpickler(pickle.Unpickler):
            """
            Custom unpickler that handles cross-platform path objects
            """
            def find_class(self, module, name):
                # Handle WindowsPath objects by converting them to the current platform's Path
                if module == 'pathlib' and name == 'WindowsPath':
                    return Path
                if module == 'pathlib' and name == 'PosixPath':
                    return Path
                return super().find_class(module, name)
        
        # Handle bytes object
        if isinstance(file_object, bytes):
            import io
            data = CrossPlatformUnpickler(io.BytesIO(file_object)).load()
        # Handle file-like object
        elif hasattr(file_object, 'read'):
            data = CrossPlatformUnpickler(file_object).load()
        else:
            raise ValueError("file_object must be bytes or a file-like object")
        
        if not isinstance(data, dict) or "results" not in data or "metadata" not in data:
            raise ValueError("Invalid results file format: missing 'results' or 'metadata' keys")
        
        return data["results"], data["metadata"]
        
    except Exception as e:
        raise ValueError(f"Failed to parse results file: {e}")


@click.command()
@click.argument("task", type=str)
@click.argument("results_file", type=click.Path(exists=True, file_okay=True, dir_okay=False))
@click.option(
    "--config",
    "-c",
    required=True,
    help="Path to configuration file (required)",
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
    "--output",
    "-o",
    required=False,
    help="Output file path for saving evaluation result (JSON format)",
    type=click.Path(file_okay=True, dir_okay=False),
)
@click.option(
    "--agent_filename",
    "-af",
    required=False,
    default="",
    help="Specify the filename for the related agent (optional)"
)
@click.option(
    "--tenant-id",
    default="",
    help="Specify tenant ID for database storage (optional)"
)
@click.option(
    "--official",
    is_flag=True,
    help="Official validation",
)
@click.pass_context
def evaluate(ctx: click.Context, 
             task: str, 
             results_file: str,
             datasets: str,
             output: str,
             tenant_id: str,
             config: str,
             official: bool,
             agent_filename: str):
    """
    Evaluate benchmark results independently
    
    TASK: Name of the task to evaluate (e.g., BehaviorModeling, HurricaneMobility)
    RESULTS_FILE: Path to the results file to evaluate (JSON or PKL format)
    
    This command allows you to run the evaluation function for a specific task
    on previously generated results without running the full benchmark pipeline.
    
    Supported file formats:
    - JSON: Standard JSON format with results data
    - PKL: Pickle format with results and metadata (from inference mode)
    
    Database storage:
    - If tenant-id, exp-id, llm, and agent are provided, results will be saved to database
    - If exp-id is not provided, a new UUID will be generated
    - Status will be set to 4 (evaluation-only) to distinguish from run results
    """
    home_dir = ctx.obj["home_dir"]

    # Validate config
    benchmark_config_path = Path(config)
    if not benchmark_config_path.exists():
        click.echo(f"Error: Config file '{config}' does not exist")
        return
    # Load configuration data
    try:
        benchmark_config = load_benchmark_config(benchmark_config_path)
    except Exception as e:
        click.echo(f"Error loading configuration: {e}")
        return
    
    # Validate task
    if not task:
        click.echo("Error: Task name is required")
        return
    
    # Validate results file
    results_path = Path(results_file)
    if not results_path.exists():
        click.echo(f"Error: Results file '{results_file}' does not exist")
        return
    
    # Set datasets path
    if datasets:
        datasets_path = Path(datasets)
    else:
        datasets_path = home_dir / "datasets" / task
    
    if not datasets_path.exists():
        click.echo(f"Error: Datasets directory '{datasets_path}' does not exist")
        click.echo("Please use 'asbench clone <task>' to download datasets first")
        return
    
    if not datasets_path.is_dir():
        click.echo(f"Error: Datasets path '{datasets_path}' is not a directory")
        return
    
    # Get task functions
    try:
        task_functions = get_task_functions(task)
        if not task_functions:
            click.echo(f"Error: Task '{task}' not found in benchmarks module")
            return
        
        if "evaluation" not in task_functions:
            click.echo(f"Error: Task '{task}' does not have an evaluation function")
            return
            
    except Exception as e:
        click.echo(f"Error getting task functions: {e}")
        return
    
    # Load results from file
    try:
        click.echo(f"Loading results from: {results_path}")
        results, metadata = load_results_file(results_path)
        click.echo("Results loaded successfully")
    except Exception as e:
        click.echo(f"Error loading results: {e}")
        return
    
    # Set output file path
    output_path = None
    if output:
        output_path = Path(output)
    else:
        # Generate default output path
        output_path = results_path.parent / "evaluation_results" / f"{task}_evaluation_result.json"
        
    # Set default values for database storage
    if not tenant_id:
        tenant_id = metadata["tenant_id"]
    
    # Run evaluation using BenchmarkRunner
    async def run_evaluation():
        try:
            click.echo(f"Running evaluation for task: {task} using BenchmarkRunner")
            click.echo(f"Datasets path: {datasets_path}")
            
            # Initialize BenchmarkRunner
            runner = BenchmarkRunner(
                config=benchmark_config,
            )
            
            # Run evaluation
            result = await runner.evaluate(
                tenant_id=tenant_id,
                task_name=task,
                results_file=str(results_path),
                datasets_path=datasets_path,
                output_file=output_path,
                official_validated=official,
                agent_filename=agent_filename,
                result_filename=str(results_file)
            )
            
            click.echo("Evaluation completed successfully")
            return result.get('evaluation_result')
            
        except Exception as e:
            click.echo(f"Error during evaluation: {e}")
            import traceback
            click.echo(f"Traceback: {traceback.format_exc()}")
            return None
    
    # Run the evaluation
    result = asyncio.run(run_evaluation())
    
    if result:
        click.echo("\n✅ Evaluation completed successfully!")
        if output_path:
            click.echo(f"Result saved to: {output_path}")
    else:
        click.echo("\n❌ Evaluation failed!")
        return 1
    
    return 0


@click.command()
@click.pass_context
def list_evaluatable_tasks(ctx: click.Context):
    """
    List all tasks that support evaluation
    """
    try:
        from agentsociety_benchmark.benchmarks import get_all_task_configs
        
        task_configs = get_all_task_configs()
        evaluatable_tasks = []
        
        for task_name, config in task_configs.items():
            if "evaluation_func" in config:
                evaluatable_tasks.append(task_name)
        
        if evaluatable_tasks:
            click.echo("Tasks that support evaluation:")
            for task in evaluatable_tasks:
                click.echo(f"  {click.style(task, fg='green', bold=True)}")
        else:
            click.echo("No tasks with evaluation functions found")
            
    except Exception as e:
        click.echo(f"Error listing evaluatable tasks: {e}")
        return 1
    
    return 0 