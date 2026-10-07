from pathlib import Path
from agentsociety.agent import CustomTool
from agentsociety.configs import IndividualConfig, TaskLoaderConfig, AgentConfig

from .task import BehaviorModelingTask
from .interactiontool import InteractionTool
from agentsociety_benchmark.cli import BenchmarkConfig

def prepare_config(benchmark_config: BenchmarkConfig, agent_config: AgentConfig, datasets_path: Path, mode: str) -> IndividualConfig:
    """
    Load and process configuration file with agent class from file or class name
    
    Args:
        config (BenchmarkConfig): Benchmark configuration
        agent_config (AgentConfig): Agent configuration
        datasets_path (Path): Path to datasets directory
        mode (str): Execution mode
    Returns:
        IndividualConfig: Processed configuration
    """
    # Add CustomTool for Information Retrieval
    agent_config.tools = [
        CustomTool(
            name="uir",  # User-Item-Review Network interaction tool
            tool=InteractionTool(data_dir=str(datasets_path)),
            description="Retrieve information from the internet",
        ),
    ]

    assert benchmark_config.llm is not None, "LLM is not provided, please provide LLM in the benchmark config"
    
    # Create solver configuration
    individual_config = IndividualConfig(
        name="BehaviorModeling_benchmark",
        llm=benchmark_config.llm,
        env=benchmark_config.env,    
        individual=agent_config,
        task_loader=TaskLoaderConfig(
            task_type=BehaviorModelingTask,
            file_path=str(datasets_path / f"{mode}_tasks.json"),
            shuffle=True,
        ),
        logging_level="INFO"
    )
    
    return individual_config