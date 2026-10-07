# {py:mod}`agentsociety.filesystem.client`

```{py:module} agentsociety.filesystem.client
```

```{autodoc2-docstring} agentsociety.filesystem.client
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`FileSystemClient <agentsociety.filesystem.client.FileSystemClient>`
  - ```{autodoc2-docstring} agentsociety.filesystem.client.FileSystemClient
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.filesystem.client.__all__>`
  - ```{autodoc2-docstring} agentsociety.filesystem.client.__all__
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.filesystem.client.__all__
:value: >
   ['FileSystemClient']

```{autodoc2-docstring} agentsociety.filesystem.client.__all__
```

````

`````{py:class} FileSystemClient(home_dir: str)
:canonical: agentsociety.filesystem.client.FileSystemClient

```{autodoc2-docstring} agentsociety.filesystem.client.FileSystemClient
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.filesystem.client.FileSystemClient.__init__
```

````{py:method} get_absolute_path(remote_path: str) -> str
:canonical: agentsociety.filesystem.client.FileSystemClient.get_absolute_path

```{autodoc2-docstring} agentsociety.filesystem.client.FileSystemClient.get_absolute_path
```

````

````{py:method} upload(data: bytes, remote_path: str)
:canonical: agentsociety.filesystem.client.FileSystemClient.upload

```{autodoc2-docstring} agentsociety.filesystem.client.FileSystemClient.upload
```

````

````{py:method} download(remote_path: str) -> bytes
:canonical: agentsociety.filesystem.client.FileSystemClient.download

```{autodoc2-docstring} agentsociety.filesystem.client.FileSystemClient.download
```

````

````{py:method} exists(remote_path: str) -> bool
:canonical: agentsociety.filesystem.client.FileSystemClient.exists

```{autodoc2-docstring} agentsociety.filesystem.client.FileSystemClient.exists
```

````

````{py:method} delete(remote_path: str)
:canonical: agentsociety.filesystem.client.FileSystemClient.delete

```{autodoc2-docstring} agentsociety.filesystem.client.FileSystemClient.delete
```

````

`````
