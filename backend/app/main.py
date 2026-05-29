"""
Graph RAG System - FastAPI Main Application Entry Point

Feature Overview:
- Health check API (Neo4j / Milvus connectivity)
- PDF upload, OCR text extraction, text chunking (LangChain RecursiveCharacterTextSplitter),
  vector embedding (LangChain OpenAIEmbeddings → Milvus), triple extraction
  (LangChain ChatOpenAI), and knowledge graph construction (Neo4j)
- PDF list retrieval and bulk deletion
- Graph RAG Q&A (LangChain LCEL pipeline, JSON response & SSE streaming)
- Citation text block retrieval (per conversation)
- System statistics API (chunk count, node/edge count, PDF count)

Tech Stack Update:
- LLM: LangChain ChatOpenAI (was raw openai SDK)
- Embedding: LangChain OpenAIEmbeddings (was raw openai SDK)
- Text Splitting: LangChain RecursiveCharacterTextSplitter (was custom fixed-size)
- Vector Store: langchain-milvus integration (was raw pymilvus)

Startup:
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logger import logger
from app.models.database import neo4j_conn, milvus_conn

# Import routers
from app.api.health import router as health_router
from app.api.pdf import router as pdf_router
from app.api.chat import router as chat_router
from app.api.system import router as system_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle management
    - On startup: Connect to databases, initialize collections
    - On shutdown: Release database connections
    """
    settings = get_settings()
    logger.info("=" * 60)
    logger.info("Graph RAG System is starting...")
    logger.info("=" * 60)

    # ── Startup phase ──
    # Connect to Neo4j
    try:
        await neo4j_conn.connect()
    except Exception as e:
        logger.warning("Neo4j connection failed, some features may be unavailable: %s", str(e))

    # Connect to Milvus and ensure collection exists
    try:
        milvus_conn.connect()
        milvus_conn.ensure_collection()
    except Exception as e:
        logger.warning("Milvus connection failed, some features may be unavailable: %s", str(e))

    logger.info("Graph RAG System startup complete ✓")
    logger.info("API docs: http://%s:%d/docs", settings.APP_HOST, settings.APP_PORT)
    yield

    # ── Shutdown phase ──
    logger.info("Graph RAG System is shutting down...")
    await neo4j_conn.close()
    milvus_conn.close()
    logger.info("Graph RAG System has been shut down")


# ── Create FastAPI application ──
app = FastAPI(
    title="Graph RAG System API",
    description=(
        "Web backend for a Knowledge Graph-based RAG (Retrieval-Augmented Generation) system\n\n"
        "## Core Features\n"
        "- PDF file upload, OCR text extraction, automatic knowledge graph construction\n"
        "- Graph RAG Q&A based on Milvus vector retrieval + Neo4j subgraph retrieval\n"
        "- Supports JSON and SSE streaming response modes\n\n"
        "## Tech Stack\n"
        "- FastAPI + Uvicorn\n"
        "- Neo4j (Knowledge Graph)\n"
        "- Milvus (Vector Database)\n"
        "- LangChain (LLM / Embedding / Text Splitting / Vector Store)\n"
        "- OpenAI-compatible API (OCR / Embedding / LLM)"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS middleware ──
#
# Production example:
#   allow_origins=[
#       "https://your-frontend-domain.com",
#       "https://staging.your-frontend-domain.com",
#   ],
#   allow_credentials=True,
#   allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
#   allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
#
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routers ──
app.include_router(health_router)
app.include_router(pdf_router)
app.include_router(chat_router)
app.include_router(system_router)


# ── Root path redirect ──
@app.get("/", tags=["Root"], include_in_schema=False)
async def root():
    """Root path, redirect to API docs"""
    return {
        "message": "Graph RAG System API",
        "docs": "/docs"
    }
    
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    from fastapi.responses import FileResponse
    return FileResponse("app/static/favicon.ico")



if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True,
        log_level=settings.LOG_LEVEL.lower(),
    )