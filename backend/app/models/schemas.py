"""
Pydantic Data Models - Defines all API request/response structures
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ────────────────── Health Check ──────────────────

class HealthResponse(BaseModel):
    """Health check response"""
    status: str = "ok"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    neo4j_connected: bool = False
    milvus_connected: bool = False
    version: str = "1.0.0"


# ────────────────── PDF Upload ──────────────────

class PDFUploadResponse(BaseModel):
    """PDF upload processing response"""
    file_id: str
    filename: str
    total_chunks: int
    total_entities: int
    total_relations: int
    message: str = "PDF processed successfully"


# ────────────────── Chat ──────────────────

class ChatRequest(BaseModel):
    """Chat request"""
    query: str = Field(..., min_length=1, description="User query content")
    top_k: Optional[int] = Field(None, description="Number of Top-K similar text chunks to retrieve")
    chat_id: Optional[str] = Field(None, description="Session ID for tracking context")


class ChatMessage(BaseModel):
    """Single chat message"""
    role: str
    content: str


class ChatResponse(BaseModel):
    """Chat response (JSON)"""
    chat_id: str
    query: str
    answer: str
    citations: list[dict] = Field(default_factory=list, description="Cited text block information")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StreamChunk(BaseModel):
    """Single chunk for SSE streaming response"""
    chat_id: str
    delta: str
    finished: bool = False


# ────────────────── Citations ──────────────────

class CitationItem(BaseModel):
    """Single citation entry"""
    chunk_id: str
    score: float
    content: str
    source_file: Optional[str] = None


class CitationsResponse(BaseModel):
    """Citation list response"""
    chat_id: str
    citations: list[CitationItem]


# ────────────────── System Statistics ──────────────────

class SystemStats(BaseModel):
    """System statistics"""
    total_chunks: int = 0
    total_nodes: int = 0
    total_edges: int = 0
    total_pdfs: int = 0


# ────────────────── PDF List ──────────────────

class PDFListItem(BaseModel):
    """Single file info in PDF list"""
    file_id: str
    filename: str
    upload_time: str
    total_chunks: int
    total_entities: int = 0
    total_relations: int = 0


class PDFListResponse(BaseModel):
    """PDF list response"""
    pdfs: list[PDFListItem]
    total: int


# ────────────────── Delete Operation ──────────────────

class DeleteAllResponse(BaseModel):
    """Delete all data response"""
    message: str


# ────────────────── Internal Data Structures ──────────────────

class ChunkData(BaseModel):
    """Text chunk data"""
    chunk_id: str
    content: str
    file_id: str
    index: int


class TripleData(BaseModel):
    """Triple data"""
    head: str
    relation: str
    tail: str


class GraphContext(BaseModel):
    """Graph retrieval context"""
    chunk_contents: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    relations: list[str] = Field(default_factory=list)