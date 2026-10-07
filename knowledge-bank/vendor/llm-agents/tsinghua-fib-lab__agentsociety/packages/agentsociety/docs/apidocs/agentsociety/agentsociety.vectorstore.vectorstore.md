# {py:mod}`agentsociety.vectorstore.vectorstore`

```{py:module} agentsociety.vectorstore.vectorstore
```

```{autodoc2-docstring} agentsociety.vectorstore.vectorstore
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`VectorStore <agentsociety.vectorstore.vectorstore.VectorStore>`
  - ```{autodoc2-docstring} agentsociety.vectorstore.vectorstore.VectorStore
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.vectorstore.vectorstore.__all__>`
  - ```{autodoc2-docstring} agentsociety.vectorstore.vectorstore.__all__
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.vectorstore.vectorstore.__all__
:value: >
   ['VectorStore']

```{autodoc2-docstring} agentsociety.vectorstore.vectorstore.__all__
```

````

`````{py:class} VectorStore(embedding: fastembed.SparseTextEmbedding)
:canonical: agentsociety.vectorstore.vectorstore.VectorStore

```{autodoc2-docstring} agentsociety.vectorstore.vectorstore.VectorStore
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.vectorstore.vectorstore.VectorStore.__init__
```

````{py:property} embeddings
:canonical: agentsociety.vectorstore.vectorstore.VectorStore.embeddings

```{autodoc2-docstring} agentsociety.vectorstore.vectorstore.VectorStore.embeddings
```

````

````{py:method} add_documents(documents: list[str], extra_tags: typing.Optional[dict] = None) -> list[str]
:canonical: agentsociety.vectorstore.vectorstore.VectorStore.add_documents
:async:

```{autodoc2-docstring} agentsociety.vectorstore.vectorstore.VectorStore.add_documents
```

````

````{py:method} delete_documents(to_delete_ids: list[str])
:canonical: agentsociety.vectorstore.vectorstore.VectorStore.delete_documents
:async:

```{autodoc2-docstring} agentsociety.vectorstore.vectorstore.VectorStore.delete_documents
```

````

````{py:method} similarity_search(query: str, k: int = 4, filter: typing.Optional[dict] = None) -> list[tuple[str, float, dict]]
:canonical: agentsociety.vectorstore.vectorstore.VectorStore.similarity_search
:async:

```{autodoc2-docstring} agentsociety.vectorstore.vectorstore.VectorStore.similarity_search
```

````

`````
