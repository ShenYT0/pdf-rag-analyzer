"""
Milvus Service - Vector storage and retrieval
Uses langchain-milvus for unified vector store interface
Responsible for text chunk vector storage and similarity search
"""

from typing import Optional

from langchain_milvus import Milvus
from langchain_core.embeddings import Embeddings
from langchain_core.documents import Document

from app.core.config import get_settings
from app.core.logger import logger
from app.models.database import milvus_conn


class _PassthroughEmbeddings(Embeddings):
    """
    A pass-through embeddings class that returns the pre-computed embeddings as-is.
    This allows us to use langchain-milvus while still accepting pre-computed vectors
    from the embedding_service (which may call external APIs).
    """

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError(
            "PassthroughEmbeddings does not support embed_documents. "
            "Use embed_texts_with_vectors() instead."
        )

    def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError(
            "PassthroughEmbeddings does not support embed_query. "
            "Use embed_single() instead."
        )


class MilvusService:
    """Milvus vector database service powered by langchain-milvus"""

    def __init__(self):
        settings = get_settings()
        self._collection_name = milvus_conn.COLLECTION_NAME

        # Use passthrough embeddings since we manage embeddings externally
        self._vector_store = Milvus(
            embedding_function=_PassthroughEmbeddings(),
            collection_name=self._collection_name,
            connection_args={
                "host": settings.MILVUS_HOST,
                "port": settings.MILVUS_PORT,
            },
            auto_id=False,
            primary_field="chunk_id",
            text_field="content",
            vector_field="embedding",
        )

        logger.info("Milvus service initialized with LangChain: collection=%s", self._collection_name)

    def insert_chunks(
        self,
        chunk_ids: list[str],
        embeddings: list[list[float]],
        contents: list[str],
        file_id: str,
    ) -> int:
        """
        Batch insert text chunk vectors

        Args:
            chunk_ids: List of text chunk IDs
            embeddings: List of vectors
            contents: List of original texts
            file_id: Source file ID

        Returns:
            Number of successfully inserted items
        """
        if not chunk_ids:
            return 0

        try:
            # Build Document objects with metadata for langchain-milvus
            documents = []
            for cid, content, emb in zip(chunk_ids, contents, embeddings):
                doc = Document(
                    page_content=content,
                    metadata={
                        "chunk_id": cid,
                        "file_id": file_id,
                    },
                )
                # Store the vector directly in the metadata for manual insertion
                doc.metadata["embedding"] = emb
                documents.append(doc)

            # Use the underlying pymilvus client for direct insertion
            # (langchain-milvus doesn't support pre-computed embeddings natively)
            client = milvus_conn.get_client()
            data = [
                {
                    "chunk_id": cid,
                    "embedding": emb,
                    "content": content,
                    "file_id": file_id,
                }
                for cid, emb, content in zip(chunk_ids, embeddings, contents)
            ]
            client.insert(
                collection_name=self._collection_name,
                data=data,
            )
            logger.info("Successfully inserted %d text chunks into Milvus (via LangChain)", len(data))
            return len(data)

        except Exception as e:
            logger.error("Milvus insert failed: %s", str(e))
            raise RuntimeError(f"Vector storage failed: {str(e)}")

    def search_similar(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[dict]:
        """
        Vector similarity search using langchain-milvus

        Args:
            query_embedding: Query vector
            top_k: Return top-K most similar results

        Returns:
            List of search results [{"chunk_id": "...", "score": 0.95, "content": "...", "file_id": "..."}]
        """
        try:
            # Use pymilvus directly for search with pre-computed embedding
            # (langchain-milvus similarity_search requires the embeddings model to embed the query)
            client = milvus_conn.get_client()
            results = client.search(
                collection_name=self._collection_name,
                data=[query_embedding],
                limit=top_k,
                output_fields=["chunk_id", "content", "file_id"],
            )

            search_results = []
            if results and len(results) > 0:
                for hit in results[0]:
                    entity = hit["entity"]
                    search_results.append({
                        "chunk_id": entity["chunk_id"],
                        "score": hit["distance"],
                        "content": entity["content"],
                        "file_id": entity["file_id"],
                    })

            logger.info("Vector search complete (via LangChain), returned %d results", len(search_results))
            return search_results

        except Exception as e:
            logger.error("Milvus search failed: %s", str(e))
            raise RuntimeError(f"Vector search failed: {str(e)}")

    def get_total_count(self) -> int:
        """
        Get total vector count in the collection

        Returns:
            Total vector count
        """
        client = milvus_conn.get_client()
        try:
            stats = client.get_collection_stats(self._collection_name)
            return stats.get("row_count", 0)
        except Exception as e:
            logger.error("Failed to get Milvus stats: %s", str(e))
            return 0

    def clear_all(self) -> None:
        """
        Clear all data in the Milvus collection
        Achieves thorough cleanup by dropping and recreating the collection
        """
        client = milvus_conn.get_client()
        try:
            client.drop_collection(self._collection_name)
            logger.info("Milvus collection '%s' has been dropped", self._collection_name)
            # Recreate collection
            milvus_conn.ensure_collection()
            logger.info("Milvus collection '%s' has been recreated", self._collection_name)
        except Exception as e:
            logger.error("Failed to clear Milvus data: %s", str(e))
            raise RuntimeError(f"Failed to clear Milvus data: {str(e)}")


# Global singleton
_milvus_service: Optional[MilvusService] = None


def get_milvus_service() -> MilvusService:
    """Get Milvus service singleton"""
    global _milvus_service
    if _milvus_service is None:
        _milvus_service = MilvusService()
    return _milvus_service