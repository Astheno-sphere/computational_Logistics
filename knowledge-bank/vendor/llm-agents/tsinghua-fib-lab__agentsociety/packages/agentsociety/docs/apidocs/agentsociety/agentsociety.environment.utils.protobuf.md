# {py:mod}`agentsociety.environment.utils.protobuf`

```{py:module} agentsociety.environment.utils.protobuf
```

```{autodoc2-docstring} agentsociety.environment.utils.protobuf
:allowtitles:
```

## Module Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`parse <agentsociety.environment.utils.protobuf.parse>`
  - ```{autodoc2-docstring} agentsociety.environment.utils.protobuf.parse
    :summary:
    ```
* - {py:obj}`async_parse <agentsociety.environment.utils.protobuf.async_parse>`
  - ```{autodoc2-docstring} agentsociety.environment.utils.protobuf.async_parse
    :summary:
    ```
* - {py:obj}`pb2dict <agentsociety.environment.utils.protobuf.pb2dict>`
  - ```{autodoc2-docstring} agentsociety.environment.utils.protobuf.pb2dict
    :summary:
    ```
* - {py:obj}`dict2pb <agentsociety.environment.utils.protobuf.dict2pb>`
  - ```{autodoc2-docstring} agentsociety.environment.utils.protobuf.dict2pb
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.environment.utils.protobuf.__all__>`
  - ```{autodoc2-docstring} agentsociety.environment.utils.protobuf.__all__
    :summary:
    ```
* - {py:obj}`T <agentsociety.environment.utils.protobuf.T>`
  - ```{autodoc2-docstring} agentsociety.environment.utils.protobuf.T
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.environment.utils.protobuf.__all__
:value: >
   ['parse', 'async_parse', 'pb2dict', 'dict2pb']

```{autodoc2-docstring} agentsociety.environment.utils.protobuf.__all__
```

````

````{py:data} T
:canonical: agentsociety.environment.utils.protobuf.T
:value: >
   'TypeVar(...)'

```{autodoc2-docstring} agentsociety.environment.utils.protobuf.T
```

````

````{py:function} parse(res: agentsociety.environment.utils.protobuf.T, dict_return: bool) -> typing.Union[dict[str, typing.Any], agentsociety.environment.utils.protobuf.T]
:canonical: agentsociety.environment.utils.protobuf.parse

```{autodoc2-docstring} agentsociety.environment.utils.protobuf.parse
```
````

````{py:function} async_parse(res: collections.abc.Awaitable[agentsociety.environment.utils.protobuf.T], dict_return: bool) -> typing.Union[dict[str, typing.Any], agentsociety.environment.utils.protobuf.T]
:canonical: agentsociety.environment.utils.protobuf.async_parse
:async:

```{autodoc2-docstring} agentsociety.environment.utils.protobuf.async_parse
```
````

````{py:function} pb2dict(pb: google.protobuf.message.Message)
:canonical: agentsociety.environment.utils.protobuf.pb2dict

```{autodoc2-docstring} agentsociety.environment.utils.protobuf.pb2dict
```
````

````{py:function} dict2pb(d: dict, pb: agentsociety.environment.utils.protobuf.T) -> agentsociety.environment.utils.protobuf.T
:canonical: agentsociety.environment.utils.protobuf.dict2pb

```{autodoc2-docstring} agentsociety.environment.utils.protobuf.dict2pb
```
````
