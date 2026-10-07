"""Pydantic schema for AEC Knowledge Graph nodes and edges.

Source-of-truth lives in JSONL files under data/nodes/ and data/edges/.
This module enforces validation on load.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    THEORIST = "Theorist"
    MOVEMENT = "Movement"
    PROJECT = "Project"
    STANDARD = "Standard"
    METRIC = "Metric"
    PATTERN = "Pattern"
    TYPOLOGY = "Typology"
    TOOL = "Tool"
    SKILL = "Skill"


class EdgeType(str, Enum):
    INFLUENCED = "INFLUENCED"
    AUTHORED = "AUTHORED"
    BELONGS_TO = "BELONGS_TO"
    EXEMPLIFIES = "EXEMPLIFIES"
    CERTIFIED_BY = "CERTIFIED_BY"
    USES_TOOL = "USES_TOOL"
    MEASURED_BY = "MEASURED_BY"
    SUPERSEDES = "SUPERSEDES"
    REFERENCES = "REFERENCES"
    MENTIONS = "MENTIONS"


class Node(BaseModel):
    """A node in the AEC knowledge graph.

    Type-specific properties are kept on the same flat model for
    Kuzu schema simplicity. Unused properties are simply None.
    """

    id: str = Field(..., description="Stable slug, e.g. 'theorist:jane-jacobs'.")
    type: NodeType
    name: str
    aliases: list[str] = Field(default_factory=list)
    summary: str = ""

    # Person-specific
    born: Optional[int] = None
    died: Optional[int] = None
    nationality: Optional[str] = None

    # Project / Movement / Standard
    year: Optional[int] = None
    location: Optional[str] = None
    scope: Optional[str] = None

    # Metric
    unit: Optional[str] = None
    typical_min: Optional[float] = None
    typical_max: Optional[float] = None

    # Skill
    plugin: Optional[str] = None        # 'urban-design' | 'architect' | 'computational-design'
    category: Optional[str] = None      # foundation | analysis | design | technical | production
    invocation: Optional[str] = None    # auto | user-only

    sources: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class Edge(BaseModel):
    source: str
    target: str
    type: EdgeType
    note: str = ""
    year: Optional[int] = None
    sources: list[str] = Field(default_factory=list)


# Property keys that map onto Kuzu node tables (stable order matters for INSERT).
NODE_PROPS: tuple[str, ...] = (
    "id", "name", "summary", "aliases", "born", "died", "nationality",
    "year", "location", "scope", "unit", "typical_min", "typical_max",
    "sources", "tags",
)
EDGE_PROPS: tuple[str, ...] = ("note", "year", "sources")
