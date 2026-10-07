import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Union
from dataclasses import dataclass, asdict, field
import threading
import time
from pathlib import Path
from collections import defaultdict
from abc import ABC, abstractmethod

from llama_index.core import (
    VectorStoreIndex, 
    Document, 
    StorageContext,
    load_index_from_storage,
    Settings
)
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.llms import ChatMessage, LLM
from llama_index.core.embeddings import BaseEmbedding

# LLM imports
from llama_index.llms.openai import OpenAI
from llama_index.llms.ollama import Ollama
from llama_index.llms.vllm import Vllm
from llama_index.llms.huggingface import HuggingFaceLLM

# Embedding imports
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.embeddings.ollama import OllamaEmbedding

from helper import humanize_date
from llm.llm_model import *
from enum import Enum

class MemoryType(Enum):
    CONVERSATION = "conversation"
    REFLECTION = "reflection"
    CONCEPT = "concept"
    SUMMARY = "summary"

    def __str__(self):
        return str(self.value)

@dataclass
class MemoryEntry:
    """Represents a memory entry with metadata"""
    content: str
    timestamp: datetime
    memory_type: MemoryType
    person_id: str
    activity_id: Optional[str] = None
    tags: Optional[str] = ""

    def to_dict(self) -> Dict:
        return {
            **asdict(self),
            'timestamp': self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MemoryEntry':
        try:
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        except Exception as e:
            print(f"Error parsing timestamp: {e}, data: {data}")
            raise e
        return cls(**data)
    
    def __str__(self) -> str:
        timestamp_str = self.timestamp.strftime("%Y-%m-%d %H:%M")
        return f"[{timestamp_str}]: {self.content}"

