# IM|Copilot — AI-Powered Academic Assistant

> Final Year Project (FYP-1) · Institute of Management Sciences, Peshawar
> A hybrid agentic AI assistant combining RAG + Text-to-SQL for academic advising.

---

## Architecture

```
User Query
    │
Intent Router (keyword + LLM classifier)
    │              │               │
ACADEMIC       POLICY           HYBRID
    │              │               │
SQL Agent      RAG Agent       Both Agents
(Text-to-SQL)  (ChromaDB RAG)
    │              │               │
SQLite DB     Handbook Chunks  Combined Answer
    │              │               │
         Natural Language Response
```

## Tech Stack

| Layer            | Technology                              |
|------------------|-----------------------------------------|
| Backend          | FastAPI + Python 3.10+                  |
| LLM (primary)    | Groq API — Llama-3.1-8b-instant         |
| LLM (fallback)   | Google Gemini 1.5 Flash                 |
| Vector DB        | ChromaDB (persistent, local)            |
| Embeddings       | SentenceTransformers (all-MiniLM-L6-v2) |
| Relational DB    | SQLite                                  |
| Frontend         | React 18 + Vite + Tailwind CSS          |
| Charts           | Recharts                                |
| Icons            | Lucide React                            |

---

## Project Structure

```
imcopilot/
├── backend/
│   ├── main.py           # FastAPI app + all endpoints
│   ├── database.py       # SQLite schema + dummy data + safe query executor
│   ├── vector_store.py   # ChromaDB ingestion + RAG retrieval
│   ├── agent.py          # Intent Router + SQL Agent + RAG Agent
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── App.jsx       # Complete React UI (Dashboard + Chat)
    │   └── main.jsx
    ├── index.html
    ├── package.json
    └── vite.config.js
```

---

## Quick Start

### 1. Clone & configure environment

```bash
cd imcopilot/backend
cp .env.example .env
# Edit .env and add your API keys:
#   GROQ_API_KEY=...     (get free key at console.groq.com)
#   GEMINI_API_KEY=...   (get free key at aistudio.google.com)
```

### 2. Start the Backend

```bash
cd imcopilot/backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

On first run, the backend will:
- Create `imcopilot.db` (SQLite) with 10 demo students + grades/attendance
- Create `chroma_db/` and embed the IMSciences handbook into ChromaDB

### 3. Start the Frontend

```bash
cd imcopilot/frontend
npm install
npm run dev
# Opens at http://localhost:5173
```

### 4. Open the App

Visit **http://localhost:5173**, select any demo student, and start exploring.

---

## API Endpoints

| Method | Endpoint                      | Description                              |
|--------|-------------------------------|------------------------------------------|
| GET    | `/`                           | Health check                             |
| GET    | `/dashboard/{student_id}`     | Full dashboard (grades, attendance, GPA) |
| POST   | `/chat`                       | AI chat (Intent Router entry point)      |
| GET    | `/students`                   | List all demo students                   |
| GET    | `/vector-store/stats`         | ChromaDB stats                           |
| POST   | `/vector-store/reingest`      | Refresh handbook embeddings              |
| GET    | `/intent-test?q=...`          | Dev: test intent classification          |

Interactive API docs: **http://localhost:8000/docs**

---

## Demo Students

| ID   | Name           | Program | CGPA |
|------|----------------|---------|------|
| S001 | Ali Hassan     | BCS     | ~3.x |
| S002 | Fatima Malik   | BBA     | ~3.x |
| S003 | Ahmed Khan     | MBA     | ~3.x |
| S005 | Bilal Afridi   | BBA     | low att. (test XF) |
| S009 | Hamza Yousaf   | BCS     | low att. (test XF) |

---

## Key Methodologies (Thesis Reference)

### Context Engineering (Zero-Shot SQL)
The SQL Agent does **not** use few-shot examples at runtime. Instead, the full
database schema is injected into the system prompt on every request. The LLM
generates valid SQLite SELECT queries purely from schema + natural language.

### RAG Pipeline
1. Handbook chunked with sliding window (600 chars, 120 overlap)
2. Embedded via `all-MiniLM-L6-v2` into ChromaDB
3. Query embedded at runtime → cosine similarity retrieval (top-4 chunks)
4. Chunks injected into LLM system prompt with source citation instructions

### Intent Router
Two-stage classification:
- **Stage 1**: Keyword matching (O(1), zero LLM cost) for obvious queries
- **Stage 2**: LLM classification only for ambiguous queries

### Safety & Governance
- SQL execution: keyword-level block of INSERT/UPDATE/DELETE/DROP
- Policy answers: LLM instructed to cite only from retrieved handbook chunks
- Hallucination guard: explicit instruction to say "I don't know" if context insufficient

---

## Environment Variables

```env
GROQ_API_KEY=gsk_...       # Required (or GEMINI_API_KEY)
GEMINI_API_KEY=AIza...     # Optional fallback
```
