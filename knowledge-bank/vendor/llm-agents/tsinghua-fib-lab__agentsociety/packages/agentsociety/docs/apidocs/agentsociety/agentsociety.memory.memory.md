# {py:mod}`agentsociety.memory.memory`

```{py:module} agentsociety.memory.memory
```

```{autodoc2-docstring} agentsociety.memory.memory
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`KVMemory <agentsociety.memory.memory.KVMemory>`
  - ```{autodoc2-docstring} agentsociety.memory.memory.KVMemory
    :summary:
    ```
* - {py:obj}`MemoryNode <agentsociety.memory.memory.MemoryNode>`
  - ```{autodoc2-docstring} agentsociety.memory.memory.MemoryNode
    :summary:
    ```
* - {py:obj}`StreamMemory <agentsociety.memory.memory.StreamMemory>`
  - ```{autodoc2-docstring} agentsociety.memory.memory.StreamMemory
    :summary:
    ```
* - {py:obj}`Memory <agentsociety.memory.memory.Memory>`
  - ```{autodoc2-docstring} agentsociety.memory.memory.Memory
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.memory.memory.__all__>`
  - ```{autodoc2-docstring} agentsociety.memory.memory.__all__
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.memory.memory.__all__
:value: >
   ['KVMemory', 'StreamMemory', 'Memory']

```{autodoc2-docstring} agentsociety.memory.memory.__all__
```

````

`````{py:class} KVMemory(memory_config: agentsociety.agent.memory_config_generator.MemoryConfig, embedding: fastembed.SparseTextEmbedding)
:canonical: agentsociety.memory.memory.KVMemory

```{autodoc2-docstring} agentsociety.memory.memory.KVMemory
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.memory.memory.KVMemory.__init__
```

````{py:method} initialize_embeddings() -> None
:canonical: agentsociety.memory.memory.KVMemory.initialize_embeddings
:async:

```{autodoc2-docstring} agentsociety.memory.memory.KVMemory.initialize_embeddings
```

````

````{py:method} _generate_semantic_text(key: str, value: typing.Any) -> str
:canonical: agentsociety.memory.memory.KVMemory._generate_semantic_text

```{autodoc2-docstring} agentsociety.memory.memory.KVMemory._generate_semantic_text
```

````

````{py:method} search(query: str, top_k: int = 3, filter: typing.Optional[dict] = None) -> str
:canonical: agentsociety.memory.memory.KVMemory.search
:async:

```{autodoc2-docstring} agentsociety.memory.memory.KVMemory.search
```

````

````{py:method} should_embed(key: str) -> bool
:canonical: agentsociety.memory.memory.KVMemory.should_embed

```{autodoc2-docstring} agentsociety.memory.memory.KVMemory.should_embed
```

````

````{py:method} get(key: typing.Any, default_value: typing.Optional[typing.Any] = None) -> typing.Any
:canonical: agentsociety.memory.memory.KVMemory.get
:async:

```{autodoc2-docstring} agentsociety.memory.memory.KVMemory.get
```

````

````{py:method} update(key: typing.Any, value: typing.Any, mode: typing.Union[typing.Literal[replace], typing.Literal[merge]] = 'replace') -> None
:canonical: agentsociety.memory.memory.KVMemory.update
:async:

```{autodoc2-docstring} agentsociety.memory.memory.KVMemory.update
```

````

````{py:method} export(keys: list[str]) -> dict[str, typing.Any]
:canonical: agentsociety.memory.memory.KVMemory.export
:async:

```{autodoc2-docstring} agentsociety.memory.memory.KVMemory.export
```

````

`````

`````{py:class} MemoryNode
:canonical: agentsociety.memory.memory.MemoryNode

```{autodoc2-docstring} agentsociety.memory.memory.MemoryNode
```

````{py:attribute} topic
:canonical: agentsociety.memory.memory.MemoryNode.topic
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.memory.memory.MemoryNode.topic
```

````

````{py:attribute} day
:canonical: agentsociety.memory.memory.MemoryNode.day
:type: int
:value: >
   None

```{autodoc2-docstring} agentsociety.memory.memory.MemoryNode.day
```

````

````{py:attribute} t
:canonical: agentsociety.memory.memory.MemoryNode.t
:type: int
:value: >
   None

```{autodoc2-docstring} agentsociety.memory.memory.MemoryNode.t
```

````

````{py:attribute} location
:canonical: agentsociety.memory.memory.MemoryNode.location
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.memory.memory.MemoryNode.location
```

````

````{py:attribute} description
:canonical: agentsociety.memory.memory.MemoryNode.description
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.memory.memory.MemoryNode.description
```

````

````{py:attribute} cognition_id
:canonical: agentsociety.memory.memory.MemoryNode.cognition_id
:type: typing.Optional[int]
:value: >
   None

```{autodoc2-docstring} agentsociety.memory.memory.MemoryNode.cognition_id
```

````

````{py:attribute} id
:canonical: agentsociety.memory.memory.MemoryNode.id
:type: typing.Optional[int]
:value: >
   None

```{autodoc2-docstring} agentsociety.memory.memory.MemoryNode.id
```

````

`````

`````{py:class} StreamMemory(environment: typing.Optional[agentsociety.environment.Environment], status_memory: agentsociety.memory.memory.KVMemory, embedding: fastembed.SparseTextEmbedding, max_len: int = 1000)
:canonical: agentsociety.memory.memory.StreamMemory

```{autodoc2-docstring} agentsociety.memory.memory.StreamMemory
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.memory.memory.StreamMemory.__init__
```

````{py:method} add(topic: str, description: str) -> int
:canonical: agentsociety.memory.memory.StreamMemory.add
:async:

```{autodoc2-docstring} agentsociety.memory.memory.StreamMemory.add
```

````

````{py:method} get_related_cognition(memory_id: int) -> typing.Union[agentsociety.memory.memory.MemoryNode, None]
:canonical: agentsociety.memory.memory.StreamMemory.get_related_cognition
:async:

```{autodoc2-docstring} agentsociety.memory.memory.StreamMemory.get_related_cognition
```

````

````{py:method} format_memory(memories: list[agentsociety.memory.memory.MemoryNode]) -> str
:canonical: agentsociety.memory.memory.StreamMemory.format_memory
:async:

```{autodoc2-docstring} agentsociety.memory.memory.StreamMemory.format_memory
```

````

````{py:method} get_by_ids(memory_ids: list[int]) -> str
:canonical: agentsociety.memory.memory.StreamMemory.get_by_ids
:async:

```{autodoc2-docstring} agentsociety.memory.memory.StreamMemory.get_by_ids
```

````

````{py:method} search(query: str, topic: typing.Optional[str] = None, top_k: int = 3, day_range: typing.Optional[tuple[int, int]] = None, time_range: typing.Optional[tuple[int, int]] = None) -> str
:canonical: agentsociety.memory.memory.StreamMemory.search
:async:

```{autodoc2-docstring} agentsociety.memory.memory.StreamMemory.search
```

````

````{py:method} search_today(query: str = '', topic: typing.Optional[str] = None, top_k: int = 100) -> str
:canonical: agentsociety.memory.memory.StreamMemory.search_today
:async:

```{autodoc2-docstring} agentsociety.memory.memory.StreamMemory.search_today
```

````

````{py:method} add_cognition_to_memory(memory_ids: list[int], cognition: str) -> None
:canonical: agentsociety.memory.memory.StreamMemory.add_cognition_to_memory
:async:

```{autodoc2-docstring} agentsociety.memory.memory.StreamMemory.add_cognition_to_memory
```

````

````{py:method} get_all() -> list[dict]
:canonical: agentsociety.memory.memory.StreamMemory.get_all
:async:

```{autodoc2-docstring} agentsociety.memory.memory.StreamMemory.get_all
```

````

`````

`````{py:class} Memory(environment: typing.Optional[agentsociety.environment.Environment], embedding: fastembed.SparseTextEmbedding, memory_config: agentsociety.agent.memory_config_generator.MemoryConfig)
:canonical: agentsociety.memory.memory.Memory

```{autodoc2-docstring} agentsociety.memory.memory.Memory
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.memory.memory.Memory.__init__
```

````{py:property} status
:canonical: agentsociety.memory.memory.Memory.status
:type: agentsociety.memory.memory.KVMemory

```{autodoc2-docstring} agentsociety.memory.memory.Memory.status
```

````

````{py:property} stream
:canonical: agentsociety.memory.memory.Memory.stream
:type: agentsociety.memory.memory.StreamMemory

```{autodoc2-docstring} agentsociety.memory.memory.Memory.stream
```

````

````{py:method} initialize_embeddings()
:canonical: agentsociety.memory.memory.Memory.initialize_embeddings
:async:

```{autodoc2-docstring} agentsociety.memory.memory.Memory.initialize_embeddings
```

````

`````
