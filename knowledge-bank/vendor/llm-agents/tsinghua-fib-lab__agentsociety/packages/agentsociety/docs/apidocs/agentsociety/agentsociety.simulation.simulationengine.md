# {py:mod}`agentsociety.simulation.simulationengine`

```{py:module} agentsociety.simulation.simulationengine
```

```{autodoc2-docstring} agentsociety.simulation.simulationengine
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`SimulationEngine <agentsociety.simulation.simulationengine.SimulationEngine>`
  - ```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine
    :summary:
    ```
````

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`_set_default_agent_config <agentsociety.simulation.simulationengine._set_default_agent_config>`
  - ```{autodoc2-docstring} agentsociety.simulation.simulationengine._set_default_agent_config
    :summary:
    ```
* - {py:obj}`_init_agent_class <agentsociety.simulation.simulationengine._init_agent_class>`
  - ```{autodoc2-docstring} agentsociety.simulation.simulationengine._init_agent_class
    :summary:
    ```
* - {py:obj}`evaluate_filter <agentsociety.simulation.simulationengine.evaluate_filter>`
  - ```{autodoc2-docstring} agentsociety.simulation.simulationengine.evaluate_filter
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.simulation.simulationengine.__all__>`
  - ```{autodoc2-docstring} agentsociety.simulation.simulationengine.__all__
    :summary:
    ```
* - {py:obj}`MIN_ID <agentsociety.simulation.simulationengine.MIN_ID>`
  - ```{autodoc2-docstring} agentsociety.simulation.simulationengine.MIN_ID
    :summary:
    ```
* - {py:obj}`MAX_ID <agentsociety.simulation.simulationengine.MAX_ID>`
  - ```{autodoc2-docstring} agentsociety.simulation.simulationengine.MAX_ID
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.simulation.simulationengine.__all__
:value: >
   ['SimulationEngine']

```{autodoc2-docstring} agentsociety.simulation.simulationengine.__all__
```

````

````{py:data} MIN_ID
:canonical: agentsociety.simulation.simulationengine.MIN_ID
:value: >
   1

```{autodoc2-docstring} agentsociety.simulation.simulationengine.MIN_ID
```

````

````{py:data} MAX_ID
:canonical: agentsociety.simulation.simulationengine.MAX_ID
:value: >
   100000000

```{autodoc2-docstring} agentsociety.simulation.simulationengine.MAX_ID
```

````

````{py:function} _set_default_agent_config(self: agentsociety.configs.Config)
:canonical: agentsociety.simulation.simulationengine._set_default_agent_config

```{autodoc2-docstring} agentsociety.simulation.simulationengine._set_default_agent_config
```
````

````{py:function} _init_agent_class(agent_config: agentsociety.configs.AgentConfig, s3config: agentsociety.s3.S3Config)
:canonical: agentsociety.simulation.simulationengine._init_agent_class

```{autodoc2-docstring} agentsociety.simulation.simulationengine._init_agent_class
```
````

````{py:function} evaluate_filter(filter_str: str, profile: dict) -> bool
:canonical: agentsociety.simulation.simulationengine.evaluate_filter

```{autodoc2-docstring} agentsociety.simulation.simulationengine.evaluate_filter
```
````

`````{py:class} SimulationEngine(config: agentsociety.configs.Config, tenant_id: str = '')
:canonical: agentsociety.simulation.simulationengine.SimulationEngine

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine.__init__
```

````{py:method} _init_embedding()
:canonical: agentsociety.simulation.simulationengine.SimulationEngine._init_embedding
:async:

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine._init_embedding
```

````

````{py:method} _init_embedding_task()
:canonical: agentsociety.simulation.simulationengine.SimulationEngine._init_embedding_task
:async:

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine._init_embedding_task
```

````

````{py:method} init()
:canonical: agentsociety.simulation.simulationengine.SimulationEngine.init
:async:

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine.init
```

````

````{py:method} close()
:canonical: agentsociety.simulation.simulationengine.SimulationEngine.close
:async:

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine.close
```

````

````{py:property} name
:canonical: agentsociety.simulation.simulationengine.SimulationEngine.name

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine.name
```

````

````{py:property} config
:canonical: agentsociety.simulation.simulationengine.SimulationEngine.config

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine.config
```

````

````{py:property} llm
:canonical: agentsociety.simulation.simulationengine.SimulationEngine.llm

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine.llm
```

````

````{py:property} enable_database
:canonical: agentsociety.simulation.simulationengine.SimulationEngine.enable_database

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine.enable_database
```

````

````{py:property} database_writer
:canonical: agentsociety.simulation.simulationengine.SimulationEngine.database_writer

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine.database_writer
```

````

````{py:property} environment
:canonical: agentsociety.simulation.simulationengine.SimulationEngine.environment

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine.environment
```

````

````{py:property} messager
:canonical: agentsociety.simulation.simulationengine.SimulationEngine.messager

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine.messager
```

````

````{py:method} _extract_target_agent_ids(target_agent: typing.Optional[typing.Union[list[int], agentsociety.configs.AgentFilterConfig]] = None) -> list[int]
:canonical: agentsociety.simulation.simulationengine.SimulationEngine._extract_target_agent_ids
:async:

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine._extract_target_agent_ids
```

````

````{py:method} gather(content: str, target_agent_ids: typing.Optional[list[int]] = None, flatten: bool = False, keep_id: bool = False) -> typing.Union[dict[int, typing.Any], list[typing.Any]]
:canonical: agentsociety.simulation.simulationengine.SimulationEngine.gather
:async:

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine.gather
```

````

````{py:method} filter(types: typing.Optional[tuple[type[agentsociety.agent.Agent]]] = None, filter_str: typing.Optional[str] = None) -> list[int]
:canonical: agentsociety.simulation.simulationengine.SimulationEngine.filter
:async:

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine.filter
```

````

````{py:method} update_environment(key: str, value: str)
:canonical: agentsociety.simulation.simulationengine.SimulationEngine.update_environment
:async:

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine.update_environment
```

````

````{py:method} update(target_agent_ids: list[int], target_key: str, content: typing.Any, query: bool = False)
:canonical: agentsociety.simulation.simulationengine.SimulationEngine.update
:async:

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine.update
```

````

````{py:method} economy_update(target_agent_id: int, target_key: str, content: typing.Any, mode: typing.Literal[replace, merge] = 'replace')
:canonical: agentsociety.simulation.simulationengine.SimulationEngine.economy_update
:async:

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine.economy_update
```

````

````{py:method} send_survey(survey: agentsociety.survey.models.Survey, agent_ids: list[int] = [], survey_day: typing.Optional[int] = None, survey_t: typing.Optional[float] = None, is_pending_survey: bool = False, pending_survey_id: typing.Optional[int] = None) -> dict[int, str]
:canonical: agentsociety.simulation.simulationengine.SimulationEngine.send_survey
:async:

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine.send_survey
```

````

````{py:method} send_interview_message(question: str, agent_ids: list[int])
:canonical: agentsociety.simulation.simulationengine.SimulationEngine.send_interview_message
:async:

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine.send_interview_message
```

````

````{py:method} send_intervention_message(intervention_message: str, agent_ids: list[int])
:canonical: agentsociety.simulation.simulationengine.SimulationEngine.send_intervention_message
:async:

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine.send_intervention_message
```

````

````{py:method} _save_exp_info() -> None
:canonical: agentsociety.simulation.simulationengine.SimulationEngine._save_exp_info
:async:

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine._save_exp_info
```

````

````{py:method} _save_global_prompt(prompt: str, day: int, t: float)
:canonical: agentsociety.simulation.simulationengine.SimulationEngine._save_global_prompt
:async:

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine._save_global_prompt
```

````

````{py:method} _gather_and_update_context(target_agent_ids: list[int], key: str, save_as: str)
:canonical: agentsociety.simulation.simulationengine.SimulationEngine._gather_and_update_context
:async:

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine._gather_and_update_context
```

````

````{py:method} _save_context()
:canonical: agentsociety.simulation.simulationengine.SimulationEngine._save_context

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine._save_context
```

````

````{py:method} _message_dispatch()
:canonical: agentsociety.simulation.simulationengine.SimulationEngine._message_dispatch
:async:

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine._message_dispatch
```

````

````{py:method} _save(day: int, t: int)
:canonical: agentsociety.simulation.simulationengine.SimulationEngine._save
:async:

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine._save
```

````

````{py:method} delete_agents(target_agent_ids: list[int])
:canonical: agentsociety.simulation.simulationengine.SimulationEngine.delete_agents
:async:

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine.delete_agents
```

````

````{py:method} next_round()
:canonical: agentsociety.simulation.simulationengine.SimulationEngine.next_round
:async:

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine.next_round
```

````

````{py:method} step(num_environment_ticks: int = 1) -> agentsociety.simulation.type.Logs
:canonical: agentsociety.simulation.simulationengine.SimulationEngine.step
:async:

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine.step
```

````

````{py:method} run_one_day(ticks_per_step: int)
:canonical: agentsociety.simulation.simulationengine.SimulationEngine.run_one_day
:async:

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine.run_one_day
```

````

````{py:method} run()
:canonical: agentsociety.simulation.simulationengine.SimulationEngine.run
:async:

```{autodoc2-docstring} agentsociety.simulation.simulationengine.SimulationEngine.run
```

````

`````
