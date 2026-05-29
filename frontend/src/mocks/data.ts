import type {
  HealthResponse,
  PDFListItem,
  SystemStats,
} from '@/types/api'

/** Mock PDF files data — starts empty so landing page shows first */
export const mockPDFs: PDFListItem[] = []

/** Mock health check response */
export const mockHealth: HealthResponse = {
  status: 'ok',
  timestamp: new Date().toISOString(),
  neo4j_connected: true,
  milvus_connected: true,
  version: '1.0.0',
}

/** Mock system stats */
export const mockSystemStats: SystemStats = {
  total_chunks: 0,
  total_nodes: 0,
  total_edges: 0,
  total_pdfs: 0,
}

/** Mock stream chat responses for different queries */
export const mockChatStreamResponses: Record<string, string[]> = {
  default: [
    'Based',
    ' on',
    ' the',
    ' knowledge',
    ' graph',
    ',',
    ' the',
    ' attention',
    ' mechanism',
    ' allows',
    ' the',
    ' model',
    ' to',
    ' focus',
    ' on',
    ' different',
    ' parts',
    ' of',
    ' the',
    ' input',
    ' sequence',
    '.',
  ],
  transformer: [
    'The',
    ' Transformer',
    ' architecture',
    ' uses',
    ' self-attention',
    ' mechanisms',
    ' instead',
    ' of',
    ' recurrence',
    ',\n\n',
    'enabling',
    ' parallel',
    ' computation',
    ' and',
    ' better',
    ' handling',
    ' of',
    ' long-range',
    ' dependencies',
    '.',
  ],
  attention: [
    'Attention',
    ' is',
    ' a',
    ' mechanism',
    ' that',
    ' computes',
    ' a',
    ' weighted',
    ' sum',
    ' of',
    ' values',
    ',\n\n',
    'where',
    ' weights',
    ' are',
    ' derived',
    ' from',
    ' the',
    ' compatibility',
    ' of',
    ' queries',
    ' and',
    ' keys',
    '.',
  ],
}

/** Pick stream response tokens based on query keywords */
export function getStreamResponseForQuery(query: string): string[] {
  const lower = query.toLowerCase()
  if (lower.includes('transformer')) return mockChatStreamResponses.transformer
  if (lower.includes('attention')) return mockChatStreamResponses.attention
  return mockChatStreamResponses.default
}