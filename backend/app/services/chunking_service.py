"""
Text Chunking Service - Splits long text into semantically meaningful chunks
Uses langchain-text-splitters RecursiveCharacterTextSplitter for intelligent splitting
"""

import uuid
from typing import Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import get_settings
from app.core.logger import logger
from app.models.schemas import ChunkData


class ChunkingService:
    """Text chunking service powered by LangChain RecursiveCharacterTextSplitter"""

    def __init__(self):
        settings = get_settings()
        self._chunk_size = settings.CHUNK_SIZE
        self._chunk_overlap = settings.CHUNK_OVERLAP

        # LangChain RecursiveCharacterTextSplitter
        # Uses a prioritized list of separators to split text at semantically natural boundaries
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=self._chunk_size,
            chunk_overlap=self._chunk_overlap,
            separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""],
            length_function=len,
            keep_separator=False,
        )

        logger.info(
            "Chunking service initialized with LangChain: chunk_size=%d, overlap=%d",
            self._chunk_size,
            self._chunk_overlap,
        )

    def split_text(self, text: str, file_id: str) -> list[ChunkData]:
        """
        Split text into semantically meaningful chunks

        Uses RecursiveCharacterTextSplitter to split at paragraph/sentence boundaries
        while respecting chunk_size and chunk_overlap constraints.

        Args:
            text: Input text
            file_id: Source file ID

        Returns:
            List of ChunkData
        """
        if not text or not text.strip():
            return []

        text = text.strip()
        raw_chunks = self._splitter.split_text(text)

        chunks: list[ChunkData] = []
        for index, chunk_text in enumerate(raw_chunks):
            chunk_text = chunk_text.strip()
            if chunk_text:
                chunk = ChunkData(
                    chunk_id=str(uuid.uuid4()),
                    content=chunk_text,
                    file_id=file_id,
                    index=index,
                )
                chunks.append(chunk)

        logger.info(
            "Text chunking complete: total_len=%d, chunk_size=%d, overlap=%d, chunk_count=%d",
            len(text), self._chunk_size, self._chunk_overlap, len(chunks),
        )
        return chunks


# Global singleton
_chunking_service: Optional[ChunkingService] = None


def get_chunking_service() -> ChunkingService:
    """Get Chunking service singleton"""
    global _chunking_service
    if _chunking_service is None:
        _chunking_service = ChunkingService()
    return _chunking_service