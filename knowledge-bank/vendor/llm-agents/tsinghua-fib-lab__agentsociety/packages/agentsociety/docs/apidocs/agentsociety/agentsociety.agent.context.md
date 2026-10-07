# {py:mod}`agentsociety.agent.context`

```{py:module} agentsociety.agent.context
```

```{autodoc2-docstring} agentsociety.agent.context
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`AgentContext <agentsociety.agent.context.AgentContext>`
  - ```{autodoc2-docstring} agentsociety.agent.context.AgentContext
    :summary:
    ```
* - {py:obj}`BlockContext <agentsociety.agent.context.BlockContext>`
  - ```{autodoc2-docstring} agentsociety.agent.context.BlockContext
    :summary:
    ```
* - {py:obj}`DotDict <agentsociety.agent.context.DotDict>`
  - ```{autodoc2-docstring} agentsociety.agent.context.DotDict
    :summary:
    ```
````

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`context_to_dot_dict <agentsociety.agent.context.context_to_dot_dict>`
  - ```{autodoc2-docstring} agentsociety.agent.context.context_to_dot_dict
    :summary:
    ```
* - {py:obj}`auto_deepcopy_dotdict <agentsociety.agent.context.auto_deepcopy_dotdict>`
  - ```{autodoc2-docstring} agentsociety.agent.context.auto_deepcopy_dotdict
    :summary:
    ```
* - {py:obj}`apply_auto_deepcopy_to_module <agentsociety.agent.context.apply_auto_deepcopy_to_module>`
  - ```{autodoc2-docstring} agentsociety.agent.context.apply_auto_deepcopy_to_module
    :summary:
    ```
````

### API

````{py:class} AgentContext(/, **data: typing.Any)
:canonical: agentsociety.agent.context.AgentContext

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.agent.context.AgentContext
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.agent.context.AgentContext.__init__
```

````

````{py:class} BlockContext(/, **data: typing.Any)
:canonical: agentsociety.agent.context.BlockContext

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.agent.context.BlockContext
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.agent.context.BlockContext.__init__
```

````

`````{py:class} DotDict(*args, **kwargs)
:canonical: agentsociety.agent.context.DotDict

Bases: {py:obj}`dict`

```{autodoc2-docstring} agentsociety.agent.context.DotDict
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.agent.context.DotDict.__init__
```

````{py:method} __getattr__(key)
:canonical: agentsociety.agent.context.DotDict.__getattr__

```{autodoc2-docstring} agentsociety.agent.context.DotDict.__getattr__
```

````

````{py:method} __setattr__(key, value)
:canonical: agentsociety.agent.context.DotDict.__setattr__

````

````{py:method} __delattr__(key)
:canonical: agentsociety.agent.context.DotDict.__delattr__

````

````{py:method} merge(other)
:canonical: agentsociety.agent.context.DotDict.merge

```{autodoc2-docstring} agentsociety.agent.context.DotDict.merge
```

````

````{py:method} __or__(other)
:canonical: agentsociety.agent.context.DotDict.__or__

```{autodoc2-docstring} agentsociety.agent.context.DotDict.__or__
```

````

````{py:method} __ior__(other)
:canonical: agentsociety.agent.context.DotDict.__ior__

```{autodoc2-docstring} agentsociety.agent.context.DotDict.__ior__
```

````

`````

````{py:function} context_to_dot_dict(context: typing.Union[agentsociety.agent.context.AgentContext, agentsociety.agent.context.BlockContext]) -> agentsociety.agent.context.DotDict
:canonical: agentsociety.agent.context.context_to_dot_dict

```{autodoc2-docstring} agentsociety.agent.context.context_to_dot_dict
```
````

````{py:function} auto_deepcopy_dotdict(func)
:canonical: agentsociety.agent.context.auto_deepcopy_dotdict

```{autodoc2-docstring} agentsociety.agent.context.auto_deepcopy_dotdict
```
````

````{py:function} apply_auto_deepcopy_to_module(module)
:canonical: agentsociety.agent.context.apply_auto_deepcopy_to_module

```{autodoc2-docstring} agentsociety.agent.context.apply_auto_deepcopy_to_module
```
````
