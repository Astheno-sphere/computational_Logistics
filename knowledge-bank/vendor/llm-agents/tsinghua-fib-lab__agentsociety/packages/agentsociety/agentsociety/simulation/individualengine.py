import asyncio
import os
import traceback
from datetime import datetime, timezone
from multiprocessing import cpu_count
from typing import Optional

import yaml
from fastembed import SparseTextEmbedding

from ..agent import (
    AgentToolbox,
    IndividualAgentBase,
)
from ..agent.memory_config_generator import (
    MemoryConfigGenerator,
    default_memory_config_solver,
)
from ..configs import (
    IndividualConfig,
)
from ..environment import EnvironmentStarter
from ..llm import LLM
from ..logger import get_logger, set_logger_level
from ..memory import Memory
from ..message import MessageInterceptor
from ..storage import DatabaseWriter
from ..storage.type import (
    StorageExpInfo,
)
from ..taskloader import TaskLoader
from .type import ExperimentStatus

__all__ = ["IndividualEngine"]

MIN_ID = 1
MAX_ID = 1000000000


class IndividualEngine:
    def __init__(
        self,
        config: IndividualConfig,
        tenant_id: str = "",
    ) -> None:
        self._config = config
        self.tenant_id = tenant_id
        self._individual_config = config.individual
        if self._individual_config.memory_config_func is None:
            self._individual_config.memory_config_func = default_memory_config_solver

        self._task_loader_config = config.task_loader
        self._task_loader = None

        # ====================
        # Initialize the logger
        # ====================
        set_logger_level(self._config.logging_level.upper())

        self.exp_id = str(config.id)
        get_logger().debug(
            f"Creating TaskSolverEngine with config: {self._config.model_dump()} as exp_id={self.exp_id}"
        )

        # typing definition
        self._llm: Optional[LLM] = None
        self._environment: Optional[EnvironmentStarter] = None
        self._message_interceptor: Optional[MessageInterceptor] = None
        self._database_writer: Optional[DatabaseWriter] = None
        self._embedding: Optional[SparseTextEmbedding] = None
        self._id2agent: dict[int, IndividualAgentBase] = {}
        yaml_config = yaml.dump(
            self._config.model_dump(
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
            allow_unicode=True,
        )
        self._exp_info: StorageExpInfo = StorageExpInfo(
            id=self.exp_id,
            tenant_id=self.tenant_id,
            name=self._config.name,
            num_day=-1,
            status=0,
            cur_day=-1,
            cur_t=-1,
            config=yaml_config,
            error="",
            input_tokens=0,
            output_tokens=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    async def _init_embedding(self):
        """Initialize embedding model with timeout."""
        try:
            # Create a task for embedding initialization
            init_task = asyncio.create_task(self._init_embedding_task())

            # Wait for the task with timeout
            try:
                await asyncio.wait_for(init_task, timeout=120)  # 2 minutes timeout
            except asyncio.TimeoutError:
                get_logger().error(
                    "Embedding model initialization timed out after 2 minutes. "
                    "Please check your HuggingFace connection and try again."
                )
                raise

        except Exception as e:
            get_logger().error(f"Failed to initialize embedding model: {str(e)}")
            raise

    async def _init_embedding_task(self):
        """Actual embedding initialization task."""
        self._embedding = SparseTextEmbedding(
            "Qdrant/bm25",
            cache_dir=os.path.join(self._config.env.home_dir, "huggingface_cache"),
            threads=cpu_count(),
        )
        get_logger().info("Embedding model initialized successfully")

    async def init(self):
        """Initialize all the components"""
        # ====================
        # Initialize the pgsql writer
        # ====================
        if self._config.env.db.enabled:
            get_logger().info("-----Initializing database writer...")
            self._database_writer = DatabaseWriter(
                self.tenant_id,
                self.exp_id,
                self._config.env.db,
                self._config.env.home_dir,
            )
            await self._database_writer.init()  # type: ignore
            get_logger().info("-----Database writer initialized")
            # save to local
            await self._database_writer.update_exp_info(self._exp_info)

        try:
            # ====================
            # Initialize the LLM
            # ====================
            get_logger().info("-----Initializing LLM model...")
            self._llm = LLM(self._config.llm)
            get_logger().info("-----LLM initialized")

            # ====================
            # Initialize the embedding
            # ====================
            get_logger().info("-----Initializing embedding model...")
            await self._init_embedding()
            assert self._embedding is not None, "Embedding is not initialized"
            get_logger().info("-----Embedding initialized")

            # ======================================
            # Initialize agents - generate agents from the config
            # ======================================
            agents = []
            defined_ids = set()
            concurrency = self._individual_config.number
            get_logger().info(f"-----Initializing {concurrency} agents for solver...")

            # ====================================
            # Initialize the agent objects
            # ====================================
            agent_toolbox = AgentToolbox(
                llm=self._llm,
                environment=None,
                messager=None,
                embedding=self._embedding,
                database_writer=self._database_writer,
            )
            if self._individual_config.tools is not None:
                for tool in self._individual_config.tools:
                    agent_toolbox.add_tool(tool)

            get_logger().info("-----Initializing the agents...")
            if self._individual_config.memory_from_file is not None:
                agent_class = self._individual_config.agent_class
                agent_params = self._individual_config.agent_params
                if agent_params is None:
                    agent_params = agent_class.ParamsType() # type: ignore
                else:
                    agent_params = agent_class.ParamsType.model_validate(agent_params) # type: ignore
                blocks = self._individual_config.blocks
                # Create generator
                generator = MemoryConfigGenerator(
                    self._individual_config.memory_config_func,  # type: ignore
                    self._individual_config.agent_class.StatusAttributes,  # type: ignore
                    self._individual_config.number,
                    self._individual_config.memory_from_file,
                    (
                        self._individual_config.memory_distributions
                        if self._individual_config.memory_distributions is not None
                        else {}
                    ),
                    self._config.env.s3,
                )
                # Get agent data from file
                agent_data = generator.get_agent_data_from_file()
                # Extract IDs from agent data
                for agent_datum in agent_data:
                    agent_id = agent_datum.get("id")
                    assert (
                        agent_id is not None
                    ), "id is required in memory_from_file"
                    assert (
                        agent_id >= MIN_ID
                    ), f"id {agent_id} is less than MIN_ID {MIN_ID}"
                    assert (
                        agent_id <= MAX_ID
                    ), f"id {agent_id} is greater than MAX_ID {MAX_ID}"
                    assert (
                        agent_id not in defined_ids
                    ), f"id {agent_id} is already defined"
                    defined_ids.add(agent_id)
                    agents.append(
                        (
                            agent_id,
                            agent_class,
                            generator,
                            agent_data.index(agent_datum),
                            agent_params,
                            blocks,
                        )
                    )
            else:
                agent_class = self._individual_config.agent_class
                agent_params = self._individual_config.agent_params
                if agent_params is None:
                    agent_params = agent_class.ParamsType() # type: ignore
                else:
                    agent_params = agent_class.ParamsType.model_validate(agent_params) # type: ignore
                blocks = self._individual_config.blocks
                generator = MemoryConfigGenerator(
                    self._individual_config.memory_config_func,  # type: ignore
                    self._individual_config.agent_class.StatusAttributes,  # type: ignore
                    self._individual_config.number,
                    None,
                    self._individual_config.memory_distributions if self._individual_config.memory_distributions is not None else {},
                    self._config.env.s3,
                )
                for i in range(concurrency):
                    agents.append(
                        (
                            i,
                            agent_class,
                            generator,
                            i,
                            agent_params,
                            blocks,
                        )
                    )
            
            generator = MemoryConfigGenerator(
                self._individual_config.memory_config_func,  # type: ignore
                self._individual_config.agent_class.StatusAttributes,  # type: ignore
                self._individual_config.number,
                self._individual_config.memory_from_file,
                (
                    self._individual_config.memory_distributions
                    if self._individual_config.memory_distributions is not None
                    else {}
                ),
                self._config.env.s3,
            )
            for agent_init in agents:
                id, agent_class, generator, index_for_generator, agent_params, blocks = agent_init
                memory_config = generator.generate(index_for_generator)

                # Initialize Memory with the unified config
                memory_init = Memory(
                    environment=None,
                    embedding=self._embedding,
                    memory_config=memory_config,
                )
                # # build blocks
                if blocks is not None:
                    blocks = [
                        block_type(
                            toolbox=agent_toolbox,
                            agent_memory=memory_init,
                            block_params=block_type.ParamsType.model_validate(
                                block_params
                            ),
                        )
                        for block_type, block_params in blocks.items()
                    ]
                else:
                    blocks = None
                # build agent
                agent = agent_class(
                    id=id,
                    name=f"{agent_class.__name__}_{id}",
                    toolbox=agent_toolbox,
                    memory=memory_init,
                    agent_params=agent_params,
                    blocks=blocks,
                )
                self._id2agent[id] = agent

            embedding_tasks = []
            for agent in self._id2agent.values():
                embedding_tasks.append(agent.memory.initialize_embeddings())
            await asyncio.gather(*embedding_tasks)
            get_logger().info("-----Agents initialized")

            # ===================================
            # Initialize the task loader
            # ===================================
            get_logger().info("-----Initializing task loader...")
            self._task_loader = TaskLoader(
                self._config.task_loader.task_type,
                self._config.task_loader.file_path,
                self._config.task_loader.shuffle,
            )
            get_logger().info("-----Task loader initialized")

            # ===================================
            # save the experiment info
            # ===================================
            await self._save_exp_info()
            get_logger().info("-----Experiment info saved")

        except Exception as e:
            get_logger().error(f"Init error: {str(e)}\n{traceback.format_exc()}")
            self._exp_info.status = ExperimentStatus.ERROR.value
            self._exp_info.error = str(e)
            await self._save_exp_info()

            raise e
        get_logger().info("-----Individual engine initialized")

    async def run(self):
        """
        Run the task solver with concurrent execution and progress tracking.
        - **Description**:
            - Distributes tasks to agents in rounds
            - Each round assigns N tasks to N agents concurrently
            - Provides progress updates at the beginning and end of each round
            - Collects only new task results after each round

        - **Args**: None

        - **Returns**: None
        """
        get_logger().info("Running individual engine...")
        self._task_loader.reset_all() # type: ignore
        
        concurrency = len(self._id2agent)
        total_tasks = len(self._task_loader) # type: ignore
        get_logger().info(f"Starting task execution with {concurrency} agents for {total_tasks} tasks")
        
        if total_tasks == 0:
            get_logger().info("No tasks to execute")
            return
        
        round_num = 0
        agent_ids = list(self._id2agent.keys())
        self._exp_info.status = ExperimentStatus.RUNNING
        await self._save_exp_info()
        
        try:
            while self._task_loader.get_pending_count() > 0: # type: ignore
                self.llm.clear_log_list()
                round_num += 1
                
                # Start of round progress
                completed_before = self._task_loader.get_completed_count() # type: ignore
                progress = (completed_before / total_tasks) * 100
                get_logger().info(f"Round {round_num} starting - Progress: {completed_before}/{total_tasks} ({progress:.1f}%)")
                
                # Get N tasks for N agents
                tasks = self._task_loader.next(concurrency) # type: ignore
                if not tasks:
                    break
                
                # Ensure tasks is a list
                if not isinstance(tasks, list):
                    tasks = [tasks]
                
                # Execute tasks concurrently
                task_coroutines = []
                for i, task in enumerate(tasks):
                    agent_id = agent_ids[i]
                    agent = self._id2agent[agent_id]
                    
                    # Assign this task to the specific agent
                    task.assign_to_agent(agent_id)
                    
                    task_coroutines.append(agent.run(task))
                
                await asyncio.gather(*task_coroutines)

                # Collect llm logs
                llm_log=self.llm.get_log_list()
                for log in llm_log:
                    self._exp_info.input_tokens += log.get("input_tokens", 0)
                    self._exp_info.output_tokens += log.get("output_tokens", 0)
                
                # Collect only new task results for this round
                task_results = self._task_loader.get_task_results() # type: ignore
                await self._database_writer.write_task_result(task_results) # type: ignore
                
                # End of round progress
                completed_after = self._task_loader.get_completed_count() # type: ignore
                pending_after = self._task_loader.get_pending_count() # type: ignore
                uncollected_completed = self._task_loader.get_uncollected_completed_count() # type: ignore
                progress = (completed_after / total_tasks) * 100
                get_logger().info(
                    f"Round {round_num} completed - Progress: {completed_after}/{total_tasks} ({progress:.1f}%) "
                    f"[Completed this round: {completed_after - completed_before}, Remaining: {pending_after}, "
                    f"New results collected: {len(task_results)}, Uncollected completed: {uncollected_completed}]"
                )

                # save the experiment info
                await self._save_exp_info()
            
            self._exp_info.status = ExperimentStatus.FINISHED
            await self._save_exp_info()
            get_logger().info("-----Individual engine completed successfully")
        except Exception as e:
            get_logger().error(f"Run error: {str(e)}\n{traceback.format_exc()}")
            self._exp_info.status = ExperimentStatus.ERROR
            self._exp_info.error = str(e)
            await self._save_exp_info()
            raise e

    async def close(self):
        """Close all the components"""
        get_logger().info("Closing...")
        close_tasks = []
        for agent in self._id2agent.values():
            close_tasks.append(agent.close())  # type:ignore
        await asyncio.gather(*close_tasks)
        get_logger().info("Closed")

    @property
    def config(self):
        return self._config
    
    @property
    def database(self):
        assert self._database_writer is not None, "database writer is not initialized"
        return self._database_writer

    @property
    def llm(self):
        assert self._llm is not None, "llm is not initialized"
        return self._llm

    @property
    def enable_database(self):
        return self._config.env.db.enabled

    @property
    def database_writer(self):
        assert self._database_writer is not None, "database writer is not initialized"
        return self._database_writer

    async def _save_exp_info(self) -> None:
        """Async save experiment info to YAML file and pgsql"""
        self._exp_info.updated_at = datetime.now(timezone.utc)
        if self.enable_database:
            assert self._database_writer is not None
            await self._database_writer.update_exp_info(self._exp_info)  # type: ignore
