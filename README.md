# pdf-rag-analyzer

A **full-stack Knowledge Graph-based RAG (Retrieval-Augmented Generation)** system that extracts, indexes, and queries information from PDF documents. Upload a PDF, ask questions in natural language, and receive cited answers powered by a hybrid vector + graph retrieval pipeline.

**Backend:** FastAPI · Neo4j · Milvus · LangChain  
**Frontend:** React 19 · TypeScript · Vite · Nginx

---

## Features

- 📄 **PDF Upload & OCR** — PyMuPDF direct extraction for text PDFs; multimodal LLM fallback for scanned pages
- 🔗 **Knowledge Graph Construction** — LLM extracts entity-relation triples and stores them in Neo4j
- 🔍 **Hybrid Graph RAG Retrieval** — Milvus vector search (Top-K) fused with Neo4j subgraph expansion
- 💬 **Streaming Chat** — SSE streaming responses with real-time token delivery
- 📚 **Citation Panel** — Every answer links back to the source text chunks with similarity scores
- 🔄 **Flexible AI Backend** — Set `API_KEY=ollama` for local [Ollama](https://ollama.com/) models, or any OpenAI-compatible API (OpenAI, GLM, vLLM, etc.)
- 🐳 **One-command Docker deployment** — All services orchestrated via Docker Compose

---

## Quick Start (Docker — Recommended)

### Prerequisites

| Requirement | Notes |
|---|---|
| Docker + Docker Compose | v2 plugin or standalone v1 |
| RAM | 8 GB+ recommended (Milvus requires it) |
| Disk | 10 GB+ free |
| Linux kernel setting | `vm.max_map_count ≥ 262144` (see below) |

**Linux — set `vm.max_map_count` (required by Milvus):**

```bash
# Temporary (until reboot)
sudo sysctl -w vm.max_map_count=262144

# Permanent
echo 'vm.max_map_count=262144' | sudo tee -a /etc/sysctl.conf
```

### 1. Configure environment

```bash
cp backend/.env.example backend/.env
# Edit backend/.env — set your LLM / Embedding / OCR API keys and model names
```

See [Environment Variables](#environment-variables) for all options.

### 2. Start all services

**Linux / macOS:**
```bash
chmod +x start.sh stop.sh
./start.sh
```

**Windows:**
```bat
start.bat
```

The script checks prerequisites, copies `.env` if missing, starts all containers, and polls the backend health endpoint. After startup:

| Service | URL |
|---|---|
| **Frontend UI** | http://localhost |
| **Backend API** | http://localhost:8000 |
| **API Docs (Swagger)** | http://localhost:8000/docs |
| **Neo4j Browser** | http://localhost:7474 |
| **MinIO Console** | http://localhost:9001 |

### 3. Stop services

```bash
./stop.sh                # stop containers
./stop.sh --volumes      # stop + delete all data volumes
./stop.sh --all          # stop + delete volumes + images
```

### 4. Rebuild after code changes

```bash
./start.sh --build
```

---

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and edit:

```ini
# ── OCR (multimodal LLM for scanned PDFs) ──
OCR_MODEL=glm-ocr
OCR_API_KEY=ollama          # "ollama" = local Ollama; otherwise remote key (e.g. "sk-xxx")
OCR_BASE_URL=http://localhost:11434/v1

# ── Embedding ──
EMBEDDING_MODEL=nomic-embed-text-v2-moe
EMBEDDING_API_KEY=ollama
EMBEDDING_BASE_URL=http://localhost:11434/v1

# ── LLM (chat + triple extraction) ──
LLM_MODEL=llama3.2
LLM_API_KEY=ollama
LLM_BASE_URL=http://localhost:11434/v1

# ── Neo4j ──
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=pdf-rag-analyzer

# ── Milvus ──
MILVUS_HOST=localhost
MILVUS_PORT=19530

# ── RAG Parameters (optional) ──
# CHUNK_SIZE=500
# CHUNK_OVERLAP=50
# TOP_K=5
# EMBEDDING_DIMENSION=768

# ── File Upload ──
# MAX_FILE_SIZE=52428800   # 50 MB
```

### AI Backend Selection

All three AI services (OCR, Embedding, LLM) independently support:

| `*_API_KEY` value | Backend used |
|---|---|
| `ollama` | Local [Ollama](https://ollama.com/) via `langchain_ollama` |
| Any other string | OpenAI-compatible API via `langchain_openai` |

**Docker + Ollama on host machine:** set `*_BASE_URL=http://host.docker.internal:11434/v1` — the `docker-compose.yml` already adds the `host-gateway` extra host entry.

**Example — OpenAI:**
```ini
LLM_MODEL=gpt-4o
LLM_API_KEY=sk-your-key
LLM_BASE_URL=https://api.openai.com/v1

EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_API_KEY=sk-your-key
EMBEDDING_BASE_URL=https://api.openai.com/v1

OCR_MODEL=gpt-4o
OCR_API_KEY=sk-your-key
OCR_BASE_URL=https://api.openai.com/v1
```

---

## Architecture

### Project Structure

```
pdf-rag-analyzer/
├── backend/                    # FastAPI application (Python 3.11)
│   ├── app/
│   │   ├── api/                # REST API routers
│   │   │   ├── health.py       #   GET  /health
│   │   │   ├── pdf.py          #   POST /v1/index/pdf, GET/DELETE /v1/index/pdfs
│   │   │   ├── chat.py         #   POST /v1/chat/completions, /stream; GET /v1/chat/citations/{id}
│   │   │   └── system.py       #   GET  /v1/system/stats
│   │   ├── core/
│   │   │   ├── config.py       #   Pydantic Settings (reads .env)
│   │   │   └── logger.py       #   Structured logging
│   │   ├── models/
│   │   │   ├── schemas.py      #   Pydantic request/response models
│   │   │   └── database.py     #   Neo4j + Milvus connection managers (singletons)
│   │   └── services/
│   │       ├── ocr_service.py          # PDF text extraction
│   │       ├── chunking_service.py     # LangChain RecursiveCharacterTextSplitter
│   │       ├── embedding_service.py    # LangChain Embeddings (Ollama / OpenAI)
│   │       ├── milvus_service.py       # Vector storage & similarity search
│   │       ├── llm_service.py          # LLM chat + triple extraction
│   │       ├── neo4j_service.py        # Knowledge graph CRUD
│   │       └── graph_rag_service.py    # Pipeline orchestration
│   ├── .env.example
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/                   # React 19 + TypeScript SPA
│   ├── src/
│   │   ├── App.tsx             #   Main UI (landing page + chat + citation panel)
│   │   ├── api/client.ts       #   Typed API client (fetch + SSE streaming)
│   │   ├── types/api.ts        #   TypeScript interfaces mirroring backend schemas
│   │   └── mocks/              #   MSW mock handlers (for offline development)
│   ├── nginx.conf              #   Nginx config (serves SPA + proxies /v1 and /health)
│   ├── Dockerfile              #   Multi-stage: Node build → Nginx serve
│   └── package.json
│
├── docker-compose.yml          # 6 services: frontend, backend, neo4j, milvus, etcd, minio
├── start.sh / start.bat        # Cross-platform start scripts
├── stop.sh  / stop.bat         # Cross-platform stop scripts
└── README.md
```

### PDF Indexing Pipeline

```
PDF Upload (≤ 50 MB)
       │
       ▼
┌──────────────────┐
│   OCR Service    │  PyMuPDF direct extraction (text PDFs, ≥ 50 chars/page)
│                  │  Multimodal LLM fallback at 200 DPI (scanned PDFs)
└────────┬─────────┘
         ▼
┌──────────────────┐
│ Chunking Service │  LangChain RecursiveCharacterTextSplitter
│                  │  chunk_size=500, overlap=50
│                  │  Separators: \n\n → \n → . → ! → ? → , → space
└────────┬─────────┘
         ▼
┌──────────────────┐
│Embedding Service │  LangChain Embeddings (dim=768, configurable)
│                  │  → Milvus collection "pdf_chunks"
│                  │    IVF_FLAT index, COSINE metric
└────────┬─────────┘
         ▼
┌──────────────────┐
│   LLM Service    │  Triple extraction per chunk (concurrency=5, temp=0.1)
│                  │  Prompt → JSON array of {head, relation, tail}
│                  │  → Neo4j: (Chunk)-[:CONTAINS]->(Entity)
│                  │           (Entity)-[:RELATES_TO {type}]->(Entity)
└──────────────────┘
```

### Graph RAG Query Pipeline

```
User Query
    │
    ▼  embed query
Milvus Top-K search  ──→  Top-K similar chunks (cosine similarity)
    │
    ▼  chunk_ids
Neo4j subgraph query ──→  Entities + 2-hop relations
    │
    ▼  fuse context
LLM generation       ──→  Answer with citations
    │
    ▼
SSE stream / JSON response
```

### Neo4j Graph Schema

```
(c:Chunk {chunk_id, file_id, filename, upload_time})
    -[:CONTAINS]->
(e:Entity {name})
    -[:RELATES_TO {type: "relation string"}]->
(e2:Entity {name})
```

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | System health — Neo4j + Milvus connectivity |
| `POST` | `/v1/index/pdf` | Upload PDF and build knowledge graph |
| `GET` | `/v1/index/pdfs` | List all uploaded PDFs with stats |
| `DELETE` | `/v1/index/pdfs` | Clear all data (Milvus + Neo4j) |
| `POST` | `/v1/chat/completions` | Graph RAG Q&A (JSON response) |
| `POST` | `/v1/chat/stream` | Graph RAG Q&A (SSE streaming) |
| `GET` | `/v1/chat/citations/{chat_id}` | Get citation text blocks for a chat |
| `GET` | `/v1/system/stats` | System statistics (chunks, nodes, edges, PDFs) |
| `GET` | `/docs` | Swagger UI interactive documentation |

### SSE Streaming Format

Each `data:` event carries a JSON `StreamChunk`:

```json
{"chat_id": "...", "delta": "token text", "finished": false}
{"chat_id": "...", "delta": "", "finished": true}
```

---

## Frontend

The React SPA has two views:

**Landing page** (no PDFs uploaded yet)  
Upload prompt with feature highlights. Transitions to the chat interface after the first PDF is processed.

**Chat interface**  
Three-panel layout:
- **Left sidebar** — Chat session history, PDF upload button, uploaded PDF list, "Clear All Data" button
- **Main area** — Message thread with streaming "Thinking…" indicator; citation toggle button per assistant message
- **Right panel** — Citation cards (similarity score + source text excerpt), slides in when citations are available

### Frontend Development

```bash
cd frontend
cp .env.example .env        # VITE_PORT=3000, VITE_API_BASE_URL=http://localhost:8000
npm install
npm run dev                 # Vite dev server on :3000, proxies /v1 and /health to backend
```

**MSW mock mode** (offline development without a running backend):  
Uncomment the MSW block in `frontend/src/main.tsx`:

```ts
if (import.meta.env.DEV) {
  const { worker } = await import('./mocks/browser')
  await worker.start({ onUnhandledRequest: 'bypass' })
}
```

Mock handlers in `frontend/src/mocks/handlers.ts` cover all API endpoints with realistic simulated responses.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 19, TypeScript 5, Vite 6, MSW 2 |
| **Frontend serving** | Nginx (Alpine), gzip, SPA routing, SSE proxy |
| **Backend framework** | FastAPI 0.115 + Uvicorn, Python 3.11 |
| **Graph database** | Neo4j 5 Community + APOC |
| **Vector database** | Milvus 2.5 Standalone (etcd + MinIO) |
| **LLM / Embedding** | LangChain (ChatOpenAI / ChatOllama / OpenAIEmbeddings / OllamaEmbeddings) |
| **Text splitting** | LangChain `RecursiveCharacterTextSplitter` |
| **PDF processing** | PyMuPDF 1.25 (direct) + multimodal LLM (OCR fallback) |
| **Data validation** | Pydantic v2 + pydantic-settings |
| **Containerization** | Docker Compose v2 |

---

## Docker Services

| Container | Image | Ports |
|---|---|---|
| `pdf-rag-frontend` | `node:20-alpine` → `nginx:alpine` | `80` |
| `pdf-rag-backend` | `python:3.11-slim` | `8000` |
| `pdf-rag-neo4j` | `neo4j:5-community` | `7474`, `7687` |
| `pdf-rag-milvus` | `milvusdb/milvus:v2.5.0` | `19530`, `9091` |
| `pdf-rag-etcd` | `quay.io/coreos/etcd:v3.5.18` | — |
| `pdf-rag-minio` | `minio/minio:latest` | `9000`, `9001` |

Persistent data is stored in named Docker volumes: `neo4j_data`, `neo4j_logs`, `etcd_data`, `minio_data`, `milvus_data`.

---

## Backend-only Development

```bash
# Start only the infrastructure (Neo4j + Milvus stack)
docker compose up -d neo4j milvus milvus-etcd milvus-minio

# Install Python dependencies
cd backend
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — set NEO4J_URI=bolt://localhost:7687, MILVUS_HOST=localhost

# Run the backend
python -m app.main
# or: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

API docs available at `http://localhost:8000/docs`.

---

## Troubleshooting

**Milvus fails to start**  
Check `vm.max_map_count`:
```bash
cat /proc/sys/vm/max_map_count   # must be ≥ 262144
sudo sysctl -w vm.max_map_count=262144
```

**Backend health shows `degraded`**  
Neo4j or Milvus is not yet ready. Wait ~30 s after `docker compose up` and refresh `/health`. Check logs:
```bash
docker compose logs neo4j
docker compose logs milvus
```

**PDF upload returns 503**  
The LLM/Embedding service is unreachable. Verify `*_API_KEY` and `*_BASE_URL` in `backend/.env`, then restart:
```bash
docker compose restart backend
```

**View all logs**
```bash
docker compose logs -f
docker compose logs -f backend   # backend only
```

**Full reset (delete all data)**
```bash
./stop.sh --volumes
./start.sh --build