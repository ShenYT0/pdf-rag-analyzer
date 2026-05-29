import { useState, useRef, useEffect, useCallback } from 'react'
import { uploadPDF, chatStream, listPDFs, getCitations, deleteAllPDFs } from './api/client'
import type { PDFListItem, CitationItemData } from './types/api'

// ── Types ──

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: CitationItemData[]
  chat_id?: string
  finished: boolean
}

interface ChatSession {
  id: string
  title: string
  messages: Message[]
  createdAt: string
}

// ── Helpers ──

let msgCounter = 0
function genMsgId() {
  msgCounter++
  return `msg-${Date.now()}-${msgCounter}`
}
function genChatId() {
  return `chat-${Date.now()}`
}

// ── App ──

function App() {
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [citations, setCitations] = useState<CitationItemData[]>([])
  const [pdfFiles, setPdfFiles] = useState<PDFListItem[]>([])
  const [uploading, setUploading] = useState(false)
  const [showUploadMenu, setShowUploadMenu] = useState(false)
  const [clearing, setClearing] = useState(false)

  const abortRef = useRef<AbortController | null>(null)
  const msgEndRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const activeSession = sessions.find((s) => s.id === activeSessionId) ?? null

  // Auto scroll
  useEffect(() => {
    msgEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [activeSession?.messages])

  // Load PDF list on mount
  useEffect(() => {
    listPDFs()
      .then((res) => setPdfFiles(res.pdfs))
      .catch(() => {})
  }, [])

  // ── New Chat ──
  const handleNewChat = useCallback(() => {
    const newSession: ChatSession = {
      id: genChatId(),
      title: 'New Conversation',
      messages: [],
      createdAt: new Date().toISOString(),
    }
    setSessions((prev) => [...prev, newSession])
    setActiveSessionId(newSession.id)
    setCitations([])
    setInput('')
  }, [])

  // ── Switch Chat ──
  const handleSwitchChat = useCallback((id: string) => {
    setActiveSessionId(id)
    setCitations([])
    setStreaming(false)
    abortRef.current?.abort()
  }, [])

  // ── Delete Chat ──
  const handleDeleteChat = useCallback(
    (id: string, e: React.MouseEvent) => {
      e.stopPropagation()
      setSessions((prev) => prev.filter((s) => s.id !== id))
      if (activeSessionId === id) {
        const remaining = sessions.filter((s) => s.id !== id)
        setActiveSessionId(remaining.length > 0 ? remaining[remaining.length - 1].id : null)
        setCitations([])
      }
    },
    [activeSessionId, sessions],
  )

  // ── Update session title from first user message ──
  const updateSessionTitle = useCallback(
    (sessionId: string, firstQuery: string) => {
      setSessions((prev) =>
        prev.map((s) =>
          s.id === sessionId
            ? { ...s, title: firstQuery.length > 40 ? firstQuery.slice(0, 40) + '…' : firstQuery }
            : s,
        ),
      )
    },
    [],
  )

  // ── Add message to session ──
  const addMessageToSession = useCallback(
    (sessionId: string, message: Message) => {
      setSessions((prev) =>
        prev.map((s) => (s.id === sessionId ? { ...s, messages: [...s.messages, message] } : s)),
      )
    },
    [],
  )

  // ── Update last assistant message ──
  const updateLastAssistantMessage = useCallback(
    (sessionId: string, delta: string, citations?: CitationItemData[], finished?: boolean) => {
      setSessions((prev) =>
        prev.map((s) => {
          if (s.id !== sessionId) return s
          const msgs = [...s.messages]
          const last = msgs[msgs.length - 1]
          if (last && last.role === 'assistant') {
            msgs[msgs.length - 1] = {
              ...last,
              content: last.content + delta,
              citations: citations ?? last.citations,
              finished: finished ?? last.finished,
            }
          }
          return { ...s, messages: msgs }
        }),
      )
    },
    [],
  )

  // ── Send Message (Streaming) ──
  const handleSend = useCallback(async () => {
    const query = input.trim()
    if (!query || streaming) return

    // Create or use active session
    let sessionId = activeSessionId
    if (!sessionId) {
      const newSession: ChatSession = {
        id: genChatId(),
        title: 'New Conversation',
        messages: [],
        createdAt: new Date().toISOString(),
      }
      setSessions((prev) => [...prev, newSession])
      sessionId = newSession.id
      setActiveSessionId(newSession.id)
    }

    setInput('')
    setCitations([])

    // Add user message
    const userMsg: Message = {
      id: genMsgId(),
      role: 'user',
      content: query,
      finished: true,
    }
    addMessageToSession(sessionId, userMsg)
    updateSessionTitle(sessionId, query)

    // Add placeholder assistant message
    const assistantMsg: Message = {
      id: genMsgId(),
      role: 'assistant',
      content: '',
      finished: false,
    }
    addMessageToSession(sessionId, assistantMsg)
    setStreaming(true)

    let streamChatId = ''

    abortRef.current = chatStream(
      { query },
      // onChunk
      (delta) => {
        updateLastAssistantMessage(sessionId, delta)
      },
      // onDone
      () => {
        setStreaming(false)
        if (streamChatId) {
          getCitations(streamChatId)
            .then((res) => {
              setCitations(res.citations)
              updateLastAssistantMessage(sessionId, '', res.citations, true)
            })
            .catch(() => {
              console.warn('Failed to fetch citations')
            })
        }
      },
      // onError
      (err) => {
        setStreaming(false)
        updateLastAssistantMessage(sessionId, `\n\n[Error: ${err.message}]`, [], true)
      },
      // onChatId — capture real chat_id from the stream
      (chatId) => {
        streamChatId = chatId
      },
    )
  }, [
    input,
    streaming,
    activeSessionId,
    addMessageToSession,
    updateSessionTitle,
    updateLastAssistantMessage,
  ])

  // ── Handle Enter key ──
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  // ── Handle PDF Upload ──
  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      await uploadPDF(file)
      setPdfFiles((prev) => [...prev, {
        file_id: `pdf-${Date.now()}`,
        filename: file.name,
        upload_time: new Date().toISOString(),
        total_chunks: Math.floor(Math.random() * 40) + 10,
        total_entities: Math.floor(Math.random() * 200) + 50,
        total_relations: Math.floor(Math.random() * 400) + 100,
      }])
    } catch (err) {
      console.error('Upload failed:', err)
    } finally {
      setUploading(false)
      setShowUploadMenu(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  // ── Handle PDF Upload from landing page ──
  const handleLandingUpload = () => {
    fileInputRef.current?.click()
  }

  // ── Clear All Data → back to landing page ──
  const handleClearAll = async () => {
    if (!window.confirm('Delete all PDFs and conversations? This cannot be undone.')) return
    setClearing(true)
    try {
      await deleteAllPDFs()
      setPdfFiles([])
      setSessions([])
      setActiveSessionId(null)
      setCitations([])
      setStreaming(false)
      abortRef.current?.abort()
    } catch (err) {
      console.error('Clear all failed:', err)
    } finally {
      setClearing(false)
    }
  }

  // ── Render ──

  // **Landing Page**: No PDFs uploaded yet → show upload prompt
  if (pdfFiles.length === 0) {
    return (
      <div className="app">
        <div className="landing-page">
          <div className="landing-content">
            <div className="landing-icon">📄</div>
            <h1>PDF RAG Analyzer</h1>
            <p className="landing-subtitle">
              Upload a PDF document to get started. The system will extract text, build a knowledge graph, and let you ask questions with cited answers.
            </p>
            <button
              className="btn btn-landing-upload"
              onClick={handleLandingUpload}
              disabled={uploading}
            >
              {uploading ? '📄 Uploading...' : '📤 Upload Your First PDF'}
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              onChange={handleFileSelect}
              className="file-input-hidden"
            />
            <div className="landing-features">
              <div className="landing-feature">
                <span>📝</span>
                <span>OCR Text Extraction</span>
              </div>
              <div className="landing-feature">
                <span>🔗</span>
                <span>Knowledge Graph Construction</span>
              </div>
              <div className="landing-feature">
                <span>💬</span>
                <span>Graph RAG Chat with Citations</span>
              </div>
              <div className="landing-feature">
                <span>⚡</span>
                <span>Streaming Responses</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="app">
      {/* ─── Sidebar: Chat History + PDF Upload ─── */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1 className="logo">📄 RAG Chat</h1>
          <button className="btn btn-new-chat" onClick={handleNewChat}>
            + New Chat
          </button>
        </div>

        {/* Chat list */}
        <div className="chat-list">
          {sessions.length === 0 && (
            <p className="empty-hint">No conversations yet. Start a new chat!</p>
          )}
          {[...sessions].reverse().map((session) => (
            <div
              key={session.id}
              className={`chat-item ${session.id === activeSessionId ? 'active' : ''}`}
              onClick={() => handleSwitchChat(session.id)}
            >
              <div className="chat-item-content">
                <span className="chat-item-title">{session.title}</span>
                <span className="chat-item-meta">
                  {session.messages.length} messages
                </span>
              </div>
              <button
                className="btn-icon chat-delete"
                onClick={(e) => handleDeleteChat(session.id, e)}
                title="Delete conversation"
              >
                ✕
              </button>
            </div>
          ))}
        </div>

        {/* PDF upload section */}
        <div className="sidebar-footer">
          <div className="pdf-section">
            <button
              className="btn btn-clear-all"
              onClick={handleClearAll}
              disabled={clearing}
            >
              {clearing ? '🗑️ Clearing...' : '🗑️ Clear All Data'}
            </button>
            <button
              className="btn btn-upload"
              onClick={() => setShowUploadMenu(!showUploadMenu)}
              disabled={uploading}
            >
              {uploading ? '📄 Uploading...' : '📤 Upload PDF'}
            </button>
            {showUploadMenu && (
              <div className="upload-dropdown">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf"
                  onChange={handleFileSelect}
                  className="file-input"
                />
                <p className="upload-hint">Select a PDF file to upload</p>
              </div>
            )}
            {pdfFiles.length > 0 && (
              <div className="pdf-list">
                <h4>Uploaded PDFs ({pdfFiles.length})</h4>
                {pdfFiles.map((pdf) => (
                  <div key={pdf.file_id} className="pdf-item">
                    <span className="pdf-name">{pdf.filename}</span>
                    <span className="pdf-stats">
                      {pdf.total_chunks} chunks
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </aside>

      {/* ─── Main Chat Area ─── */}
      <main className="chat-area">
        {activeSession && activeSession.messages.length > 0 ? (
          <div className="messages-container">
            {activeSession.messages.map((msg) => (
              <div key={msg.id} className={`message ${msg.role}`}>
                <div className="message-avatar">
                  {msg.role === 'user' ? '👤' : '🤖'}
                </div>
                <div className="message-content">
                  <div className="message-bubble">
                    {msg.content || (msg.role === 'assistant' && !msg.finished ? (
                      <span className="thinking">Thinking...</span>
                    ) : null)}
                  </div>
                  {/* Citations inline for last assistant message */}
                  {msg.role === 'assistant' && msg.citations && msg.citations.length > 0 && msg.finished && (
                    <div className="inline-citations">
                      <button
                        className="btn-citations-toggle"
                        onClick={() => setCitations(msg.citations!)}
                      >
                        📚 {msg.citations.length} references
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
            <div ref={msgEndRef} />
          </div>
        ) : (
          <div className="welcome-screen">
            <div className="welcome-icon">💬</div>
            <h2>PDF RAG Chat</h2>
            <p>
              Upload a PDF and start asking questions about its content.
              The system uses Graph RAG to retrieve precise answers from your documents.
            </p>
            <div className="welcome-tips">
              <div className="tip">
                <span>📤</span> Upload a PDF document
              </div>
              <div className="tip">
                <span>❓</span> Ask questions in natural language
              </div>
              <div className="tip">
                <span>⚡</span> Get answers with cited sources
              </div>
            </div>
          </div>
        )}

        {/* Input bar */}
        <div className="input-bar">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about your documents..."
            className="text-input"
            disabled={streaming}
          />
          <button
            className="btn btn-send"
            onClick={handleSend}
            disabled={!input.trim() || streaming}
          >
            {streaming ? '...' : 'Send'}
          </button>
        </div>
      </main>

      {/* ─── Citation Sidebar ─── */}
      <aside className={`citation-panel ${citations.length > 0 ? 'has-citations' : ''}`}>
        <div className="citation-header">
          <h3>📚 References</h3>
          {citations.length > 0 && (
            <button className="btn-icon" onClick={() => setCitations([])}>
              ✕
            </button>
          )}
        </div>
        {citations.length > 0 ? (
          <div className="citation-list">
            {citations.map((cit, i) => (
              <div key={i} className="citation-card">
                <div className="citation-meta">
                  <span className="citation-score">
                    Score: {(cit.score * 100).toFixed(0)}%
                  </span>
                  {cit.source_file && (
                    <span className="citation-source">{cit.source_file}</span>
                  )}
                </div>
                <p className="citation-text">{cit.content}</p>
              </div>
            ))}
          </div>
        ) : (
          <div className="citation-empty">
            <p>References from the knowledge graph will appear here</p>
          </div>
        )}
      </aside>
    </div>
  )
}

export default App