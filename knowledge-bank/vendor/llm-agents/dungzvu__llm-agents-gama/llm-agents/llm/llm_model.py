from typing import Dict, Any
from dataclasses import dataclass

from llama_index.core.llms import LLM
from llama_index.core.embeddings import BaseEmbedding

# LLM imports
from llama_index.llms.openai import OpenAI
from llama_index.llms.ollama import Ollama
from llama_index.llms.vllm import VllmServer
from llama_index.llms.huggingface import HuggingFaceLLM

# Embedding imports
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.embeddings.ollama import OllamaEmbedding

from llm.vllm_server import OpenAIvLLM


class LLMConfig:
    """Configuration for different LLM providers"""
    
    @staticmethod
    def create_openai_llm(model: str = "gpt-3.5-turbo", **kwargs) -> OpenAI:
        """Create OpenAI LLM"""
        return OpenAI(model=model, **kwargs)
    
    @staticmethod
    def create_vllm_llm(model: str, tensor_parallel_size: int = 1, **kwargs) -> OpenAIvLLM:
        """Create vLLM instance"""
        return OpenAIvLLM(
            model=model,
            tensor_parallel_size=tensor_parallel_size,
            **kwargs
        )
    
    @staticmethod
    def create_ollama_llm(model: str = "llama2", base_url: str = "http://localhost:11434", **kwargs) -> Ollama:
        """Create Ollama LLM"""
        return Ollama(
            model=model,
            base_url=base_url,
            **kwargs
        )
    
    @staticmethod
    def create_huggingface_llm(model_name: str, **kwargs) -> HuggingFaceLLM:
        """Create HuggingFace LLM"""
        return HuggingFaceLLM(
            model_name=model_name,
            **kwargs
        )
    
    @staticmethod
    def create_custom_llm(llm_instance: LLM) -> LLM:
        """Use custom LLM instance"""
        return llm_instance


class EmbeddingConfig:
    """Configuration for different embedding providers"""
    
    @staticmethod
    def create_openai_embedding(model: str = "text-embedding-ada-002", **kwargs) -> OpenAIEmbedding:
        """Create OpenAI embedding"""
        return OpenAIEmbedding(model=model, **kwargs)
    
    @staticmethod
    def create_huggingface_embedding(model_name: str = "sentence-transformers/all-MiniLM-L6-v2", **kwargs) -> HuggingFaceEmbedding:
        """Create HuggingFace embedding"""
        return HuggingFaceEmbedding(model_name=model_name, **kwargs)
    
    @staticmethod
    def create_ollama_embedding(model_name: str = "llama2", base_url: str = "http://localhost:11434", **kwargs) -> OllamaEmbedding:
        """Create Ollama embedding"""
        return OllamaEmbedding(
            model_name=model_name,
            base_url=base_url,
            **kwargs
        )
    
    @staticmethod
    def create_custom_embedding(embedding_instance: BaseEmbedding) -> BaseEmbedding:
        """Use custom embedding instance"""
        return embedding_instance


@dataclass
class ModelConfig:
    """Configuration for LLM and embedding models"""
    llm_provider: str  # 'openai', 'vllm', 'ollama', 'huggingface', 'custom'
    llm_model: str
    llm_kwargs: Dict[str, Any]
    
    embedding_provider: str  # 'openai', 'huggingface', 'ollama', 'custom'
    embedding_model: str
    embedding_kwargs: Dict[str, Any]
    
    @classmethod
    def create_openai_config(cls, llm_model: str = "gpt-3.5-turbo", embedding_model: str = "text-embedding-ada-002", **kwargs) -> 'ModelConfig':
        """Create OpenAI configuration"""
        return cls(
            llm_provider="openai",
            llm_model=llm_model,
            llm_kwargs=kwargs or {},
            embedding_provider="openai",
            embedding_model=embedding_model,
            embedding_kwargs={}
        )
    
    @classmethod
    def create_vllm_config(cls, llm_model: str, tensor_parallel_size: int = 1, embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2", **kwargs) -> 'ModelConfig':
        """Create vLLM configuration"""
        return cls(
            llm_provider="vllm",
            llm_model=llm_model,
            llm_kwargs={"tensor_parallel_size": tensor_parallel_size, **kwargs},
            embedding_provider="huggingface",
            embedding_model=embedding_model,
            embedding_kwargs={}
        )
    
    @classmethod
    def create_ollama_config(cls, llm_model: str = "llama2", embedding_model: str = "llama2", base_url: str = "http://localhost:11434") -> 'ModelConfig':
        """Create Ollama configuration"""
        return cls(
            llm_provider="ollama",
            llm_model=llm_model,
            llm_kwargs={"base_url": base_url},
            embedding_provider="ollama",
            embedding_model=embedding_model,
            embedding_kwargs={"base_url": base_url}
        )
    
    @classmethod
    def create_huggingface_config(cls, llm_model: str, embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2") -> 'ModelConfig':
        """Create HuggingFace configuration"""
        return cls(
            llm_provider="huggingface",
            llm_model=llm_model,
            llm_kwargs={},
            embedding_provider="huggingface",
            embedding_model=embedding_model,
            embedding_kwargs={}
        )
    
    def create_llm(self, use_async: bool = True) -> LLM:
        """Create LLM instance based on configuration"""
        if self.llm_provider == "openai":
            return LLMConfig.create_openai_llm(self.llm_model, use_async=use_async, **self.llm_kwargs)
        elif self.llm_provider == "vllm":
            return LLMConfig.create_vllm_llm(self.llm_model, use_async=use_async, **self.llm_kwargs)
        elif self.llm_provider == "ollama":
            return LLMConfig.create_ollama_llm(self.llm_model, use_async=use_async, **self.llm_kwargs)
        elif self.llm_provider == "huggingface":
            return LLMConfig.create_huggingface_llm(self.llm_model, use_async=use_async, **self.llm_kwargs)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")
    
    def create_embedding(self) -> BaseEmbedding:
        """Create embedding instance based on configuration"""
        if self.embedding_provider == "openai":
            return EmbeddingConfig.create_openai_embedding(self.embedding_model, **self.embedding_kwargs)
        elif self.embedding_provider == "huggingface":
            return EmbeddingConfig.create_huggingface_embedding(self.embedding_model, **self.embedding_kwargs)
        elif self.embedding_provider == "ollama":
            return EmbeddingConfig.create_ollama_embedding(self.embedding_model, **self.embedding_kwargs)
        else:
            raise ValueError(f"Unsupported embedding provider: {self.embedding_provider}")
