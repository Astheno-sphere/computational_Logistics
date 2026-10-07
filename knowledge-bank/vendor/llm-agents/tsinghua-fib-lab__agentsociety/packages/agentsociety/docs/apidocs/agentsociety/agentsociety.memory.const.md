# {py:mod}`agentsociety.memory.const`

```{py:module} agentsociety.memory.const
```

```{autodoc2-docstring} agentsociety.memory.const
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`RelationType <agentsociety.memory.const.RelationType>`
  - ```{autodoc2-docstring} agentsociety.memory.const.RelationType
    :summary:
    ```
* - {py:obj}`SocialRelation <agentsociety.memory.const.SocialRelation>`
  - ```{autodoc2-docstring} agentsociety.memory.const.SocialRelation
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.memory.const.__all__>`
  - ```{autodoc2-docstring} agentsociety.memory.const.__all__
    :summary:
    ```
* - {py:obj}`PROFILE_ATTRIBUTES <agentsociety.memory.const.PROFILE_ATTRIBUTES>`
  - ```{autodoc2-docstring} agentsociety.memory.const.PROFILE_ATTRIBUTES
    :summary:
    ```
* - {py:obj}`STATE_ATTRIBUTES <agentsociety.memory.const.STATE_ATTRIBUTES>`
  - ```{autodoc2-docstring} agentsociety.memory.const.STATE_ATTRIBUTES
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.memory.const.__all__
:value: >
   ['RelationType', 'SocialRelation', 'PROFILE_ATTRIBUTES', 'STATE_ATTRIBUTES']

```{autodoc2-docstring} agentsociety.memory.const.__all__
```

````

`````{py:class} RelationType()
:canonical: agentsociety.memory.const.RelationType

Bases: {py:obj}`str`, {py:obj}`enum.Enum`

```{autodoc2-docstring} agentsociety.memory.const.RelationType
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.memory.const.RelationType.__init__
```

````{py:attribute} FRIEND
:canonical: agentsociety.memory.const.RelationType.FRIEND
:value: >
   'friend'

```{autodoc2-docstring} agentsociety.memory.const.RelationType.FRIEND
```

````

````{py:attribute} FAMILY
:canonical: agentsociety.memory.const.RelationType.FAMILY
:value: >
   'family'

```{autodoc2-docstring} agentsociety.memory.const.RelationType.FAMILY
```

````

````{py:attribute} COLLEAGUE
:canonical: agentsociety.memory.const.RelationType.COLLEAGUE
:value: >
   'colleague'

```{autodoc2-docstring} agentsociety.memory.const.RelationType.COLLEAGUE
```

````

````{py:attribute} FOLLOWER
:canonical: agentsociety.memory.const.RelationType.FOLLOWER
:value: >
   'follower'

```{autodoc2-docstring} agentsociety.memory.const.RelationType.FOLLOWER
```

````

````{py:attribute} FOLLOWING
:canonical: agentsociety.memory.const.RelationType.FOLLOWING
:value: >
   'following'

```{autodoc2-docstring} agentsociety.memory.const.RelationType.FOLLOWING
```

````

`````

`````{py:class} SocialRelation(/, **data: typing.Any)
:canonical: agentsociety.memory.const.SocialRelation

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.memory.const.SocialRelation
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.memory.const.SocialRelation.__init__
```

````{py:attribute} source_id
:canonical: agentsociety.memory.const.SocialRelation.source_id
:type: typing.Optional[int]
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.memory.const.SocialRelation.source_id
```

````

````{py:attribute} target_id
:canonical: agentsociety.memory.const.SocialRelation.target_id
:type: int
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.memory.const.SocialRelation.target_id
```

````

````{py:attribute} kind
:canonical: agentsociety.memory.const.SocialRelation.kind
:type: agentsociety.memory.const.RelationType
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.memory.const.SocialRelation.kind
```

````

````{py:attribute} strength
:canonical: agentsociety.memory.const.SocialRelation.strength
:type: typing.Optional[float]
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.memory.const.SocialRelation.strength
```

````

`````

````{py:data} PROFILE_ATTRIBUTES
:canonical: agentsociety.memory.const.PROFILE_ATTRIBUTES
:value: >
   None

```{autodoc2-docstring} agentsociety.memory.const.PROFILE_ATTRIBUTES
```

````

````{py:data} STATE_ATTRIBUTES
:canonical: agentsociety.memory.const.STATE_ATTRIBUTES
:value: >
   None

```{autodoc2-docstring} agentsociety.memory.const.STATE_ATTRIBUTES
```

````
