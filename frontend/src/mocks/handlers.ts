import { http, HttpResponse, delay } from 'msw'
import {
  mockPDFs,
  mockHealth,
  mockSystemStats,
  getStreamResponseForQuery,
} from './data'
import type { ChatRequest, PDFUploadResponse } from '@/types/api'

// ── Helpers ──

let pdfIdCounter = 3
const storedPDFs = [...mockPDFs]

// ── Handlers ──

export const handlers = [
  // ──── GET /health ────
  http.get('/health', async () => {
    await delay(200)
    return HttpResponse.json({
      ...mockHealth,
      timestamp: new Date().toISOString(),
    })
  }),

  // ──── GET /v1/index/pdfs ────
  http.get('/v1/index/pdfs', async () => {
    await delay(300)
    return HttpResponse.json({
      pdfs: storedPDFs,
      total: storedPDFs.length,
    })
  }),

  // ──── DELETE /v1/index/pdfs ────
  http.delete('/v1/index/pdfs', async () => {
    await delay(500)
    storedPDFs.length = 0
    return HttpResponse.json({
      message: 'All PDFs and related data have been cleared successfully',
    })
  }),

  // ──── POST /v1/index/pdf ────
  http.post('/v1/index/pdf', async ({ request }) => {
    await delay(1500)
    const formData = await request.formData()
    const file = formData.get('file') as File | null
    const filename = file?.name || 'unknown.pdf'

    pdfIdCounter++
    const newPDF = {
      file_id: `pdf-${String(pdfIdCounter).padStart(3, '0')}`,
      filename,
      upload_time: new Date().toISOString(),
      total_chunks: Math.floor(Math.random() * 40) + 10,
      total_entities: Math.floor(Math.random() * 200) + 50,
      total_relations: Math.floor(Math.random() * 400) + 100,
    }
    storedPDFs.push(newPDF)

    const response: PDFUploadResponse = {
      file_id: newPDF.file_id,
      filename: newPDF.filename,
      total_chunks: newPDF.total_chunks,
      total_entities: newPDF.total_entities,
      total_relations: newPDF.total_relations,
      message: 'PDF processed successfully',
    }

    return HttpResponse.json(response)
  }),

  // ──── POST /v1/chat/completions ────
  http.post('/v1/chat/completions', async ({ request }) => {
    await delay(800)
    const body = (await request.json()) as ChatRequest
    const query = body.query

    const answer = getStreamResponseForQuery(query).join('')

    return HttpResponse.json({
      chat_id: `chat-${Date.now()}`,
      query,
      answer,
      citations: [
        {
          chunk_id: 'chunk-001',
          score: 0.95,
          content:
            'The attention mechanism allows the model to focus on different parts of the input sequence, capturing dependencies regardless of distance.',
          source_file: 'attention_is_all_you_need.pdf',
        },
        {
          chunk_id: 'chunk-002',
          score: 0.88,
          content:
            'Self-attention layers enable parallel computation and better handling of long-range dependencies compared to recurrent neural networks.',
          source_file: 'transformer_architecture_overview.pdf',
        },
      ],
      created_at: new Date().toISOString(),
    })
  }),

  // ──── POST /v1/chat/stream (SSE) ────
  http.post('/v1/chat/stream', async ({ request }) => {
    const body = (await request.json()) as ChatRequest
    const query = body.query
    const tokens = getStreamResponseForQuery(query)
    const chatId = `chat-${Date.now()}`

    const encoder = new TextEncoder()
    const stream = new ReadableStream({
      async start(controller) {
        for (let i = 0; i < tokens.length; i++) {
          await delay(80)
          const chunk = {
            chat_id: chatId,
            delta: tokens[i],
            finished: false,
          }
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(chunk)}\n\n`))
        }
        // Final chunk
        const finalChunk = {
          chat_id: chatId,
          delta: '',
          finished: true,
        }
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(finalChunk)}\n\n`))
        controller.close()
      },
    })

    return new HttpResponse(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
      },
    })
  }),

  // ──── GET /v1/chat/citations/:chatId ────
  http.get('/v1/chat/citations/:chatId', async ({ params }) => {
    await delay(200)
    const { chatId } = params
    return HttpResponse.json({
      chat_id: chatId,
      citations: [
        {
          chunk_id: 'chunk-001',
          score: 0.95,
          content:
            'The attention mechanism allows the model to focus on different parts of the input sequence.',
          source_file: 'attention_is_all_you_need.pdf',
        },
        {
          chunk_id: 'chunk-004',
          score: 0.91,
          content:
            'Multi-head attention runs multiple attention functions in parallel to capture different representation subspaces.',
          source_file: 'attention_is_all_you_need.pdf',
        },
      ],
    })
  }),

  // ──── GET /v1/system/stats ────
  http.get('/v1/system/stats', async () => {
    await delay(300)
    return HttpResponse.json(mockSystemStats)
  }),
]