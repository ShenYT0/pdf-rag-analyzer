# pdf-rag-analyzer

A **Knowledge Graph-based RAG (Retrieval-Augmented Generation)** system that extracts, indexes, and queries information from PDF documents. Built with FastAPI, Neo4j, Milvus, and LangChain.

## Quick Start

```bash
# Start infrastructure (Neo4j + Milvus)
docker compose up -d

# Start backend API server
cd backend
python -m app.main
```

API docs available at `http://localhost:8000/docs`.

---

## Backend Architecture

```
backend/
├── app/
│   ├── api/            # REST API endpoints
│   │   ├── health.py   #   /health - System & DB connectivity check
│   │   ├── pdf.py      #   /v1/index - PDF upload, list, delete
│   │   ├── chat.py     #   /v1/chat - Graph RAG Q&A (JSON + SSE streaming)
│   │   └── system.py   #   /v1/system - System statistics
│   ├── core/           # Configuration & logging
│   │   ├── config.py   #   Environment-driven settings (.env)
│   │   └── logger.py   #   Structured logging
│   ├── models/         # Pydantic schemas & DB connections
│   │   ├── schemas.py  #   Request/response models
│   │   └── database.py #   Neo4j & Milvus client management
│   └── services/       # Core business logic
│       ├── ocr_service.py        # PDF text extraction (PyMuPDF + multimodal LLM fallback)
│       ├── chunking_service.py   # LangChain RecursiveCharacterTextSplitter
│       ├── embedding_service.py  # OpenAI/Ollama embeddings (auto-detected)
│       ├── milvus_service.py     # Vector storage & similarity search
│       ├── llm_service.py        # LLM chat & triple extraction
│       ├── neo4j_service.py      # Knowledge graph storage & retrieval
│       └── graph_rag_service.py  # Orchestration: full pipeline & RAG logic
├── .env.example        # Environment variable template
└── requirements.txt    # Python dependencies
```

### Pipeline: PDF → Knowledge Graph

```
PDF Upload
   │
   ▼
┌─────────────────┐
│   OCR Service   │  PyMuPDF direct extraction (text PDFs)
│   (ocr_service) │  Multimodal LLM fallback (scanned PDFs)
└────────┬────────┘
         ▼
┌─────────────────┐
│ Chunking Service │  LangChain RecursiveCharacterTextSplitter
│ (chunking_service)│  Chunk size: 500, overlap: 50
└────────┬────────┘
         ▼
┌────────────────────┐
│ Embedding Service  │  OpenAI/Ollama embeddings (auto-detect)
│ (embedding_service)│  → Milvus vector store (langchain-milvus)
└────────┬───────────┘
         ▼
┌──────────────────┐
│  LLM Service     │  Triple extraction (entity-relation-entity)
│  (llm_service)   │  → Neo4j knowledge graph
└──────────────────┘
```

### Tech Stack

| Component          | Technology                           |
|--------------------|--------------------------------------|
| **Web Framework**  | FastAPI + Uvicorn                    |
| **Graph DB**       | Neo4j 5 (Community) + APOC          |
| **Vector DB**      | Milvus 2.5 (Standalone, via pymilvus + langchain-milvus) |
| **LLM / Embedding**| LangChain (ChatOpenAI / OpenAIEmbeddings / ChatOllama) |
| **Text Splitting** | LangChain RecursiveCharacterTextSplitter |
| **PDF Processing** | PyMuPDF (direct) + Multimodal LLM (OCR fallback) |

### Flexible Backend Selection

All AI services (OCR, Embedding, LLM) support automatic backend switching via `.env`:

- **API key = `ollama`** → Uses local [Ollama](https://ollama.com/) models
- **Otherwise**     → Uses OpenAI-compatible API (OpenAI, GLM, vLLM, etc.)

### Available API Endpoints

| Method | Path                    | Description                                    |
|--------|-------------------------|------------------------------------------------|
| GET    | `/health`               | System health (Neo4j + Milvvus connectivity check) |
| POST   | `/v1/index/pdf`         | Upload PDF and build knowledge graph           |
| GET    | `/v1/index/pdfs`        | List all uploaded PDFs with stats              |
| DELETE | `/v1/index/pdfs`        | Clear all data (Milvus + Neo4j)                |
| POST   | `/v1/chat/completions`  | Graph RAG Q&A (JSON response)                  |
| POST   | `/v1/chat/stream`       | Graph RAG Q&A (SSE streaming response)         |
| GET    | `/v1/chat/citations/{chat_id}` | Get citation text blocks for a chat     |
| GET    | `/v1/system/stats`      | System statistics (chunks, nodes, edges, PDFs) |
| GET    | `/docs`                 | Swagger UI API documentation                   |
