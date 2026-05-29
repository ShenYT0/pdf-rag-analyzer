/**
 * API client for communicating with the backend.
 * When MSW is active in dev mode, all requests are intercepted by the Service Worker.
 * When MSW is disabled or in production, requests go directly to the backend server.
 */
import type {
  HealthResponse,
  PDFListResponse,
  PDFUploadResponse,
  DeleteAllResponse,
  ChatRequest,
  ChatResponse,
  CitationsResponse,
  SystemStats,
} from '@/types/api'

const BASE_URL = ''

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
    },
    ...options,
  })

  if (!res.ok) {
    const errorBody = await res.text()
    throw new Error(`API error ${res.status}: ${errorBody}`)
  }

  return res.json()
}

// ──── Health ────

export async function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health')
}

// ──── PDF Indexing ────

export async function listPDFs(): Promise<PDFListResponse> {
  return request<PDFListResponse>('/v1/index/pdfs')
}

export async function deleteAllPDFs(): Promise<DeleteAllResponse> {
  return request<DeleteAllResponse>('/v1/index/pdfs', { method: 'DELETE' })
}

export async function uploadPDF(file: File): Promise<PDFUploadResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const res = await fetch(`${BASE_URL}/v1/index/pdf`, {
    method: 'POST',
    body: formData,
  })

  if (!res.ok) {
    const errorBody = await res.text()
    throw new Error(`Upload error ${res.status}: ${errorBody}`)
  }

  return res.json()
}

// ──── Chat ────

export async function chatCompletion(request: ChatRequest): Promise<ChatResponse> {
  return request<ChatResponse>('/v1/chat/completions', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export function chatStream(
  request: ChatRequest,
  onChunk: (delta: string) => void,
  onDone: () => void,
  onError: (error: Error) => void,
  onChatId?: (chatId: string) => void,
): AbortController {
  const controller = new AbortController()

  fetch(`${BASE_URL}/v1/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`Stream error ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response body reader available')
      }

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const jsonStr = line.slice(6)
            try {
              const chunk = JSON.parse(jsonStr)
              // Forward the chat_id from the first chunk to the caller
              if (chunk.chat_id && onChatId) {
                onChatId(chunk.chat_id)
              }
              if (chunk.finished) {
                onDone()
              } else if (chunk.delta) {
                onChunk(chunk.delta)
              }
            } catch {
              // Skip malformed chunks
            }
          }
        }
      }

      // Process remaining buffer
      if (buffer.startsWith('data: ')) {
        try {
          const chunk = JSON.parse(buffer.slice(6))
          if (!chunk.finished && chunk.delta) {
            onChunk(chunk.delta)
          }
        } catch {
          // Skip malformed
        }
      }

      onDone()
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        onError(err instanceof Error ? err : new Error(String(err)))
      }
    })

  return controller
}

// ──── Citations ────

export async function getCitations(chatId: string): Promise<CitationsResponse> {
  return request<CitationsResponse>(`/v1/chat/citations/${chatId}`)
}

// ──── System ────

export async function getSystemStats(): Promise<SystemStats> {
  return request<SystemStats>('/v1/system/stats')
}