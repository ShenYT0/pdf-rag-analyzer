# PDF RAG Analyzer - Frontend

A Graph RAG chat application for PDF document analysis. Built with React, TypeScript, Vite, and MSW (Mock Service Worker).

## Quick Start

### Requirements

- Node.js >= 18

### Install Dependencies

```bash
cd frontend
npm install
```

---

## 🧪 Test Mode (No Backend Needed)

This mode uses **MSW (Mock Service Worker)** to intercept all API requests in the browser — no backend required.

```bash
cd frontend
npm run dev
```

Open **http://localhost:5173/** in your browser.

### What's Mocked

| Endpoint | Mock Behavior |
|----------|---------------|
| `GET /health` | Returns `{"status": "ok", ...}` |
| `POST /v1/index/pdf` | Simulates upload with random stats |
| `GET /v1/index/pdfs` | Returns list of uploaded PDFs |
| `DELETE /v1/index/pdfs` | Clears all data |
| `POST /v1/chat/completions` | Returns mock JSON answer |
| `POST /v1/chat/stream` | SSE stream of tokens (80ms intervals) |
| `GET /v1/chat/citations/:id` | Returns mock citation blocks |
| `GET /v1/system/stats` | Returns mock system statistics |

### Test Flow

1. Open the app → **Landing Page** with "Upload Your First PDF" button
2. Select any `.pdf` file → uploads instantly (mocked) → transitions to chat interface
3. Type a question (e.g. "What is transformer?") → see streaming response
4. After response completes → **Citation sidebar** slides in from the right
5. Click "+ New Chat" to start another conversation
6. Click "🗑️ Clear All Data" to reset everything → back to landing page

---

## 🚀 Production Mode (With Backend)

Point the frontend to the running FastAPI backend.

### Step 1: Start the Backend

```bash
# From the project root, start all services
docker compose up -d

# Or start the Python backend directly
cd backend
python -m app.main
```

### Step 2: Disable MSW Mock

Edit `src/main.tsx`:

```typescript
// Comment out MSW initialization
// if (import.meta.env.DEV) {
//   const { worker } = await import('./mocks/browser')
//   await worker.start({ onUnhandledRequest: 'bypass' })
// }
```

### Step 3: Start the Frontend

```bash
cd frontend
npm run dev
```

Vite's proxy (`vite.config.ts`) automatically forwards `/v1/*` and `/health` requests to **http://localhost:8000**.

### Build for Production

```bash
cd frontend
npm run build
```

Output is in `dist/`. Serve with any static file server (or via the FastAPI backend's static file mount).

---

## Project Structure

```
frontend/
├── public/
│   └── mockServiceWorker.js    # MSW Service Worker
├── src/
│   ├── api/
│   │   └── client.ts           # API client (fetch wrapper)
│   ├── mocks/
│   │   ├── browser.ts          # MSW worker setup
│   │   ├── data.ts             # Mock data definitions
│   │   └── handlers.ts         # MSW request handlers
│   ├── types/
│   │   └── api.ts              # TypeScript interfaces matching backend schemas
│   ├── App.tsx                 # Main chat application
│   ├── index.css               # Styles
│   └── main.tsx                # Entry point
├── index.html
├── package.json
├── tsconfig.json
└── vite.config.ts              # Vite config with proxy
```

## Tech Stack

- **React 19** + **TypeScript** — UI framework
- **Vite** — Build tool & dev server
- **MSW** — Mock Service Worker for API mocking
- **CSS Variables** — Dark theme with custom properties