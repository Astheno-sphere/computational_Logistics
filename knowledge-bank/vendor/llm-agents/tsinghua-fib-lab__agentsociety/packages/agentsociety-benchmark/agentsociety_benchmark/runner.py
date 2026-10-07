"""
Independent Benchmark Runner for executing and evaluating benchmarks.

This module provides a standalone BenchmarkRunner class that abstracts
the core functionality of running benchmarks and evaluating results.
"""

import json
import yaml
import pickle
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from agentsociety.configs import AgentConfig, Config, IndividualConfig
from agentsociety_benchmark.cli.config import BenchmarkConfig
from agentsociety_benchmark.storage.database import DatabaseWriter
from agentsociety_benchmark.storage.type import StorageBenchmark, BenchmarkStatus
from agentsociety_benchmark.utils.agent_loader import load_agent_class

class BenchmarkRunner:
    """
    Independent benchmark runner for executing and evaluating benchmarks.
    
    - **Description**:
        - Provides a unified interface for running benchmarks and evaluating results
        - Abstracts the core functionality from CLI commands
        - Supports both synchronous and asynchronous operations
        
    - **Args**:
        - `home_dir` (Optional[Path]): Home directory for database and logs
        - `tenant_id` (str): Tenant ID for database operations
        - `exp_id` (str): Experiment ID for tracking
    """
    
    def __init__(self, 
                 config: BenchmarkConfig):
        self.config = config
        self.home_dir = Path(config.env.home_dir) if config.env.home_dir else Path.home() / ".agentsociety-benchmark"
        
    def _load_benchmark_config(self, config_path: Path) -> BenchmarkConfig:
        """
        Load benchmark configuration from file.
        
        - **Description**:
            - Supports JSON and YAML configuration formats
            - Validates configuration using Pydantic models
            
        - **Args**:
            - `config_path` (Path): Path to the configuration file
            
        - **Returns**:
            - `BenchmarkConfig`: Validated configuration object
        """
        if not config_path.exists():
            raise FileNotFoundError(f"Benchmark config file {config_path} does not exist")
        
        file_ext = config_path.suffix.lower()
        if file_ext in [".json"]:
            try:
                with open(config_path, "r") as f:
                    return BenchmarkConfig.model_validate(json.load(f))
            except json.JSONDecodeError as e:
                raise ValueError(f"Failed to parse JSON benchmark config file: {e}")
        elif file_ext in [".yaml", ".yml"]:
            try:
                import yaml
                with open(config_path, "r") as f:
                    return BenchmarkConfig.model_validate(yaml.safe_load(f))
            except yaml.YAMLError as e:
                raise ValueError(f"Failed to parse YAML benchmark config file: {e}")
        else:
            raise ValueError(f"Unsupported benchmark config file format: {file_ext}")
    
    def _load_agent_config(self, agent_path: Path) -> AgentConfig:
        """
        Load agent configuration from file.
        
        - **Description**:
            - Supports JSON, YAML, and Python file formats
            - Handles different agent configuration types
            
        - **Args**:
            - `agent_path` (Path): Path to the agent configuration file
            
        - **Returns**:
            - `AgentConfig`: Agent configuration object
        """
        file_ext = agent_path.suffix.lower()
        if file_ext in [".json"]:
            try:
                with open(agent_path, "r") as f:
                    return AgentConfig.model_validate(json.load(f))
            except json.JSONDecodeError as e:
                raise ValueError(f"Failed to parse JSON agent config file: {e}")
        elif file_ext in [".yaml", ".yml"]:
            try:
                import yaml
                with open(agent_path, "r") as f:
                    return AgentConfig.model_validate(yaml.safe_load(f))
            except yaml.YAMLError as e:
                raise ValueError(f"Failed to parse YAML agent config file: {e}")
        elif file_ext in [".py"]:
            return AgentConfig(
                agent_class=str(agent_path),
                number=1,
            )
        else:
            raise ValueError(f"Unsupported agent config file format: {file_ext}")
        
    def _get_task_config(self, task_name: str) -> Optional[Dict[str, Any]]:
        """
        Get task configuration from the benchmarks module.
        """
        try:
            from agentsociety_benchmark.benchmarks import get_task_config
            return get_task_config(task_name)
        except ImportError:
            return None
    
    def _get_task_functions(self, task_name: str) -> Optional[Dict[str, Any]]:
        """
        Get task functions from the benchmarks module.
        
        - **Description**:
            - Dynamically loads task functions based on task name
            - Supports prepare_config, entry, and evaluation functions
            
        - **Args**:
            - `task_name` (str): Name of the benchmark task
            
        - **Returns**:
            - `Optional[Dict[str, Any]]`: Dictionary containing task functions
        """
        try:
            task_config = self._get_task_config(task_name)
            if not task_config:
                return None
                
            functions = {}
            
            # Get prepare_config function (lazy loading)
            if "prepare_config_func" in task_config:
                functions["prepare_config"] = task_config["prepare_config_func"]()
                    
            # Get entry function (lazy loading)
            if "entry" in task_config:
                functions["entry"] = task_config["entry"]()
                    
            # Get evaluation function (lazy loading)
            if "evaluation_func" in task_config:
                functions["evaluation"] = task_config["evaluation_func"]()
                    
            return functions
            
        except ImportError as e:
            raise ValueError(f"Could not import benchmarks module: {e}")
        except Exception as e:
            raise ValueError(f"Failed to get task functions: {e}")
    
    async def _init_database_writer(self, tenant_id: str, exp_id: str) -> DatabaseWriter:
        """
        Initialize database writer for storing results.
        
        - **Description**:
            - Creates database configuration and writer instance
            - Handles database initialization
            
        - **Args**:
            - `tenant_id` (str): Tenant ID for database operations
            - `exp_id` (str): Experiment ID for database operations
            
        - **Returns**:
            - `DatabaseWriter`: Initialized database writer
        """        
        database_writer = DatabaseWriter(tenant_id, exp_id, self.config.env.db, str(self.home_dir))
        await database_writer.init()
        return database_writer
    
    async def _update_benchmark_status(self, 
                                     database_writer: DatabaseWriter,
                                     tenant_id: str,
                                     exp_id: str,
                                     task_name: str,
                                     llm: str,
                                     agent: str,
                                     config_str: str,
                                     status: BenchmarkStatus,
                                     result_info: str = "",
                                     final_score: float = 0.0,
                                     error: str = "",
                                     official_validated: bool = False,
                                     agent_filename: str = "",
                                     result_filename: str = ""):
        """
        Update benchmark status in database.
        
        - **Description**:
            - Updates benchmark information in the database
            - Handles status updates during execution and completion
            
        - **Args**:
            - `database_writer` (DatabaseWriter): Database writer instance
            - `task_name` (str): Name of the benchmark task
            - `llm` (str): LLM name
            - `agent` (str): Agent name
            - `config_str` (str): Configuration as JSON string
            - `status` (int): Status code (1=running, 2=completed, 3=error, 4=evaluation)
            - `result_info` (str): Result information
            - `final_score` (float): Final score
            - `error` (str): Error message if any
            - `official_validated` (bool): Whether this is an official validation
        """
        benchmark_info = StorageBenchmark(
            tenant_id=tenant_id,
            id=exp_id,
            benchmark_name=task_name,
            llm=llm,
            agent=agent,
            official_validated=official_validated,
            status=status,
            result_info=result_info,
            final_score=final_score,
            config=config_str,
            error=error,
            agent_filename=agent_filename,
            result_filename=result_filename,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        await database_writer.update_benchmark_info(benchmark_info)
    
    async def run(self,
                 tenant_id: str,
                 task_name: str,
                 agent_config: AgentConfig,
                 agent_filename: str = "",
                 datasets_path: Optional[Path] = None,
                 mode: str = "test",
                 official_validated: bool = False,
                 save_results: bool = True) -> Dict[str, Any]:
        """
        Run a benchmark experiment.
        
        - **Description**:
            - Executes a benchmark experiment with the given configuration objects
            - Supports both test mode (with evaluation) and inference mode
            - Handles database updates and result storage
            
        - **Args**:
            - `task_name` (str): Name of the benchmark task
            - `benchmark_config` (BenchmarkConfig): Benchmark configuration object
            - `agent_config` (AgentConfig): Agent configuration object
            - `datasets_path` (Optional[Path]): Path to datasets directory
            - `mode` (str): Execution mode ('test' or 'inference')
            - `official_validated` (bool): Whether this is an official validation
            - `save_results` (bool): Whether to save results to database
            
        - **Returns**:
            - `Dict[str, Any]`: Execution results and metadata
        """
        assert self.config.llm is not None, "LLM is not provided, please provide LLM in the benchmark config"
        
        # Get task functions
        task_functions = self._get_task_functions(task_name)
        if not task_functions:
            raise ValueError(f"Task '{task_name}' not found or invalid")
        
        task_config = self._get_task_config(task_name)
        if not task_config:
            raise ValueError(f"Task '{task_name}' not found or invalid")
        
        database_writer = None

        # Handle agent_class if it's a string (could be file path or class name)
        if isinstance(agent_config.agent_class, str):
            agent_path = Path(agent_config.agent_class)
            
            # Check if it's a file path (ends with .py or exists as file)
            if agent_path.suffix == '.py' or agent_path.exists():
                # It's a file path, load agent class from file
                agent_class = load_agent_class(agent_path, task_config["agent_class"])
                agent_config.agent_class = agent_class
        
        try:
            # Prepare configuration
            if "prepare_config" in task_functions:
                prepare_config_function = task_functions["prepare_config"]
                prepared_config = prepare_config_function(
                    benchmark_config=self.config,
                    agent_config=agent_config,
                    datasets_path=datasets_path,
                    mode=mode
                )
            else:
                prepared_config = self.config

            # Initialize database writer if needed
            if save_results:
                if isinstance(prepared_config, IndividualConfig):
                    exp_id = prepared_config.id
                if isinstance(prepared_config, Config):
                    exp_id = prepared_config.exp.id
                database_writer = await self._init_database_writer(tenant_id, str(exp_id))

            # Update status to running
            if database_writer:
                config_str = yaml.dump(
                        prepared_config.model_dump(
                            exclude_defaults=True,
                            exclude_none=True,
                            exclude={
                                "llm": {
                                    "__all__": {"api_key": True},
                                },
                                "env": {
                                    "db": {"pg_dsn": True},
                                    "s3": True,
                                },
                                "individual": {
                                    "tools": True,
                                },
                            },
                        ),
                        allow_unicode=True
                    )
                # Extract LLM name from config
                llm_name = prepared_config.llm[0].model if prepared_config.llm else "unknown"
                # Extract agent name from config
                agent_config_str = yaml.dump(agent_config.model_dump(
                    exclude_defaults=True,
                    exclude_none=True,
                    exclude={
                        "tools": True,
                    },
                ), allow_unicode=True)
                
                await self._update_benchmark_status(
                    database_writer=database_writer,
                    tenant_id=tenant_id,
                    exp_id=str(exp_id),
                    task_name=task_name,
                    llm=llm_name,
                    agent=agent_config_str,
                    config_str=config_str,
                    status=BenchmarkStatus.RUNNING,
                    official_validated=official_validated,
                    agent_filename=agent_filename,
                )
            
            # Execute benchmark
            if "entry" not in task_functions:
                raise ValueError(f"Task '{task_name}' does not have an entry function")
            
            entry_function = task_functions["entry"]
            results = await entry_function(
                config=prepared_config,
                tenant_id=tenant_id
            )

            result_filename = self.home_dir / "inference_results" / f"{task_name}_{exp_id}_results.pkl"
            result_filename.parent.mkdir(parents=True, exist_ok=True)
            
            # Save results
            results_data = {
                "results": results,
                "metadata": {
                    "task_name": task_name,
                    "tenant_id": tenant_id,
                    "llm": llm_name,
                    "exp_id": exp_id,
                    "config": config_str,
                    "agent": agent_config_str,
                    "agent_filename": agent_filename,
                    "result_filename": result_filename,
                    "execution_time": datetime.now().isoformat(),
                    "mode": mode
                }
            }
            
            # Save to file
            with open(result_filename, "wb") as f:
                pickle.dump(results_data, f)
            
            # Update database with completion status
            if database_writer:
                await self._update_benchmark_status(
                    database_writer=database_writer,
                    tenant_id=tenant_id,
                    exp_id=str(exp_id),
                    task_name=task_name,
                    llm=llm_name,
                    agent=agent_config_str,
                    config_str=config_str,
                    status=BenchmarkStatus.FINISHED,
                    official_validated=official_validated,
                    agent_filename=agent_filename,
                    result_filename=str(result_filename)
                )
            
            # Run evaluation if in test mode
            evaluation_result = None
            if mode == "test" and "evaluation" in task_functions:
                evaluation_function = task_functions["evaluation"]
                evaluation_result = await evaluation_function(
                    to_evaluate=results,
                    datasets_path=str(datasets_path),
                    metadata=results_data["metadata"]
                )
            
            return {
                "success": True,
                "result_filename": str(result_filename),
                "results": results,
                "evaluation": evaluation_result,
                "task_name": task_name,
                "mode": mode
            }
            
        except Exception as e:
            # Update database with error status
            if database_writer:
                await self._update_benchmark_status(
                    database_writer=database_writer,
                    tenant_id=tenant_id,
                    exp_id=str(exp_id),
                    task_name=task_name,
                    llm=llm_name,
                    agent=agent_config_str,
                    config_str=config_str,
                    status=BenchmarkStatus.ERROR,
                    error=str(e),
                    official_validated=official_validated,
                    agent_filename=agent_filename,
                )
            
            raise e
        finally:
            if database_writer:
                await database_writer.close()
    
    async def evaluate(self,
                      tenant_id: str,
                      task_name: str,
                      results_file: str,
                      agent_filename: str = "",
                      result_filename: str = "",
                      datasets_path: Optional[Path] = None,
                      official_validated: bool = False,
                      output_file: Optional[Path] = None) -> Dict[str, Any]:
        """
        Evaluate benchmark results.
        
        - **Description**:
            - Evaluates benchmark results using the task's evaluation function
            - Supports saving results to file and database
            - Handles evaluation metadata and scoring
            
        - **Args**:
            - `task_name` (str): Name of the benchmark task
            - `results_file` (str): Path to the results file
            - `datasets_path` (Optional[Path]): Path to datasets directory
            - `output_file` (Optional[Path]): Output file for evaluation results
            
        - **Returns**:
            - `Dict[str, Any]`: Evaluation results and metadata
        """
        # Load results
        results_path = Path(results_file)
        if not results_path.exists():
            raise FileNotFoundError(f"Results file {results_file} does not exist")
        
        try:
            with open(results_path, "rb") as f:
                data = pickle.load(f)
                results, metadata = data["results"], data["metadata"]
                print(f"Inference Evaluation Metadata: \n{metadata}")
        except Exception as e:
            raise ValueError(f"Failed to load results file: {e}")
        if agent_filename == "":
            agent_filename = metadata.get("agent_filename", "unknown")
        if result_filename == "":
            result_filename = metadata.get("result_filename", "unknown")
        return await self._evaluate_results(tenant_id, task_name, results, metadata, datasets_path, output_file, official_validated, agent_filename, result_filename)

    async def evaluate_from_file_object(self,
                                       tenant_id: str,
                                       task_name: str,
                                       file_object,
                                       agent_filename: str = "",
                                       result_filename: str = "",
                                       datasets_path: Optional[Path] = None,
                                       output_file: Optional[Path] = None,
                                       official_validated: bool = False) -> Dict[str, Any]:
        """
        Evaluate benchmark results from file object.
        
        - **Description**:
            - Evaluates benchmark results using the task's evaluation function
            - Accepts file object (bytes or file-like) instead of file path
            - Supports saving results to file and database
            - Handles evaluation metadata and scoring
            
        - **Args**:
            - `task_name` (str): Name of the benchmark task
            - `file_object` (bytes or file-like): File object containing results data
            - `datasets_path` (Optional[Path]): Path to datasets directory
            - `output_file` (Optional[Path]): Output file for evaluation results
            
        - **Returns**:
            - `Dict[str, Any]`: Evaluation results and metadata
        """
        # Import the function to load results from file object
        from .cli.commands.evaluate import load_results_from_file_object
        
        try:
            # Load results from file object
            results, metadata = load_results_from_file_object(file_object)
            print(f"Inference Evaluation Metadata: \n{metadata}")
        except Exception as e:
            raise ValueError(f"Failed to load results from file object: {e}")
        if agent_filename == "":
            agent_filename = metadata.get("agent_filename", "unknown")
        if result_filename == "":
            result_filename = metadata.get("result_filename", "unknown")
        return await self._evaluate_results(tenant_id, task_name, results, metadata, datasets_path, output_file, official_validated, agent_filename, result_filename)

    async def _evaluate_results(self,
                               tenant_id: str,
                               task_name: str,
                               results: Any,
                               metadata: Dict[str, Any],
                               datasets_path: Optional[Path] = None,
                               output_file: Optional[Path] = None,
                               official_validated: bool = False,
                               agent_filename: str = "",
                               result_filename: str = "") -> Dict[str, Any]:
        """
        Internal method to evaluate benchmark results.
        
        - **Description**:
            - Internal method that handles the actual evaluation logic
            - Used by both evaluate() and evaluate_from_file_object() methods
            - Supports saving results to file and database
            
        - **Args**:
            - `task_name` (str): Name of the benchmark task
            - `results` (Any): Results data to evaluate
            - `metadata` (Dict[str, Any]): Metadata from the results file
            - `datasets_path` (Optional[Path]): Path to datasets directory
            - `output_file` (Optional[Path]): Output file for evaluation results
            
        - **Returns**:
            - `Dict[str, Any]`: Evaluation results and metadata
        """
        exp_id = metadata["exp_id"]
        
        # Get task functions
        task_functions = self._get_task_functions(task_name)
        if not task_functions or "evaluation" not in task_functions:
            raise ValueError(f"Task '{task_name}' does not have an evaluation function")
        
        # Initialize database writer if needed
        database_writer = await self._init_database_writer(tenant_id, str(exp_id))
        
        try:
            # Run evaluation
            evaluation_result = await task_functions["evaluation"](
                to_evaluate=results,
                datasets_path=str(datasets_path),
                metadata=metadata
            )
            
            # Save to output file if specified
            if output_file:
                output_file.parent.mkdir(parents=True, exist_ok=True)
                with open(output_file, "w") as f:
                    json.dump(evaluation_result, f, ensure_ascii=False, indent=2)
            
            result_info = json.dumps(evaluation_result, ensure_ascii=False, indent=2, default=str)            
            # Get final score from result
            final_score = 0.0
            if isinstance(evaluation_result, dict) and "final_score" in evaluation_result:
                try:
                    final_score = float(evaluation_result["final_score"])
                except (ValueError, TypeError):
                    final_score = 0.0
            
            print(f"Evaluation Result: \n{evaluation_result}")

            # Update database with evaluation status
            await self._update_benchmark_status(
                database_writer=database_writer,
                tenant_id=tenant_id,
                exp_id=str(exp_id),
                task_name=task_name,
                llm=metadata.get("llm", ""),
                agent=metadata.get("agent", ""),
                config_str=metadata.get("config", {}),
                status=BenchmarkStatus.EVALUATED,
                result_info=result_info,
                final_score=final_score,
                official_validated=official_validated,
                agent_filename=agent_filename,
                result_filename=result_filename
            )
            
            return {
                "success": True,
                "evaluation_result": evaluation_result,
                "output_file": str(output_file) if output_file else None
            }
            
        except Exception as e:
            # Update database with error status
            if database_writer:
                await self._update_benchmark_status(
                    database_writer=database_writer,
                    tenant_id=tenant_id,
                    exp_id=str(exp_id),
                    task_name=task_name,
                    llm=metadata.get("llm", ""),
                    agent=metadata.get("agent", ""),
                    config_str=metadata.get("config", {}),
                    status=BenchmarkStatus.ERROR,
                    error=str(e),
                    official_validated=official_validated,
                    agent_filename=agent_filename,
                    result_filename=result_filename
                )
            
            raise e
        finally:
            if database_writer:
                await database_writer.close()
    
    def list_available_tasks(self) -> list:
        """
        List all available benchmark tasks.
        
        - **Description**:
            - Returns a list of all available benchmark task names
            - Useful for discovering available benchmarks
            
        - **Returns**:
            - `list`: List of available task names
        """
        try:
            from agentsociety_benchmark.benchmarks import list_available_tasks
            return list_available_tasks()
        except ImportError:
            return []
    
    def get_task_info(self, task_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific task.
        
        - **Description**:
            - Returns detailed information about a benchmark task
            - Includes description, dependencies, and supported modes
            
        - **Args**:
            - `task_name` (str): Name of the benchmark task
            
        - **Returns**:
            - `Optional[Dict[str, Any]]`: Task information or None if not found
        """
        try:
            from agentsociety_benchmark.benchmarks import get_task_config
            return get_task_config(task_name)
        except ImportError:
            return None 