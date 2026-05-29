"""
Graph RAG Orchestration Service - Core business logic
Powered by LangChain LCEL (LangChain Expression Language)
Integrates the complete pipeline: OCR → Chunking → Vectorization → Graph Construction → Retrieval → Generation
"""

import uuid
import asyncio
from datetime import datetime
from typing import AsyncGenerator, Optional
from langchain_core.prompts import ChatPromptTemplate

from app.core.config import get_settings
from app.core.logger import logger
from app.models.schemas import (
    PDFUploadResponse,
    ChatResponse,
    StreamChunk,
    CitationsResponse,
    CitationItem,
    SystemStats,
    GraphContext,
    PDFListItem,
    PDFListResponse,
    DeleteAllResponse,
)

from app.models.database import neo4j_conn
from app.services.ocr_service import get_ocr_service
from app.services.embedding_service import get_embedding_service
from app.services.llm_service import get_llm_service
from app.services.milvus_service import get_milvus_service
from app.services.neo4j_service import get_neo4j_service
from app.services.chunking_service import get_chunking_service


class GraphRAGService:
    """Graph RAG core orchestration service powered by LangChain"""

    # In-memory store for chat citation records (chat_id -> citations)
    _chat_citations: dict[str, list[dict]] = {}

    # LangChain ChatPromptTemplate for RAG (used for reference/extension)
    _rag_prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a professional knowledge Q&A assistant. Please answer the user's question based on the retrieved context information below.\n"
            "Requirements:\n"
            "1. Prioritize using information from the context to answer\n"
            "2. If context information is insufficient, you may supplement with your knowledge, but clarify this\n"
            "3. Answers should be accurate, clear, and well-structured\n"
            "4. If you cannot answer, please honestly state so\n\n"
            "Context information:\n{context}"
        ),
        ("human", "{query}"),
    ])

    # ────────────────── PDF Processing Pipeline ──────────────────

    async def process_pdf(self, file_bytes: bytes, filename: str) -> PDFUploadResponse:
        """
        Complete PDF processing pipeline:
        1. OCR text extraction
        2. Text chunking (LangChain RecursiveCharacterTextSplitter)
        3. Vectorization (LangChain OpenAIEmbeddings) + Milvus storage (langchain-milvus)
        4. Triple extraction (LangChain ChatOpenAI) + Neo4j storage

        Args:
            file_bytes: PDF file binary content
            filename: File name

        Returns:
            PDFUploadResponse
        """
        file_id = str(uuid.uuid4())
        logger.info("Starting PDF processing: %s (file_id=%s)", filename, file_id)

        # Step 1: OCR text extraction
        ocr_service = get_ocr_service()
        full_text = await ocr_service.extract_text_from_pdf(file_bytes)

        if not full_text or not full_text.strip():
            raise ValueError("PDF text extraction failed, file may be empty or unparseable")

        # Step 2: Text chunking (powered by LangChain RecursiveCharacterTextSplitter)
        chunking_service = get_chunking_service()
        chunks = chunking_service.split_text(full_text, file_id)

        if not chunks:
            raise ValueError("Text chunking failed, no valid text blocks generated")

        logger.info("PDF chunking complete: %d text blocks", len(chunks))

        # Step 3: Batch vectorization (powered by LangChain OpenAIEmbeddings)
        embedding_service = get_embedding_service()
        contents = [c.content for c in chunks]
        embeddings = await embedding_service.embed_texts(contents)

        # Step 4: Store into Milvus (powered by langchain-milvus)
        milvus_service = get_milvus_service()
        chunk_ids = [c.chunk_id for c in chunks]
        milvus_service.insert_chunks(
            chunk_ids=chunk_ids,
            embeddings=embeddings,
            contents=contents,
            file_id=file_id,
        )

        upload_time_str = datetime.now().isoformat()

        # Step 5: Triple extraction (powered by LangChain ChatOpenAI) + Neo4j storage
        llm_service = get_llm_service()
        neo4j_service = get_neo4j_service()

        total_entities = 0
        total_relations = 0

        # Use a semaphore to limit concurrency and avoid API overload
        semaphore = asyncio.Semaphore(5)

        async def process_chunk(idx: int):
            nonlocal total_entities, total_relations
            chunk = chunks[idx]
            async with semaphore:
                try:
                    # Extract triples (powered by LangChain ChatPromptTemplate + ChatOpenAI)
                    triples = await llm_service.extract_triples(chunk.content)

                    # Store into Neo4j
                    e_count, r_count = await neo4j_service.store_triples(
                        triples=triples,
                        chunk_id=chunk.chunk_id,
                        file_id=file_id,
                        filename=filename,
                        upload_time=upload_time_str,
                    )
                    return e_count, r_count
                except Exception as e:
                    logger.warning("Failed to process chunk %d: %s", idx, str(e))
                    return 0, 0

        # Process all chunks concurrently
        results = await asyncio.gather(
            *[process_chunk(i) for i in range(len(chunks))],
            return_exceptions=True,
        )

        for r in results:
            if isinstance(r, tuple):
                total_entities += r[0]
                total_relations += r[1]

        logger.info(
            "PDF processing complete: file_id=%s, chunks=%d, entities=%d, relations=%d",
            file_id, len(chunks), total_entities, total_relations,
        )

        return PDFUploadResponse(
            file_id=file_id,
            filename=filename,
            total_chunks=len(chunks),
            total_entities=total_entities,
            total_relations=total_relations,
        )

    # ────────────────── Graph RAG Retrieval & Generation ──────────────────

    def _build_rag_context(self, graph_context: GraphContext) -> str:
        """
        Build context string for LangChain prompt from graph context

        Args:
            graph_context: Graph retrieval context

        Returns:
            Formatted context string
        """
        context_parts = []

        # Text block contents
        if graph_context.chunk_contents:
            context_parts.append("[Relevant Text Segments]")
            for i, content in enumerate(graph_context.chunk_contents, 1):
                context_parts.append(f"Segment {i}:\n{content}")

        # Graph entities
        if graph_context.entities:
            context_parts.append("\n[Knowledge Graph Entities]")
            context_parts.append(", ".join(graph_context.entities))

        # Graph relations
        if graph_context.relations:
            context_parts.append("\n[Knowledge Graph Relations]")
            for rel in graph_context.relations:
                context_parts.append(f"- {rel}")

        return "\n".join(context_parts) if context_parts else "No relevant context found"

    async def _retrieve_context(
        self,
        query: str,
        top_k: int = 5,
    ) -> tuple[list[dict], GraphContext]:
        """
        Graph RAG retrieval logic:
        1. Vectorize the query and retrieve Top-K similar chunks from Milvus
        2. Query related entities and subgraph relations from Neo4j using chunk_ids
        3. Fuse the context

        Args:
            query: User query
            top_k: Number of results to retrieve

        Returns:
            (Search result list, Graph context)
        """
        settings = get_settings()
        if top_k is None:
            top_k = settings.TOP_K

        # 1. Vectorize query (powered by LangChain OpenAIEmbeddings)
        embedding_service = get_embedding_service()
        query_embedding = await embedding_service.embed_single(query)

        # 2. Milvus vector search (powered by langchain-milvus)
        milvus_service = get_milvus_service()
        search_results = milvus_service.search_similar(query_embedding, top_k=top_k)

        if not search_results:
            return search_results, GraphContext()

        # 3. Neo4j subgraph retrieval
        chunk_ids = [r["chunk_id"] for r in search_results]
        neo4j_service = get_neo4j_service()
        subgraph = await neo4j_service.get_subgraph_by_chunk_ids(chunk_ids, max_depth=2)

        # 4. Build graph context
        graph_context = GraphContext(
            chunk_contents=[r["content"] for r in search_results],
            entities=[e["name"] for e in subgraph.get("entities", [])],
            relations=[
                f"{r['head']} -[{r['relation']}]-> {r['tail']}"
                for r in subgraph.get("relations", [])
            ],
        )

        return search_results, graph_context

    async def chat(self, query: str, top_k: Optional[int] = None, chat_id: Optional[str] = None) -> ChatResponse:
        """
        Standard (non-streaming) Graph RAG chat
        Uses LangChain LCEL chain for generation

        Args:
            query: User query
            top_k: Number of results to retrieve
            chat_id: Session ID

        Returns:
            ChatResponse
        """
        if not chat_id:
            chat_id = str(uuid.uuid4())

        logger.info("Received chat request: chat_id=%s, query=%s", chat_id, query[:50])

        # Retrieve context
        search_results, graph_context = await self._retrieve_context(query, top_k=top_k or get_settings().TOP_K)

        # Build context string
        context_str = self._build_rag_context(graph_context)

        # LLM generation via LangChain LCEL chain
        llm_service = get_llm_service()
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a professional knowledge Q&A assistant. Please answer the user's question based on the retrieved context information below.\n"
                    "Requirements:\n"
                    "1. Prioritize using information from the context to answer\n"
                    "2. If context information is insufficient, you may supplement with your knowledge, but clarify this\n"
                    "3. Answers should be accurate, clear, and well-structured\n"
                    "4. If you cannot answer, please honestly state so\n\n"
                    f"Context information:\n{context_str}"
                ),
            },
            {
                "role": "user",
                "content": query,
            },
        ]
        answer = await llm_service.chat(messages)

        # Save citation info
        citations = [
            {
                "chunk_id": r["chunk_id"],
                "score": r["score"],
                "content": r["content"][:200],  # Truncated for display
                "source_file": r.get("file_id", ""),
            }
            for r in search_results
        ]
        self._chat_citations[chat_id] = citations

        return ChatResponse(
            chat_id=chat_id,
            query=query,
            answer=answer,
            citations=citations,
        )

    async def chat_stream(
        self,
        query: str,
        top_k: Optional[int] = None,
        chat_id: Optional[str] = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Streaming (SSE) Graph RAG chat
        Uses LangChain streaming LLM for generation

        Args:
            query: User query
            top_k: Number of results to retrieve
            chat_id: Session ID

        Yields:
            StreamChunk
        """
        if not chat_id:
            chat_id = str(uuid.uuid4())

        logger.info("Received streaming chat request: chat_id=%s, query=%s", chat_id, query[:50])

        # Retrieve context
        search_results, graph_context = await self._retrieve_context(query, top_k=top_k or get_settings().TOP_K)

        # Save citation info
        citations = [
            {
                "chunk_id": r["chunk_id"],
                "score": r["score"],
                "content": r["content"][:200],
                "source_file": r.get("file_id", ""),
            }
            for r in search_results
        ]
        self._chat_citations[chat_id] = citations

        # Build context string
        context_str = self._build_rag_context(graph_context)

        # Streaming generation via LangChain
        llm_service = get_llm_service()
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a professional knowledge Q&A assistant. Please answer the user's question based on the retrieved context information below.\n"
                    "Requirements:\n"
                    "1. Prioritize using information from the context to answer\n"
                    "2. If context information is insufficient, you may supplement with your knowledge, but clarify this\n"
                    "3. Answers should be accurate, clear, and well-structured\n"
                    "4. If you cannot answer, please honestly state so\n\n"
                    f"Context information:\n{context_str}"
                ),
            },
            {
                "role": "user",
                "content": query,
            },
        ]
        async for delta in llm_service.chat_stream(messages):
            yield StreamChunk(chat_id=chat_id, delta=delta, finished=False)

        # Send end marker
        yield StreamChunk(chat_id=chat_id, delta="", finished=True)

    # ────────────────── Citation Query ──────────────────

    def get_citations(self, chat_id: str) -> Optional[CitationsResponse]:
        """
        Get citation info for a specific chat

        Args:
            chat_id: Session ID

        Returns:
            CitationsResponse or None
        """
        citations_data = self._chat_citations.get(chat_id)
        if citations_data is None:
            return None

        return CitationsResponse(
            chat_id=chat_id,
            citations=[
                CitationItem(
                    chunk_id=c["chunk_id"],
                    score=c["score"],
                    content=c["content"],
                    source_file=c.get("source_file"),
                )
                for c in citations_data
            ],
        )

    # ────────────────── PDF List ──────────────────

    async def list_pdfs(self) -> PDFListResponse:
        """
        Get info list of all uploaded PDFs

        Retrieves file metadata from Neo4j, and statistical counts from Milvus and Neo4j
        """
        neo4j_service = get_neo4j_service()
        pdf_records = await neo4j_service.list_pdfs()

        pdf_items = []
        for record in pdf_records:
            # For each file, count entity and relation counts in the graph
            file_id = record["file_id"]
            entities_count = 0
            relations_count = 0
            try:
                async with neo4j_conn.get_session() as session:
                    # Count entities associated with this file_id
                    result = await session.run(
                        """
                        MATCH (c:Chunk {file_id: $file_id})-[:CONTAINS]->(e:Entity)
                        RETURN count(DISTINCT e) AS entities
                        """,
                        file_id=file_id,
                    )
                    data = await result.data()
                    if data:
                        entities_count = data[0].get("entities", 0)

                    # Count relations associated with this file_id
                    result = await session.run(
                        """
                        MATCH (c:Chunk {file_id: $file_id})-[:CONTAINS]->(h:Entity)-[r:RELATES_TO]->(t:Entity)
                        RETURN count(DISTINCT r) AS relations
                        """,
                        file_id=file_id,
                    )
                    data = await result.data()
                    if data:
                        relations_count = data[0].get("relations", 0)
            except Exception as e:
                logger.warning("Failed to count graph data for file_id %s: %s", file_id, str(e))

            pdf_items.append(PDFListItem(
                file_id=file_id,
                filename=record.get("filename") or "",
                upload_time=record.get("upload_time") or "",
                total_chunks=record.get("total_chunks", 0),
                total_entities=entities_count,
                total_relations=relations_count,
            ))

        return PDFListResponse(pdfs=pdf_items, total=len(pdf_items))

    # ────────────────── Clear All Data ──────────────────

    async def clear_all(self) -> DeleteAllResponse:
        """
        Clear all data:
        1. Clear Milvus vector database
        2. Clear Neo4j knowledge graph
        """
        logger.info("Starting to clear all data...")

        # 1. Clear Milvus
        milvus_service = get_milvus_service()
        milvus_service.clear_all()

        # 2. Clear Neo4j
        neo4j_service = get_neo4j_service()
        await neo4j_service.clear_all()

        # 3. Clear in-memory chat citation cache
        self._chat_citations.clear()

        logger.info("All data has been cleared")
        return DeleteAllResponse(message="All data cleared successfully")

    # ────────────────── System Statistics ──────────────────

    async def get_system_stats(self) -> SystemStats:
        """
        Get system statistics

        Returns:
            SystemStats
        """
        milvus_service = get_milvus_service()
        neo4j_service = get_neo4j_service()

        # Concurrently query each database's stats
        chunks_count, nodes_count, edges_count, pdfs_count = await asyncio.gather(
            asyncio.to_thread(milvus_service.get_total_count),
            neo4j_service.get_total_nodes(),
            neo4j_service.get_total_edges(),
            neo4j_service.get_total_pdfs(),
        )

        return SystemStats(
            total_chunks=chunks_count,
            total_nodes=nodes_count,
            total_edges=edges_count,
            total_pdfs=pdfs_count,
        )

# Global singleton
_graph_rag_service: Optional[GraphRAGService] = None


def get_graph_rag_service() -> GraphRAGService:
    """Get Graph RAG service singleton"""
    global _graph_rag_service
    if _graph_rag_service is None:
        _graph_rag_service = GraphRAGService()
    return _graph_rag_service