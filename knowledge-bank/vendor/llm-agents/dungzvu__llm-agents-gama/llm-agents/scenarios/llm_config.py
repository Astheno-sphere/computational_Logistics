from llm.llm_model import ModelConfig
from settings import settings


def create_llm_config_from_settings() -> ModelConfig:
    """Create LLM configuration based on settings"""
    model = settings.agent.llm_model
    cfg = next((m for m in settings.MODELS if m["code"] == model))
    assert cfg, f"Model {model} not found in settings.MODELS"

    llm_provider = cfg.get("llm_provider", None)
    assert llm_provider, f"Model {model} does not have a valid llm_provider"

    if llm_provider == "openai":
        return ModelConfig.create_openai_config(
            llm_model=cfg["model"],
            embedding_model=cfg.get("embedding_model") or "text-embedding-ada-002",
            api_key=cfg.get("api_key", None),
            api_base=cfg.get("api_url", None),
            temperature=settings.agent.llm_params.get("temperature", 0),
            max_tokens=settings.agent.llm_params.get("max_tokens", 200),
        )
    if llm_provider == "vllm":
        return ModelConfig.create_vllm_config(
            llm_model=cfg["model"],
            embedding_model=cfg.get("embedding_model") or "sentence-transformers/all-MiniLM-L6-v2",
            temperature=settings.agent.llm_params.get("temperature", 0),
            max_new_tokens=settings.agent.llm_params.get("max_tokens", 200),
            tensor_parallel_size=settings.agent.llm_params.get("tensor_parallel_size", 1),
            api_url=cfg["api_url"],
            api_key=cfg.get("api_key", None),
        )
    raise ValueError(f"Unsupported LLM provider: {llm_provider}")
