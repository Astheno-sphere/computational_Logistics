# {py:mod}`agentsociety.s3.client`

```{py:module} agentsociety.s3.client
```

```{autodoc2-docstring} agentsociety.s3.client
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`S3Config <agentsociety.s3.client.S3Config>`
  - ```{autodoc2-docstring} agentsociety.s3.client.S3Config
    :summary:
    ```
* - {py:obj}`S3Client <agentsociety.s3.client.S3Client>`
  - ```{autodoc2-docstring} agentsociety.s3.client.S3Client
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.s3.client.__all__>`
  - ```{autodoc2-docstring} agentsociety.s3.client.__all__
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.s3.client.__all__
:value: >
   ['S3Config']

```{autodoc2-docstring} agentsociety.s3.client.__all__
```

````

`````{py:class} S3Config(/, **data: typing.Any)
:canonical: agentsociety.s3.client.S3Config

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.s3.client.S3Config
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.s3.client.S3Config.__init__
```

````{py:attribute} enabled
:canonical: agentsociety.s3.client.S3Config.enabled
:type: bool
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.s3.client.S3Config.enabled
```

````

````{py:attribute} endpoint
:canonical: agentsociety.s3.client.S3Config.endpoint
:type: str
:value: <Multiline-String>

```{autodoc2-docstring} agentsociety.s3.client.S3Config.endpoint
```

````

````{py:attribute} access_key
:canonical: agentsociety.s3.client.S3Config.access_key
:type: str
:value: <Multiline-String>

```{autodoc2-docstring} agentsociety.s3.client.S3Config.access_key
```

````

````{py:attribute} secret_key
:canonical: agentsociety.s3.client.S3Config.secret_key
:type: str
:value: <Multiline-String>

```{autodoc2-docstring} agentsociety.s3.client.S3Config.secret_key
```

````

````{py:attribute} bucket
:canonical: agentsociety.s3.client.S3Config.bucket
:type: str
:value: <Multiline-String>

```{autodoc2-docstring} agentsociety.s3.client.S3Config.bucket
```

````

````{py:attribute} region
:canonical: agentsociety.s3.client.S3Config.region
:type: str
:value: <Multiline-String>

```{autodoc2-docstring} agentsociety.s3.client.S3Config.region
```

````

````{py:attribute} prefix
:canonical: agentsociety.s3.client.S3Config.prefix
:type: str
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.s3.client.S3Config.prefix
```

````

`````

`````{py:class} S3Client(config: agentsociety.s3.client.S3Config)
:canonical: agentsociety.s3.client.S3Client

```{autodoc2-docstring} agentsociety.s3.client.S3Client
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.s3.client.S3Client.__init__
```

````{py:method} _get_s3_path(remote_path: str) -> str
:canonical: agentsociety.s3.client.S3Client._get_s3_path

```{autodoc2-docstring} agentsociety.s3.client.S3Client._get_s3_path
```

````

````{py:method} upload(data: bytes, remote_path: str)
:canonical: agentsociety.s3.client.S3Client.upload

```{autodoc2-docstring} agentsociety.s3.client.S3Client.upload
```

````

````{py:method} download(remote_path: str) -> bytes
:canonical: agentsociety.s3.client.S3Client.download

```{autodoc2-docstring} agentsociety.s3.client.S3Client.download
```

````

````{py:method} exists(remote_path: str) -> bool
:canonical: agentsociety.s3.client.S3Client.exists

```{autodoc2-docstring} agentsociety.s3.client.S3Client.exists
```

````

````{py:method} delete(remote_path: str)
:canonical: agentsociety.s3.client.S3Client.delete

```{autodoc2-docstring} agentsociety.s3.client.S3Client.delete
```

````

`````
