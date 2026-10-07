# {py:mod}`agentsociety.agent.memory_config_generator`

```{py:module} agentsociety.agent.memory_config_generator
```

```{autodoc2-docstring} agentsociety.agent.memory_config_generator
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`MemoryAttribute <agentsociety.agent.memory_config_generator.MemoryAttribute>`
  -
* - {py:obj}`MemoryConfig <agentsociety.agent.memory_config_generator.MemoryConfig>`
  - ```{autodoc2-docstring} agentsociety.agent.memory_config_generator.MemoryConfig
    :summary:
    ```
* - {py:obj}`MemoryConfigGenerator <agentsociety.agent.memory_config_generator.MemoryConfigGenerator>`
  - ```{autodoc2-docstring} agentsociety.agent.memory_config_generator.MemoryConfigGenerator
    :summary:
    ```
````

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`_create_default_citizen_attributes <agentsociety.agent.memory_config_generator._create_default_citizen_attributes>`
  - ```{autodoc2-docstring} agentsociety.agent.memory_config_generator._create_default_citizen_attributes
    :summary:
    ```
* - {py:obj}`_create_default_supervisor_attributes <agentsociety.agent.memory_config_generator._create_default_supervisor_attributes>`
  - ```{autodoc2-docstring} agentsociety.agent.memory_config_generator._create_default_supervisor_attributes
    :summary:
    ```
* - {py:obj}`default_memory_config_citizen <agentsociety.agent.memory_config_generator.default_memory_config_citizen>`
  - ```{autodoc2-docstring} agentsociety.agent.memory_config_generator.default_memory_config_citizen
    :summary:
    ```
* - {py:obj}`default_memory_config_supervisor <agentsociety.agent.memory_config_generator.default_memory_config_supervisor>`
  - ```{autodoc2-docstring} agentsociety.agent.memory_config_generator.default_memory_config_supervisor
    :summary:
    ```
* - {py:obj}`default_memory_config_solver <agentsociety.agent.memory_config_generator.default_memory_config_solver>`
  - ```{autodoc2-docstring} agentsociety.agent.memory_config_generator.default_memory_config_solver
    :summary:
    ```
* - {py:obj}`_memory_config_load_file <agentsociety.agent.memory_config_generator._memory_config_load_file>`
  - ```{autodoc2-docstring} agentsociety.agent.memory_config_generator._memory_config_load_file
    :summary:
    ```
* - {py:obj}`_memory_config_merge <agentsociety.agent.memory_config_generator._memory_config_merge>`
  - ```{autodoc2-docstring} agentsociety.agent.memory_config_generator._memory_config_merge
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.agent.memory_config_generator.__all__>`
  - ```{autodoc2-docstring} agentsociety.agent.memory_config_generator.__all__
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.agent.memory_config_generator.__all__
:value: >
   ['MemoryConfigGenerator', 'MemoryAttribute', 'MemoryConfig', 'default_memory_config_citizen', 'defau...

```{autodoc2-docstring} agentsociety.agent.memory_config_generator.__all__
```

````

`````{py:class} MemoryAttribute(/, **data: typing.Any)
:canonical: agentsociety.agent.memory_config_generator.MemoryAttribute

Bases: {py:obj}`pydantic.BaseModel`

````{py:attribute} name
:canonical: agentsociety.agent.memory_config_generator.MemoryAttribute.name
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.agent.memory_config_generator.MemoryAttribute.name
```

````

````{py:attribute} type
:canonical: agentsociety.agent.memory_config_generator.MemoryAttribute.type
:type: typing.Any
:value: >
   None

```{autodoc2-docstring} agentsociety.agent.memory_config_generator.MemoryAttribute.type
```

````

````{py:attribute} default_or_value
:canonical: agentsociety.agent.memory_config_generator.MemoryAttribute.default_or_value
:type: typing.Any
:value: >
   None

```{autodoc2-docstring} agentsociety.agent.memory_config_generator.MemoryAttribute.default_or_value
```

````

````{py:attribute} description
:canonical: agentsociety.agent.memory_config_generator.MemoryAttribute.description
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.agent.memory_config_generator.MemoryAttribute.description
```

````

````{py:attribute} whether_embedding
:canonical: agentsociety.agent.memory_config_generator.MemoryAttribute.whether_embedding
:type: bool
:value: >
   False

```{autodoc2-docstring} agentsociety.agent.memory_config_generator.MemoryAttribute.whether_embedding
```

````

````{py:attribute} embedding_template
:canonical: agentsociety.agent.memory_config_generator.MemoryAttribute.embedding_template
:type: typing.Optional[str]
:value: >
   None

```{autodoc2-docstring} agentsociety.agent.memory_config_generator.MemoryAttribute.embedding_template
```

````

`````

`````{py:class} MemoryConfig(/, **data: typing.Any)
:canonical: agentsociety.agent.memory_config_generator.MemoryConfig

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.agent.memory_config_generator.MemoryConfig
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.agent.memory_config_generator.MemoryConfig.__init__
```

````{py:attribute} attributes
:canonical: agentsociety.agent.memory_config_generator.MemoryConfig.attributes
:type: dict[str, agentsociety.agent.memory_config_generator.MemoryAttribute]
:value: >
   None

```{autodoc2-docstring} agentsociety.agent.memory_config_generator.MemoryConfig.attributes
```

````

````{py:method} from_list(attributes: list[agentsociety.agent.memory_config_generator.MemoryAttribute]) -> agentsociety.agent.memory_config_generator.MemoryConfig
:canonical: agentsociety.agent.memory_config_generator.MemoryConfig.from_list
:staticmethod:

```{autodoc2-docstring} agentsociety.agent.memory_config_generator.MemoryConfig.from_list
```

````

`````

````{py:function} _create_default_citizen_attributes() -> agentsociety.agent.memory_config_generator.MemoryConfig
:canonical: agentsociety.agent.memory_config_generator._create_default_citizen_attributes

```{autodoc2-docstring} agentsociety.agent.memory_config_generator._create_default_citizen_attributes
```
````

````{py:function} _create_default_supervisor_attributes() -> agentsociety.agent.memory_config_generator.MemoryConfig
:canonical: agentsociety.agent.memory_config_generator._create_default_supervisor_attributes

```{autodoc2-docstring} agentsociety.agent.memory_config_generator._create_default_supervisor_attributes
```
````

````{py:function} default_memory_config_citizen(distributions: dict[str, agentsociety.agent.distribution.Distribution], class_config: typing.Optional[list[agentsociety.agent.memory_config_generator.MemoryAttribute]] = None) -> agentsociety.agent.memory_config_generator.MemoryConfig
:canonical: agentsociety.agent.memory_config_generator.default_memory_config_citizen

```{autodoc2-docstring} agentsociety.agent.memory_config_generator.default_memory_config_citizen
```
````

````{py:function} default_memory_config_supervisor(distributions: dict[str, agentsociety.agent.distribution.Distribution], class_config: typing.Optional[list[agentsociety.agent.memory_config_generator.MemoryAttribute]] = None) -> agentsociety.agent.memory_config_generator.MemoryConfig
:canonical: agentsociety.agent.memory_config_generator.default_memory_config_supervisor

```{autodoc2-docstring} agentsociety.agent.memory_config_generator.default_memory_config_supervisor
```
````

````{py:function} default_memory_config_solver(distributions: dict[str, agentsociety.agent.distribution.Distribution], class_config: typing.Optional[list[agentsociety.agent.memory_config_generator.MemoryAttribute]] = None) -> agentsociety.agent.memory_config_generator.MemoryConfig
:canonical: agentsociety.agent.memory_config_generator.default_memory_config_solver

```{autodoc2-docstring} agentsociety.agent.memory_config_generator.default_memory_config_solver
```
````

`````{py:class} MemoryConfigGenerator(config_func: typing.Callable[[dict[str, agentsociety.agent.distribution.Distribution], typing.Optional[list[agentsociety.agent.memory_config_generator.MemoryAttribute]]], agentsociety.agent.memory_config_generator.MemoryConfig], class_config: typing.Optional[list[agentsociety.agent.memory_config_generator.MemoryAttribute]] = None, number: typing.Optional[int] = None, file: typing.Optional[str] = None, distributions: dict[str, typing.Union[agentsociety.agent.distribution.Distribution, agentsociety.agent.distribution.DistributionConfig]] = {}, s3config: agentsociety.s3.S3Config = S3Config.model_validate({}))
:canonical: agentsociety.agent.memory_config_generator.MemoryConfigGenerator

```{autodoc2-docstring} agentsociety.agent.memory_config_generator.MemoryConfigGenerator
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.agent.memory_config_generator.MemoryConfigGenerator.__init__
```

````{py:method} merge_distributions(distributions: dict[str, typing.Union[agentsociety.agent.distribution.Distribution, agentsociety.agent.distribution.DistributionConfig]])
:canonical: agentsociety.agent.memory_config_generator.MemoryConfigGenerator.merge_distributions

```{autodoc2-docstring} agentsociety.agent.memory_config_generator.MemoryConfigGenerator.merge_distributions
```

````

````{py:method} generate(i: int) -> agentsociety.agent.memory_config_generator.MemoryConfig
:canonical: agentsociety.agent.memory_config_generator.MemoryConfigGenerator.generate

```{autodoc2-docstring} agentsociety.agent.memory_config_generator.MemoryConfigGenerator.generate
```

````

````{py:method} get_agent_data_from_file() -> typing.List[dict]
:canonical: agentsociety.agent.memory_config_generator.MemoryConfigGenerator.get_agent_data_from_file

```{autodoc2-docstring} agentsociety.agent.memory_config_generator.MemoryConfigGenerator.get_agent_data_from_file
```

````

`````

````{py:function} _memory_config_load_file(file_path: str, s3config: agentsociety.s3.S3Config)
:canonical: agentsociety.agent.memory_config_generator._memory_config_load_file

```{autodoc2-docstring} agentsociety.agent.memory_config_generator._memory_config_load_file
```
````

````{py:function} _memory_config_merge(file_data: dict, memory_config: agentsociety.agent.memory_config_generator.MemoryConfig) -> agentsociety.agent.memory_config_generator.MemoryConfig
:canonical: agentsociety.agent.memory_config_generator._memory_config_merge

```{autodoc2-docstring} agentsociety.agent.memory_config_generator._memory_config_merge
```
````
