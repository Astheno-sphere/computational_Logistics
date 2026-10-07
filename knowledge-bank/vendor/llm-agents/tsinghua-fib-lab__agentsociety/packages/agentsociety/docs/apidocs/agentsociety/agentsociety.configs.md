# {py:mod}`agentsociety.configs`

```{py:module} agentsociety.configs
```

```{autodoc2-docstring} agentsociety.configs
:allowtitles:
```

## Submodules

```{toctree}
:titlesonly:
:maxdepth: 1

agentsociety.configs.exp
agentsociety.configs.env
agentsociety.configs.agent
agentsociety.configs.utils
```

## Package Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`AgentsConfig <agentsociety.configs.AgentsConfig>`
  - ```{autodoc2-docstring} agentsociety.configs.AgentsConfig
    :summary:
    ```
* - {py:obj}`Config <agentsociety.configs.Config>`
  - ```{autodoc2-docstring} agentsociety.configs.Config
    :summary:
    ```
* - {py:obj}`TaskLoaderConfig <agentsociety.configs.TaskLoaderConfig>`
  - ```{autodoc2-docstring} agentsociety.configs.TaskLoaderConfig
    :summary:
    ```
* - {py:obj}`IndividualConfig <agentsociety.configs.IndividualConfig>`
  - ```{autodoc2-docstring} agentsociety.configs.IndividualConfig
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.configs.__all__>`
  - ```{autodoc2-docstring} agentsociety.configs.__all__
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.configs.__all__
:value: >
   ['EnvConfig', 'AgentConfig', 'WorkflowStepConfig', 'ExpConfig', 'EnvironmentConfig', 'Config', 'load...

```{autodoc2-docstring} agentsociety.configs.__all__
```

````

`````{py:class} AgentsConfig(/, **data: typing.Any)
:canonical: agentsociety.configs.AgentsConfig

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.configs.AgentsConfig
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.configs.AgentsConfig.__init__
```

````{py:attribute} citizens
:canonical: agentsociety.configs.AgentsConfig.citizens
:type: list[agentsociety.configs.agent.AgentConfig]
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.configs.AgentsConfig.citizens
```

````

````{py:attribute} firms
:canonical: agentsociety.configs.AgentsConfig.firms
:type: list[agentsociety.configs.agent.AgentConfig]
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.configs.AgentsConfig.firms
```

````

````{py:attribute} banks
:canonical: agentsociety.configs.AgentsConfig.banks
:type: list[agentsociety.configs.agent.AgentConfig]
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.configs.AgentsConfig.banks
```

````

````{py:attribute} nbs
:canonical: agentsociety.configs.AgentsConfig.nbs
:type: list[agentsociety.configs.agent.AgentConfig]
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.configs.AgentsConfig.nbs
```

````

````{py:attribute} governments
:canonical: agentsociety.configs.AgentsConfig.governments
:type: list[agentsociety.configs.agent.AgentConfig]
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.configs.AgentsConfig.governments
```

````

````{py:attribute} supervisor
:canonical: agentsociety.configs.AgentsConfig.supervisor
:type: typing.Optional[agentsociety.configs.agent.AgentConfig]
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.configs.AgentsConfig.supervisor
```

````

````{py:attribute} init_funcs
:canonical: agentsociety.configs.AgentsConfig.init_funcs
:type: list[typing.Callable[[typing.Any], typing.Union[None, typing.Awaitable[None]]]]
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.configs.AgentsConfig.init_funcs
```

````

````{py:method} serialize_init_funcs(init_funcs, info)
:canonical: agentsociety.configs.AgentsConfig.serialize_init_funcs

```{autodoc2-docstring} agentsociety.configs.AgentsConfig.serialize_init_funcs
```

````

`````

`````{py:class} Config(/, **data: typing.Any)
:canonical: agentsociety.configs.Config

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.configs.Config
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.configs.Config.__init__
```

````{py:attribute} llm
:canonical: agentsociety.configs.Config.llm
:type: typing.List[agentsociety.llm.LLMConfig]
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.configs.Config.llm
```

````

````{py:attribute} env
:canonical: agentsociety.configs.Config.env
:type: agentsociety.configs.env.EnvConfig
:value: >
   None

```{autodoc2-docstring} agentsociety.configs.Config.env
```

````

````{py:attribute} map
:canonical: agentsociety.configs.Config.map
:type: agentsociety.environment.MapConfig
:value: >
   None

```{autodoc2-docstring} agentsociety.configs.Config.map
```

````

````{py:attribute} agents
:canonical: agentsociety.configs.Config.agents
:type: agentsociety.configs.AgentsConfig
:value: >
   None

```{autodoc2-docstring} agentsociety.configs.Config.agents
```

````

````{py:attribute} exp
:canonical: agentsociety.configs.Config.exp
:type: agentsociety.configs.exp.ExpConfig
:value: >
   None

```{autodoc2-docstring} agentsociety.configs.Config.exp
```

````

````{py:attribute} logging_level
:canonical: agentsociety.configs.Config.logging_level
:type: str
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.configs.Config.logging_level
```

````

`````

`````{py:class} TaskLoaderConfig(/, **data: typing.Any)
:canonical: agentsociety.configs.TaskLoaderConfig

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.configs.TaskLoaderConfig
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.configs.TaskLoaderConfig.__init__
```

````{py:attribute} task_type
:canonical: agentsociety.configs.TaskLoaderConfig.task_type
:type: type[agentsociety.taskloader.Task]
:value: >
   None

```{autodoc2-docstring} agentsociety.configs.TaskLoaderConfig.task_type
```

````

````{py:attribute} file_path
:canonical: agentsociety.configs.TaskLoaderConfig.file_path
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.configs.TaskLoaderConfig.file_path
```

````

````{py:attribute} shuffle
:canonical: agentsociety.configs.TaskLoaderConfig.shuffle
:type: bool
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.configs.TaskLoaderConfig.shuffle
```

````

`````

`````{py:class} IndividualConfig(/, **data: typing.Any)
:canonical: agentsociety.configs.IndividualConfig

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.configs.IndividualConfig
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.configs.IndividualConfig.__init__
```

````{py:attribute} name
:canonical: agentsociety.configs.IndividualConfig.name
:type: str
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.configs.IndividualConfig.name
```

````

````{py:attribute} llm
:canonical: agentsociety.configs.IndividualConfig.llm
:type: typing.List[agentsociety.llm.LLMConfig]
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.configs.IndividualConfig.llm
```

````

````{py:attribute} env
:canonical: agentsociety.configs.IndividualConfig.env
:type: agentsociety.configs.env.EnvConfig
:value: >
   None

```{autodoc2-docstring} agentsociety.configs.IndividualConfig.env
```

````

````{py:attribute} id
:canonical: agentsociety.configs.IndividualConfig.id
:type: uuid.UUID
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.configs.IndividualConfig.id
```

````

````{py:attribute} individual
:canonical: agentsociety.configs.IndividualConfig.individual
:type: agentsociety.configs.agent.AgentConfig
:value: >
   None

```{autodoc2-docstring} agentsociety.configs.IndividualConfig.individual
```

````

````{py:attribute} task_loader
:canonical: agentsociety.configs.IndividualConfig.task_loader
:type: agentsociety.configs.TaskLoaderConfig
:value: >
   None

```{autodoc2-docstring} agentsociety.configs.IndividualConfig.task_loader
```

````

````{py:attribute} logging_level
:canonical: agentsociety.configs.IndividualConfig.logging_level
:type: str
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.configs.IndividualConfig.logging_level
```

````

````{py:method} serialize_id(id, info)
:canonical: agentsociety.configs.IndividualConfig.serialize_id

```{autodoc2-docstring} agentsociety.configs.IndividualConfig.serialize_id
```

````

`````
