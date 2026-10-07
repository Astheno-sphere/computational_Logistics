# {py:mod}`agentsociety.cityagent.memory_config`

```{py:module} agentsociety.cityagent.memory_config
```

```{autodoc2-docstring} agentsociety.cityagent.memory_config
:allowtitles:
```

## Module Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`memory_config_societyagent <agentsociety.cityagent.memory_config.memory_config_societyagent>`
  - ```{autodoc2-docstring} agentsociety.cityagent.memory_config.memory_config_societyagent
    :summary:
    ```
* - {py:obj}`memory_config_firm <agentsociety.cityagent.memory_config.memory_config_firm>`
  - ```{autodoc2-docstring} agentsociety.cityagent.memory_config.memory_config_firm
    :summary:
    ```
* - {py:obj}`memory_config_government <agentsociety.cityagent.memory_config.memory_config_government>`
  - ```{autodoc2-docstring} agentsociety.cityagent.memory_config.memory_config_government
    :summary:
    ```
* - {py:obj}`memory_config_bank <agentsociety.cityagent.memory_config.memory_config_bank>`
  - ```{autodoc2-docstring} agentsociety.cityagent.memory_config.memory_config_bank
    :summary:
    ```
* - {py:obj}`memory_config_nbs <agentsociety.cityagent.memory_config.memory_config_nbs>`
  - ```{autodoc2-docstring} agentsociety.cityagent.memory_config.memory_config_nbs
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`pareto_param <agentsociety.cityagent.memory_config.pareto_param>`
  - ```{autodoc2-docstring} agentsociety.cityagent.memory_config.pareto_param
    :summary:
    ```
* - {py:obj}`payment_max_skill_multiplier_base <agentsociety.cityagent.memory_config.payment_max_skill_multiplier_base>`
  - ```{autodoc2-docstring} agentsociety.cityagent.memory_config.payment_max_skill_multiplier_base
    :summary:
    ```
* - {py:obj}`payment_max_skill_multiplier <agentsociety.cityagent.memory_config.payment_max_skill_multiplier>`
  - ```{autodoc2-docstring} agentsociety.cityagent.memory_config.payment_max_skill_multiplier
    :summary:
    ```
* - {py:obj}`pmsm <agentsociety.cityagent.memory_config.pmsm>`
  - ```{autodoc2-docstring} agentsociety.cityagent.memory_config.pmsm
    :summary:
    ```
* - {py:obj}`pareto_samples <agentsociety.cityagent.memory_config.pareto_samples>`
  - ```{autodoc2-docstring} agentsociety.cityagent.memory_config.pareto_samples
    :summary:
    ```
* - {py:obj}`clipped_skills <agentsociety.cityagent.memory_config.clipped_skills>`
  - ```{autodoc2-docstring} agentsociety.cityagent.memory_config.clipped_skills
    :summary:
    ```
* - {py:obj}`sorted_clipped_skills <agentsociety.cityagent.memory_config.sorted_clipped_skills>`
  - ```{autodoc2-docstring} agentsociety.cityagent.memory_config.sorted_clipped_skills
    :summary:
    ```
* - {py:obj}`agent_skills <agentsociety.cityagent.memory_config.agent_skills>`
  - ```{autodoc2-docstring} agentsociety.cityagent.memory_config.agent_skills
    :summary:
    ```
* - {py:obj}`__all__ <agentsociety.cityagent.memory_config.__all__>`
  - ```{autodoc2-docstring} agentsociety.cityagent.memory_config.__all__
    :summary:
    ```
* - {py:obj}`DEFAULT_DISTRIBUTIONS <agentsociety.cityagent.memory_config.DEFAULT_DISTRIBUTIONS>`
  - ```{autodoc2-docstring} agentsociety.cityagent.memory_config.DEFAULT_DISTRIBUTIONS
    :summary:
    ```
````

### API

````{py:data} pareto_param
:canonical: agentsociety.cityagent.memory_config.pareto_param
:value: >
   8

```{autodoc2-docstring} agentsociety.cityagent.memory_config.pareto_param
```

````

````{py:data} payment_max_skill_multiplier_base
:canonical: agentsociety.cityagent.memory_config.payment_max_skill_multiplier_base
:value: >
   950

```{autodoc2-docstring} agentsociety.cityagent.memory_config.payment_max_skill_multiplier_base
```

````

````{py:data} payment_max_skill_multiplier
:canonical: agentsociety.cityagent.memory_config.payment_max_skill_multiplier
:value: >
   'float(...)'

```{autodoc2-docstring} agentsociety.cityagent.memory_config.payment_max_skill_multiplier
```

````

````{py:data} pmsm
:canonical: agentsociety.cityagent.memory_config.pmsm
:value: >
   None

```{autodoc2-docstring} agentsociety.cityagent.memory_config.pmsm
```

````

````{py:data} pareto_samples
:canonical: agentsociety.cityagent.memory_config.pareto_samples
:value: >
   'pareto(...)'

```{autodoc2-docstring} agentsociety.cityagent.memory_config.pareto_samples
```

````

````{py:data} clipped_skills
:canonical: agentsociety.cityagent.memory_config.clipped_skills
:value: >
   'minimum(...)'

```{autodoc2-docstring} agentsociety.cityagent.memory_config.clipped_skills
```

````

````{py:data} sorted_clipped_skills
:canonical: agentsociety.cityagent.memory_config.sorted_clipped_skills
:value: >
   'sort(...)'

```{autodoc2-docstring} agentsociety.cityagent.memory_config.sorted_clipped_skills
```

````

````{py:data} agent_skills
:canonical: agentsociety.cityagent.memory_config.agent_skills
:value: >
   'list(...)'

```{autodoc2-docstring} agentsociety.cityagent.memory_config.agent_skills
```

````

````{py:data} __all__
:canonical: agentsociety.cityagent.memory_config.__all__
:value: >
   ['memory_config_societyagent', 'memory_config_firm', 'memory_config_government', 'memory_config_bank...

```{autodoc2-docstring} agentsociety.cityagent.memory_config.__all__
```

````

````{py:data} DEFAULT_DISTRIBUTIONS
:canonical: agentsociety.cityagent.memory_config.DEFAULT_DISTRIBUTIONS
:type: dict[str, agentsociety.agent.distribution.Distribution]
:value: >
   None

```{autodoc2-docstring} agentsociety.cityagent.memory_config.DEFAULT_DISTRIBUTIONS
```

````

````{py:function} memory_config_societyagent(distributions: dict[str, agentsociety.agent.distribution.Distribution], class_config: typing.Optional[list[agentsociety.agent.memory_config_generator.MemoryAttribute]] = None) -> agentsociety.agent.memory_config_generator.MemoryConfig
:canonical: agentsociety.cityagent.memory_config.memory_config_societyagent

```{autodoc2-docstring} agentsociety.cityagent.memory_config.memory_config_societyagent
```
````

````{py:function} memory_config_firm(distributions: dict[str, agentsociety.agent.distribution.Distribution], class_config: typing.Optional[list[agentsociety.agent.memory_config_generator.MemoryAttribute]] = None) -> agentsociety.agent.memory_config_generator.MemoryConfig
:canonical: agentsociety.cityagent.memory_config.memory_config_firm

```{autodoc2-docstring} agentsociety.cityagent.memory_config.memory_config_firm
```
````

````{py:function} memory_config_government(distributions: dict[str, agentsociety.agent.distribution.Distribution], class_config: typing.Optional[list[agentsociety.agent.memory_config_generator.MemoryAttribute]] = None) -> agentsociety.agent.memory_config_generator.MemoryConfig
:canonical: agentsociety.cityagent.memory_config.memory_config_government

```{autodoc2-docstring} agentsociety.cityagent.memory_config.memory_config_government
```
````

````{py:function} memory_config_bank(distributions: dict[str, agentsociety.agent.distribution.Distribution], class_config: typing.Optional[list[agentsociety.agent.memory_config_generator.MemoryAttribute]] = None) -> agentsociety.agent.memory_config_generator.MemoryConfig
:canonical: agentsociety.cityagent.memory_config.memory_config_bank

```{autodoc2-docstring} agentsociety.cityagent.memory_config.memory_config_bank
```
````

````{py:function} memory_config_nbs(distributions: dict[str, agentsociety.agent.distribution.Distribution], class_config: typing.Optional[list[agentsociety.agent.memory_config_generator.MemoryAttribute]] = None) -> agentsociety.agent.memory_config_generator.MemoryConfig
:canonical: agentsociety.cityagent.memory_config.memory_config_nbs

```{autodoc2-docstring} agentsociety.cityagent.memory_config.memory_config_nbs
```
````
