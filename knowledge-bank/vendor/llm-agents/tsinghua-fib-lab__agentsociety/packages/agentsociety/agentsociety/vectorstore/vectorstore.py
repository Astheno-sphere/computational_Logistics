import asyncio
import uuid
from typing import Optional

from fastembed import SparseTextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance

from ..utils.decorators import lock_decorator

__all__ = ["VectorStore"]


class VectorStore:
    """
    A class for handling similarity searches and document management using Qdrant and FastEmbed.

    - **Description**:
        - This class provides functionalities to manage embeddings and perform similarity searches over a set of documents.
        - It uses FastEmbed for generating embeddings and Qdrant for vector storage and retrieval.
        - The class initializes with an optional embedding model and Qdrant client settings.
    """

    def __init__(
        self,
        embedding: SparseTextEmbedding,
    ):
        """
        Initialize the VectorStore instance.

        - **Parameters**:
            - `embedding` (SparseTextEmbedding): The embedding model to use.
        """
        self._embeddings = embedding
        self._collection_name = "documents"
        self._lock = asyncio.Lock()
        self._client = QdrantClient(":memory:")

        self._client.create_collection(
            collection_name=self._collection_name,
            # the size is meaningless, just for compatibility
            # because we only use sparse vector
            vectors_config=models.VectorParams(size=384, distance=Distance.COSINE),
            sparse_vectors_config={
                "text-sparse": models.SparseVectorParams(
                    index=models.SparseIndexParams(
                        on_disk=False,
                    )
                )
            },
        )

    @property
    def embeddings(self):
        return self._embeddings

    @lock_decorator
    async def add_documents(
        self,
        documents: list[str],
        extra_tags: Optional[dict] = None,
    ) -> list[str]:
        """
        Add documents to the vector store with metadata.

        - **Description**:
            - Asynchronously adds one or more documents to the vector store, associating them with an agent ID and optional extra tags.
            - Each document is converted into a vector using FastEmbed before being added to Qdrant.

        - **Args**:
            - `documents` (list[str]): A list of document strings to add.
            - `extra_tags` (Optional[dict], optional): Additional metadata tags to associate with the documents. Defaults to None.

        - **Returns**:
            - `list[str]`: List of document IDs (UUIDs) that were added to the vector store.
        """
        # Generate embeddings
        embeddings = self._embeddings.embed(documents)

        # Prepare points for Qdrant
        points = []
        for i, (doc, embedding) in enumerate(zip(documents, embeddings)):
            metadata = {"content": doc}
            if extra_tags is not None:
                metadata.update(extra_tags)

            # Generate a UUID for the point
            point_id = str(uuid.uuid4())

            points.append(
                models.PointStruct(
                    id=point_id,
                    vector={
                        "text-sparse": models.SparseVector(
                            indices=embedding.indices.tolist(),
                            values=embedding.values.tolist(),
                        )
                    },
                    payload=metadata,
                )
            )

        # Upload points to Qdrant
        self._client.upsert(collection_name=self._collection_name, points=points)

        return [point.id for point in points]

    @lock_decorator
    async def delete_documents(
        self,
        to_delete_ids: list[str],
    ):
        """
        Delete documents from the vector store by IDs.

        - **Description**:
            - Asynchronously deletes documents from the vector store based on provided document IDs.

        - **Args**:
            - `to_delete_ids` (list[str]): List of document IDs (UUIDs) to delete from the vector store.
        """
        self._client.delete(
            collection_name=self._collection_name,
            points_selector=models.PointIdsList(
                points=to_delete_ids  # type: ignore[arg-type]
            ),
        )

    @lock_decorator
    async def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[dict] = None,
    ) -> list[tuple[str, float, dict]]:
        """
        Perform a similarity search for documents related to the given query.

        - **Description**:
            - Conducts an asynchronous search for the top-k documents most similar to the query text.
            - Uses FastEmbed to generate query embedding and Qdrant for vector search.

        - **Args**:
            - `query` (str): The text to look up documents similar to.
            - `k` (int, optional): The number of top similar contents to return. Defaults to 4.
            - `fetch_k` (int, optional): The number of documents to fetch before applying any filters. Defaults to 20.
            - `filter` (Optional[dict], optional): The filter dict for metadata.

        - **Returns**:
            - `list[tuple[str, float, dict]]`: List of tuples containing content, score, and metadata.
        """
        # Generate query embedding
        query_embedding = list(self._embeddings.query_embed(query))[0]

        # Prepare filter
        search_filter = {}
        if filter is not None:
            search_filter.update(filter)

        # Create NamedSparseVector for the query
        named_vector = models.NamedSparseVector(
            name="text-sparse",
            vector=models.SparseVector(
                indices=query_embedding.indices.tolist(),
                values=query_embedding.values.tolist(),
            ),
        )

        # Perform search
        must_conditions = []
        for key, value in search_filter.items():
            if isinstance(value, dict):
                must_conditions.append(
                    models.FieldCondition(
                        key=key,
                        range=models.Range(
                            gte=value.get("gte"),
                            lte=value.get("lte"),
                            gt=value.get("gt"),
                            lt=value.get("lt"),
                        ),
                    )
                )
            else:
                # Handle exact match filter
                must_conditions.append(
                    models.FieldCondition(key=key, match=models.MatchValue(value=value))
                )

        search_result = self._client.search(
            collection_name=self._collection_name,
            query_vector=named_vector,
            limit=k,
            query_filter=models.Filter(must=must_conditions),
        )

        # Format results
        results = []
        for hit in search_result:
            assert hit.payload is not None
            content = hit.payload.get("content", "")
            score = hit.score
            metadata = {k: v for k, v in hit.payload.items() if k != "content"}
            results.append((content, score, metadata))

        return results
