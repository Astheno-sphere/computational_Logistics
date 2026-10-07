
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional
from loguru import logger
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings
import os

import yaml

base_dir = os.path.dirname(os.path.abspath(__file__))


class VLLMSettings(BaseSettings):
    """Settings for VLLM server."""
    vllm_endpoint: str = os.getenv("VLLM_ENDPOINT", "")


class LLMServerSettings(BaseSettings):
    vllm: VLLMSettings = VLLMSettings()

    MODELS: list[dict[str, Any]] = [
        {
            "code": "mistral-7B-instruct-v0.3",
            "model": "RedHatAI/Mistral-7B-Instruct-v0.3-GPTQ-4bit",
            # "model": "mistralai/Mistral-7B-Instruct-v0.3",
            "llm_provider": "vllm",
            "api_key": os.getenv("VLLM_API_KEY", "EMPTY"),
            "api_url": os.getenv("VLLM_ENDPOINT", "http://127.0.0.1:1234/v1"),
            "metadata": {
                "context_window": 32768,
            }
        },
        {
            "code": "meta-llama-3-8b-instruct",
            # "model": "QuantFactory/Meta-Llama-3-8B-Instruct-GGUF",
            "model": "meta-llama/Meta-Llama-3-8B-Instruct",
            "llm_provider": "vllm",
            "api_key": os.getenv("VLLM_API_KEY", "EMPTY"),
            "api_url": os.getenv("VLLM_ENDPOINT", "http://127.0.0.1:1234/v1"),
            "metadata": {
                "context_window": 32768,
            }
        },
        {
            "code": "gpt-4",
            "model": "gpt-4",
            "llm_provider": "openai",
            "api_key": os.getenv("OPENAI_API_KEY"),
            # "base_url": "https://api.openai.com/v1",
            "api_url": None,
        },
        {
            "code": "llama3-8b-8192",
            "model": "llama3-8b-8192",
            "llm_provider": "vllm",
            "api_key": os.getenv("GROQ_API_KEY"),
            "api_url": "https://api.groq.com/openai/v1",
        },
        {
            "code": "qwen/qwen3-32b",
            "model": "qwen/qwen3-32b",
            "llm_provider": "vllm",
            "api_key": os.getenv("GROQ_API_KEY"),
            "api_url": "https://api.groq.com/openai/v1",
        },
        {
            "code": "openai/gpt-oss-120b",
            "model": "openai/gpt-oss-120b",
            "llm_provider": "vllm",
            "api_key": os.getenv("GROQ_API_KEY"),
            "api_url": "https://api.groq.com/openai/v1",
        },
        {
            "code": "deepseek-r1-distill-llama-70b",
            "model": "deepseek-r1-distill-llama-70b",
            "llm_provider": "vllm",
            "api_key": os.getenv("GROQ_API_KEY"),
            "api_url": "https://api.groq.com/openai/v1",
        },
        {
            "code": "llama-3.3-70b-versatile",
            "model": "llama-3.3-70b-versatile",
            "llm_provider": "vllm",
            "api_key": os.getenv("GROQ_API_KEY"),
            "api_url": "https://api.groq.com/openai/v1",
        },
    ]

def merge_configs(*config_paths: str) -> Dict[str, Any]:
    """Merge multiple YAML files, with later files overriding earlier ones."""
    merged_config = {}
    
    for path in config_paths:
        if Path(path).exists():
            with open(path, 'r') as f:
                config = yaml.safe_load(f)
                if config:
                    merged_config = deep_merge(merged_config, config)
    
    return merged_config

def deep_merge(base: Dict, override: Dict) -> Dict:
    """Deep merge two dictionaries."""
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result


class WorkdirPathResolutionMixin:
    """Mixin to handle path resolution in nested models."""
    
    # Define path fields at class level
    _in_workdir_path_fields: ClassVar[List[str]] = []
    
    def resolve_paths(self, workdir: Path):
        """Resolve relative paths to absolute paths."""
        for field_name in self._in_workdir_path_fields:
            if hasattr(self, field_name):
                value = getattr(self, field_name)
                if value is not None and not Path(value).is_absolute():
                    resolved_path = workdir / value
                    setattr(self, field_name, str(resolved_path))


class ServerConfig(BaseSettings, WorkdirPathResolutionMixin):
    # HTTP settings
    http_host: str = "localhost"
    http_port: int = 8002

    # GAMA websocket settings
    gama_ws_url: str = "ws://localhost:3001"


class WorldConfig(BaseSettings, WorkdirPathResolutionMixin):
    # General settings
    geo_crs: str = "EPSG:4326"
    geo_projection: str = "EPSG:3857"
    # Grid settings
    grid_size: int = 1000 # 1km
    time_step: int = 900 # 15 minutes


class GTFSConfig(BaseSettings, WorkdirPathResolutionMixin):
    _in_workdir_path_fields: ClassVar[List[str]] = ["solari_cache_file"]

    mode: str = "SOLARI" # SOLARI or OTP

    # GTFS settings
    gtfs_file: str = os.path.join(base_dir, "../data/gtfs/")
    gtfs_modality_name_map: dict[str, str] = {
        "0": "T1/Tram",
        "1": "Metro",
        "3": "Bus",
        "6": "Teleo",
    }

    # RAPTOR provider settings
    solari_endpoint: str = "http://localhost:8000/v1/plan"
    solari_cache_file: str = "raptor_cache.pickle"

    # OTP provider settings
    otp_endpoint: str = "http://localhost:8080/otp/transmodel/v3"

    # number of cached itineraries per grid cell
    n_trip_in_grid: int = 5
    cache_enabled: bool = True
    recursion_search_depth: int = 0  # 0 means no recursion, 1 means one level of recursion
    trip_query_range: list[int] = [0, 15, -15]  # in minutes, relative to the departure time
    max_trip_candidates: int = 5 # maximum number of trip candidates to be selected
    fixed_day: Optional[str] = None


class DataConfig(BaseSettings, WorkdirPathResolutionMixin):
    _in_workdir_path_fields: ClassVar[List[str]] = ["population_cache_prefix", "state_file"]

    # Agent settings
    population_max_size: Optional[int] = 100 + 20 # buffer 20 agents
    population_cache_prefix: str = "./population_"
    state_file: str = "./state.json"
    number_of_llm_based_agents: Optional[int] = 0

    # Synthesis settings
    synthetic_dir: str = os.path.join(base_dir, "../data/po_toulouse.big")
    synthetic_file_prefix: str = "toulouse_"
    # Debug
    debug_people_ids: Optional[list[str]] = None


class AgentConfig(BaseSettings, WorkdirPathResolutionMixin):
    _in_workdir_path_fields: ClassVar[List[str]] = ["long_term_memory_storage_dir", "chat_log_dir"]

    llm_model: str = "mistral-7B-instruct-v0.3"
    embedding_model: Optional[str] = None
    chat_log_dir: str = "chat_logs"
    long_term_memory_storage_dir: str = "long_term_memory"
    long_term_memory_filter_by_datetime: bool = False
    long_term_memory_enabled: bool = True
    long_term_max_entries_query: int = 10
    long_term_max_days_query: int = 30
    long_term_reflect_interval: int = 6 * 3600  # 6 hours

    long_term_retrieval__sim_weight: float = 0.4
    long_term_retrieval__keyword_weight: float = 0.3
    long_term_retrieval__time_weight: float = 0.3
    long_term_retrieval__default_reflection_importance_score: float = 0.2
    long_term_retrieval__time_decay: float = 0.7

    long_term_self_reflect_enabled: bool = False
    long_term_self_reflect_interval_days: int = 3
    long_term_self_reflect_window_days: int = 5

    llm_params: dict[str, Any] = {
        "temperature": 0,
        "top_p": 1.0,
        "max_tokens": 4096,
    }
    llm_retry_count: int = 3
    llm_retry_delay: int = 5  # seconds

    # Scheduler settings
    reschedule_activity__version: int = 2
    reschedule_activity_departure_time: bool = True
    reschedule_transition_ratio: float = 0.75
    reschedule_activity_v2__k: float = 0.02
    max_reschedule_amount: int = 3600  # 1 hour
    pre_schedule_duration: int = 0

    quantify_time_window: bool = True
    reflection_custom_guidelines: Optional[str] = None
    travel_plan_custom_guidelines: Optional[str] = None

    # Remote LLM settings
    remote_llm_max_concurrent_requests: Optional[int] = 20


class AppConfig(BaseSettings, WorkdirPathResolutionMixin):
    _in_workdir_path_fields: ClassVar[List[str]] = ["history_file_v2", "log_file"]
    
    # History settings
    history_file: str = "history.jsonl"
    history_file_v2: str = "history_stream_log.jsonl"

    # Logging settings
    log_file: str = "app.log"
    log_level: str = "DEBUG"


class Settings(LLMServerSettings):
    app: AppConfig = AppConfig()
    server: ServerConfig = ServerConfig()
    data: DataConfig = DataConfig()
    world: WorldConfig = WorldConfig()
    gtfs: GTFSConfig = GTFSConfig()
    agent: AgentConfig = AgentConfig()

    # Directory settings
    workdir: Path = Field(default_factory=lambda: Path.cwd())

    # @field_validator('workdir', mode='before')
    # @classmethod
    # def resolve_workdir(cls, v):
    #     """Ensure workdir is an absolute Path."""
    #     return Path(v).resolve()
    
    @model_validator(mode='after')
    def resolve_all_paths(self): 
        # This will only be triggered if you instantiate Settings via pydantic's validation process,
        # e.g., Settings(**data), not when you subclass or access attributes directly.
        # If you use Settings.from_yaml_files or FactorySettings, it will be triggered.
        # If you instantiate Settings without validation, it won't.
        for field_name, field_value in self.__dict__.items():
            if isinstance(field_value, WorkdirPathResolutionMixin):
                field_value.resolve_paths(self.workdir)
        return self
    
    def _resolve_nested_paths(self, model_instance: BaseModel, path_fields: list):
        """Resolve paths in a nested model instance."""
        for path_field in path_fields:
            if hasattr(model_instance, path_field):
                current_value = getattr(model_instance, path_field)
                if current_value is not None and not Path(current_value).is_absolute():
                    resolved_path = self.workdir / current_value
                    setattr(model_instance, path_field, str(resolved_path))

    @classmethod
    def from_yaml_files(cls, *yaml_paths: str, workdir: str = None) -> 'Settings':
        """Load and merge multiple YAML files."""
        merged_data = merge_configs(*yaml_paths)
        if workdir:
            merged_data['workdir'] = Path(workdir).resolve()

        # workdir = Path(yaml_paths[0]).parent.resolve()
        # merged_data['workdir'] = workdir
        assert 'workdir' in merged_data, "Work directory must be specified in the configuration files."

        _self = cls(**merged_data)
        # _self.resolve_all_paths()
        return _self


class FactorySettings:
    _instance: Optional[Settings] = None

    @classmethod
    def get(cls, workdir: str=None) -> Settings:
        if cls._instance is not None:
            return cls._instance
        
        base_config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "config/config.yaml",
        )
        yaml_files = [base_config_path]
        config_file_path = os.environ.get("APP_CONFIG_PATH")
        if config_file_path and os.path.isfile(config_file_path):
            yaml_files.append(config_file_path)

        cls._instance = Settings.from_yaml_files(*yaml_files, workdir=workdir)

        logger.info(f"Settings loaded from: {yaml_files}")
        logger.info(f"All settings: {cls._instance.model_dump_json(indent=2)}")
        return cls._instance
    
    def __getattribute__(self, name):
        # Handle special methods and private attributes directly
        if name.startswith('_') or name in ('get', 'force_reload', 'force_reload_paths'):
            return super().__getattribute__(name)
        
        # Delegate all other attributes to the Settings instance
        return getattr(self.get(), name)
    
    @classmethod
    def force_reload(cls) -> Settings:
        """Force reload the settings."""
        cls._instance = None
        return cls.get()
    
    @classmethod
    def force_reload_paths(cls, workdir: str) -> Settings:
        cls._instance = None
        settings = cls.get(workdir=workdir)
        return settings


settings = FactorySettings()

