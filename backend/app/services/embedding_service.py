"""
Embedding Service - Vectorizes text
Auto-detects backend based on API key:
  - API key == "ollama" → langchain_ollama.OllamaEmbeddings (local)
  - otherwise           → langchain_openai.OpenAIEmbeddings (online/compatible)
"""

from typing import Optional

from langchain_core.embeddings import Embeddings

from app.core.config import get_settings
from app.core.logger import logger


def _is_ollama(api_key: str) -> bool:
    """Return True when the API key signals a local Ollama backend."""
    return api_key.strip().lower() == "ollama"


def _strip_v1(url: str) -> str:
    """
    langchain_ollama expects the bare Ollama host (e.g. http://localhost:11434),
    not the OpenAI-compat path (http://localhost:11434/v1).
    """
    return url.rstrip("/").removesuffix("/v1")


def _build_embeddings(model: str, api_key: str, base_url: str) -> Embeddings:
    """
    Factory: return the appropriate LangChain Embeddings instance.

    Args:
        model:    Model name
        api_key:  API key (use "ollama" to select the local Ollama backend)
        base_url: Base URL from config

    Returns:
        A LangChain Embeddings instance
    """
    if _is_ollama(api_key):
        from langchain_ollama import OllamaEmbeddings
        ollama_url = _strip_v1(base_url)
        logger.info(
            "Embedding backend: Ollama  model=%s  base_url=%s", model, ollama_url
        )
        return OllamaEmbeddings(model=model, base_url=ollama_url)
    else:
        from langchain_openai import OpenAIEmbeddings
        logger.info(
            "Embedding backend: OpenAI-compatible  model=%s  base_url=%s",
            model, base_url,
        )
        return OpenAIEmbeddings(model=model, api_key=api_key, base_url=base_url)


class EmbeddingService:
    """
    Text vectorization service.
    Automatically selects langchain_ollama or langchain_openai based on the
    EMBEDDING_API_KEY value in .env.
    """

    def __init__(self):
        settings = get_settings()
        self._model = settings.EMBEDDING_MODEL
        self._embeddings: Embeddings = _build_embeddings(
            model=settings.EMBEDDING_MODEL,
            api_key=settings.EMBEDDING_API_KEY,
            base_url=settings.EMBEDDING_BASE_URL,
        )

    async def embed_single(self, text: str) -> list[float]:
        """
        Vectorize a single text.

        Args:
            text: Input text

        Returns:
            Float vector
        """
        return await self._embeddings.aembed_query(text)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Batch vectorize texts.

        Args:
            texts: List of texts

        Returns:
            List of vectors
        """
        if not texts:
            return []

        try:
            embeddings = await self._embeddings.aembed_documents(texts)
            logger.debug(
                "Batch vectorization complete, count=%d, dim=%d",
                len(embeddings),
                len(embeddings[0]) if embeddings else 0,
            )
            return embeddings

        except Exception as e:
            logger.error("Embedding request failed: %s", str(e))
            raise RuntimeError(f"Embedding service error: {str(e)}")


# Global singleton
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get Embedding service singleton"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service