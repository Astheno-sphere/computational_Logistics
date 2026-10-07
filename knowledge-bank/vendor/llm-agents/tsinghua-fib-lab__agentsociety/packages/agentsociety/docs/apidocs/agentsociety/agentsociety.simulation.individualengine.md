# {py:mod}`agentsociety.simulation.individualengine`

```{py:module} agentsociety.simulation.individualengine
```

```{autodoc2-docstring} agentsociety.simulation.individualengine
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`IndividualEngine <agentsociety.simulation.individualengine.IndividualEngine>`
  - ```{autodoc2-docstring} agentsociety.simulation.individualengine.IndividualEngine
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.simulation.individualengine.__all__>`
  - ```{autodoc2-docstring} agentsociety.simulation.individualengine.__all__
    :summary:
    ```
* - {py:obj}`MIN_ID <agentsociety.simulation.individualengine.MIN_ID>`
  - ```{autodoc2-docstring} agentsociety.simulation.individualengine.MIN_ID
    :summary:
    ```
* - {py:obj}`MAX_ID <agentsociety.simulation.individualengine.MAX_ID>`
  - ```{autodoc2-docstring} agentsociety.simulation.individualengine.MAX_ID
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.simulation.individualengine.__all__
:value: >
   ['IndividualEngine']

```{autodoc2-docstring} agentsociety.simulation.individualengine.__all__
```

````

````{py:data} MIN_ID
:canonical: agentsociety.simulation.individualengine.MIN_ID
:value: >
   1

```{autodoc2-docstring} agentsociety.simulation.individualengine.MIN_ID
```

````

````{py:data} MAX_ID
:canonical: agentsociety.simulation.individualengine.MAX_ID
:value: >
   1000000000

```{autodoc2-docstring} agentsociety.simulation.individualengine.MAX_ID
```

````

`````{py:class} IndividualEngine(config: agentsociety.configs.IndividualConfig, tenant_id: str = '')
:canonical: agentsociety.simulation.individualengine.IndividualEngine

```{autodoc2-docstring} agentsociety.simulation.individualengine.IndividualEngine
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.simulation.individualengine.IndividualEngine.__init__
```

````{py:method} _init_embedding()
:canonical: agentsociety.simulation.individualengine.IndividualEngine._init_embedding
:async:

```{autodoc2-docstring} agentsociety.simulation.individualengine.IndividualEngine._init_embedding
```

````

````{py:method} _init_embedding_task()
:canonical: agentsociety.simulation.individualengine.IndividualEngine._init_embedding_task
:async:

```{autodoc2-docstring} agentsociety.simulation.individualengine.IndividualEngine._init_embedding_task
```

````

````{py:method} init()
:canonical: agentsociety.simulation.individualengine.IndividualEngine.init
:async:

```{autodoc2-docstring} agentsociety.simulation.individualengine.IndividualEngine.init
```

````

````{py:method} run()
:canonical: agentsociety.simulation.individualengine.IndividualEngine.run
:async:

```{autodoc2-docstring} agentsociety.simulation.individualengine.IndividualEngine.run
```

````

````{py:method} close()
:canonical: agentsociety.simulation.individualengine.IndividualEngine.close
:async:

```{autodoc2-docstring} agentsociety.simulation.individualengine.IndividualEngine.close
```

````

````{py:property} config
:canonical: agentsociety.simulation.individualengine.IndividualEngine.config

```{autodoc2-docstring} agentsociety.simulation.individualengine.IndividualEngine.config
```

````

````{py:property} database
:canonical: agentsociety.simulation.individualengine.IndividualEngine.database

```{autodoc2-docstring} agentsociety.simulation.individualengine.IndividualEngine.database
```

````

````{py:property} llm
:canonical: agentsociety.simulation.individualengine.IndividualEngine.llm

```{autodoc2-docstring} agentsociety.simulation.individualengine.IndividualEngine.llm
```

````

````{py:property} enable_database
:canonical: agentsociety.simulation.individualengine.IndividualEngine.enable_database

```{autodoc2-docstring} agentsociety.simulation.individualengine.IndividualEngine.enable_database
```

````

````{py:property} database_writer
:canonical: agentsociety.simulation.individualengine.IndividualEngine.database_writer

```{autodoc2-docstring} agentsociety.simulation.individualengine.IndividualEngine.database_writer
```

````

````{py:method} _save_exp_info() -> None
:canonical: agentsociety.simulation.individualengine.IndividualEngine._save_exp_info
:async:

```{autodoc2-docstring} agentsociety.simulation.individualengine.IndividualEngine._save_exp_info
```

````

`````
