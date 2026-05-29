// ────────────────── Health Check ──────────────────

export interface HealthResponse {
  status: string
  timestamp: string
  neo4j_connected: boolean
  milvus_connected: boolean
  version: string
}

// ────────────────── PDF Upload ──────────────────

export interface PDFUploadResponse {
  file_id: string
  filename: string
  total_chunks: number
  total_entities: number
  total_relations: number
  message: string
}

// ────────────────── Chat ──────────────────

export interface ChatRequest {
  query: string
  top_k?: number | null
  chat_id?: string | null
}

export interface ChatMessage {
  role: string
  content: string
}

export interface ChatResponse {
  chat_id: string
  query: string
  answer: string
  citations: CitationItemData[]
  created_at: string
}

export interface StreamChunk {
  chat_id: string
  delta: string
  finished: boolean
}

// ────────────────── Citations ──────────────────

export interface CitationItemData {
  chunk_id: string
  score: number
  content: string
  source_file?: string | null
}

export interface CitationsResponse {
  chat_id: string
  citations: CitationItemData[]
}

// ────────────────── System Statistics ──────────────────

export interface SystemStats {
  total_chunks: number
  total_nodes: number
  total_edges: number
  total_pdfs: number
}

// ────────────────── PDF List ──────────────────

export interface PDFListItem {
  file_id: string
  filename: string
  upload_time: string
  total_chunks: number
  total_entities: number
  total_relations: number
}

export interface PDFListResponse {
  pdfs: PDFListItem[]
  total: number
}

// ────────────────── Delete Operation ──────────────────

export interface DeleteAllResponse {
  message: string
}

// ────────────────── Internal Data Structures ──────────────────

export interface ChunkData {
  chunk_id: string
  content: string
  file_id: string
  index: number
}

export interface TripleData {
  head: string
  relation: string
  tail: string
}

export interface GraphContext {
  chunk_contents: string[]
  entities: string[]
  relations: string[]
}