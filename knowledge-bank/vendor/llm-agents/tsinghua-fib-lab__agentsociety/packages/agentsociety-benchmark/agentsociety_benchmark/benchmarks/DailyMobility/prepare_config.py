from pathlib import Path
from agentsociety.agent import CitizenAgentBase
from agentsociety.configs import Config, AgentsConfig, AgentConfig, MapConfig, ExpConfig, WorkflowStepConfig, EnvironmentConfig, WorkflowType
from agentsociety_benchmark.utils.agent_loader import load_agent_class
from agentsociety_benchmark.cli import BenchmarkConfig

def prepare_config(benchmark_config: BenchmarkConfig, agent_config: AgentConfig, datasets_path: Path, mode: str) -> Config:
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
    # Handle agent_class if it's a string (could be file path or class name)
    if isinstance(agent_config.agent_class, str):
        agent_path = Path(agent_config.agent_class)
        
        # Check if it's a file path (ends with .py or exists as file)
        if agent_path.suffix == '.py' or agent_path.exists():
            # It's a file path, load agent class from file
            agent_class = load_agent_class(agent_path, CitizenAgentBase)
            agent_config.agent_class = agent_class

    agent_config.memory_from_file = str(datasets_path / "profiles.json")
    agent_config.number = 100

    assert benchmark_config.llm is not None, "LLM is not provided, please provide LLM in the benchmark config"
    
    # Create solver configuration
    simulation_config = Config(
        llm=benchmark_config.llm,
        env=benchmark_config.env,    
        map=MapConfig(
            file_path=str(datasets_path / "beijing.pb")
        ),
        agents=AgentsConfig(
            citizens=[agent_config],
            supervisor=None,
            init_funcs=[]
        ),
        exp=ExpConfig(
            name="DailyMobilityGeneration_benchmark",
            workflow=[
                WorkflowStepConfig(
                    type=WorkflowType.RUN,
                    days=1.05,
                    ticks_per_step=15*60  # 15 minutes
                )
            ],
            environment=EnvironmentConfig(
                start_tick=0,
            ),
        ),
        logging_level="INFO",
    )
    
    return simulation_config