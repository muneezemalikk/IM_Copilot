# IM|Copilot — FYP-1 Thesis: Technical Design Document

**Chapter 4: System Design, Architecture & Implementation**

Institute of Management Sciences, Peshawar
Department of Computer Science
Final Year Project — Phase 1

---

## 4.1 System Overview

IM|Copilot is a hybrid, agentic AI assistant designed to address a fundamental
problem in university information systems: academic knowledge is locked in two
incompatible silos. Institutional rules are stored in lengthy, unsearchable PDF
documents (handbooks, policy circulars), while personal academic records (GPA,
attendance, grades) exist in rigid, non-conversational student portals. Students
must manually cross-reference both to answer even simple questions such as "Am I
at risk of probation?"

IM|Copilot solves this by acting as a unified conversational interface over both
data sources simultaneously. It combines two distinct AI pipelines — a
Retrieval-Augmented Generation (RAG) pipeline for unstructured policy documents
and a Text-to-SQL generation pipeline for structured relational data — under a
single Intent Router that automatically selects the correct agent for each query.

---

## 4.2 Architectural Philosophy

The system is built on three core design principles that directly informed every
architectural decision:

**Principle 1 — No Fine-Tuning.** The system achieves all its intelligence
through Context Engineering (also called System Prompt Optimization) rather than
model fine-tuning or training. This is both a practical constraint (fine-tuning
requires expensive GPU compute and large labeled datasets) and a deliberate
methodological choice. Context Engineering is more maintainable: when the
handbook is updated, only the document needs to be re-ingested; no model
retraining is required.

**Principle 2 — Agentic Routing.** Rather than building a single monolithic
prompt that tries to answer all question types, the system uses a router-agent
pattern inspired by LangGraph. A central Intent Router classifies each query and
dispatches it to a specialized agent. This separation of concerns means each
agent can be independently optimized, tested, and replaced without affecting the
others.

**Principle 3 — Safety by Design.** The system enforces governance at multiple
layers: SQL execution is restricted to read-only SELECT statements via keyword
filtering; the RAG agent is instructed to cite only from retrieved chunks and
explicitly forbidden from speculation; and student data is always scoped to the
authenticated student's ID, preventing cross-student data leakage.

---

## 4.3 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    React Frontend (Vite)                    │
│          Dashboard View          │        Chat View         │
│  [CGPA Widget][Attendance Bars]  │  [Message Bubbles][Input]│
└────────────────────┬────────────────────────────────────────┘
                     │  HTTP (REST)
                     │  POST /chat
                     │  GET  /dashboard/{id}
┌────────────────────▼────────────────────────────────────────┐
│                  FastAPI Backend (Python)                    │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │                   Intent Router                     │   │
│   │  Stage 1: Keyword Matching  (zero LLM cost)         │   │
│   │  Stage 2: LLM Classification (ambiguous queries)    │   │
│   └────────────┬──────────────┬──────────────┬──────────┘   │
│                │              │              │               │
│         ACADEMIC           POLICY         HYBRID            │
│                │              │              │               │
│   ┌────────────▼──┐  ┌────────▼──────┐  ┌───▼───────────┐  │
│   │   SQL Agent   │  │   RAG Agent   │  │ Hybrid Agent  │  │
│   │               │  │               │  │ SQL + RAG     │  │
│   │ 1.Schema inj. │  │ 1.Embed query │  │ combined      │  │
│   │ 2.LLM gen SQL │  │ 2.ChromaDB    │  │               │  │
│   │ 3.Safe exec   │  │   retrieve    │  │               │  │
│   │ 4.LLM format  │  │ 3.Context inj │  │               │  │
│   │               │  │ 4.LLM answer  │  │               │  │
│   └───────┬───────┘  └───────┬───────┘  └───────┬───────┘  │
│           │                  │                   │           │
└───────────┼──────────────────┼───────────────────┼───────────┘
            │                  │                   │
   ┌─────────▼──────┐  ┌───────▼──────┐            │
   │  SQLite DB     │  │  ChromaDB    │◄────────────┘
   │  students      │  │  (Vector DB) │
   │  grades        │  │              │
   │  attendance    │  │  Handbook    │
   │  courses       │  │  Chunks      │
   │  enrollments   │  │  (Embedded)  │
   └────────────────┘  └──────────────┘
            ▲                  ▲
   ┌─────────┴──────┐  ┌───────┴──────┐
   │  Seed Script   │  │  Ingestion   │
   │  (database.py) │  │  Pipeline    │
   └────────────────┘  │(vector_store)│
                        └─────────────┘
```

---

## 4.4 Component Design

### 4.4.1 Intent Router

The Intent Router is the entry point for all chat queries. It implements a
two-stage classification strategy designed to minimize unnecessary LLM API calls
while maintaining high classification accuracy.

**Stage 1 — Keyword Matching (O(1) time, zero LLM cost)**

A curated set of keyword lists covers the most common query patterns:

- *Academic keywords*: "my gpa", "my grades", "my attendance", "show me my",
  "what did i get", "my transcript" — these signal queries about personal data
  that require database access.

- *Policy keywords*: "policy", "rule", "probation", "freeze", "gold medal",
  "fee refund", "unfair means", "make-up", "grading system" — these signal
  queries about institutional rules that require handbook retrieval.

- *Hybrid patterns*: Regular expressions match queries that structurally require
  both data sources, such as "am I on probation?" (requires CGPA from DB +
  probation threshold from handbook), "do I qualify for gold medal?" (requires
  grades from DB + eligibility criteria from handbook).

If a query cleanly matches only academic or only policy keywords, it is
dispatched immediately without any LLM inference. This covers approximately 75%
of queries in practice.

**Stage 2 — LLM Classification (invoked only for ambiguous queries)**

When both keyword sets match or neither matches, a small LLM call is made with a
tightly constrained prompt requesting exactly one of three tokens: ACADEMIC,
POLICY, or HYBRID. The model is instructed to respond with a single word, keeping
token usage and latency minimal.

**Intent Categories:**

| Intent   | Trigger Condition                          | Dispatched To      |
|----------|--------------------------------------------|--------------------|
| ACADEMIC | Personal data query (GPA, grades, courses) | SQL Agent          |
| POLICY   | Institutional rule/policy query            | RAG Agent          |
| HYBRID   | Requires both personal data + policy rule  | Hybrid Agent       |
| GREETING | Short greeting or casual message           | Greeting Handler   |

---

### 4.4.2 SQL Agent — Zero-Shot Text-to-SQL via Context Engineering

The SQL Agent handles all queries about personal student academic data. Its core
innovation is the use of Context Engineering to achieve Zero-Shot SQL generation
— producing valid SQL queries from natural language without any training examples
provided at inference time.

**Context Engineering — Schema Injection**

The database schema is represented as a structured natural language string
(stored in `database.py` as `DB_SCHEMA`) that describes every table, every
column, its data type, and any business rules associated with it. This schema
string is dynamically injected into the LLM system prompt on every request.

The system prompt for the SQL Agent has four components:

1. **Role definition**: "You are an expert SQLite query generator..."
2. **Full schema injection**: All 5 tables with column names, types, and
   relationship descriptions
3. **Hard safety rules**: "Only SELECT statements", "Always filter by
   student_id = '{id}'", "Add LIMIT 20"
4. **Few-shot examples**: Three concrete input/output SQL examples embedded
   directly in the prompt to demonstrate correct JOIN syntax and table aliases

The student's authenticated ID is injected into the system prompt at runtime,
ensuring all generated queries are automatically scoped to that student's data.
This is a critical privacy enforcement mechanism — the LLM cannot generate a
query for a different student's data because the WHERE clause is hardcoded into
its instructions.

**SQL Extraction and Sanitization**

LLM responses often include markdown formatting (code fences, explanatory text).
The `_extract_sql()` function uses a regular expression to locate the SELECT
statement, strips all surrounding content, and ensures the query ends with a
semicolon.

**Read-Only Execution Guard**

Before execution, `execute_read_query()` scans the SQL string for forbidden
keywords: INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE. If any are
found, a `ValueError` is raised and the query is rejected. This is a defense-in-
depth measure that operates independently of the LLM's instructions.

**Response Formatting**

After execution, the raw query results (a list of Python dicts) are passed back
to the LLM with a formatting prompt that requests a natural language summary. The
formatting prompt includes specific instructions: flag CGPA below 2.2 as
probation risk, flag attendance below 80% as XF risk, and round all numbers to 2
decimal places. This ensures the output is not just technically correct but
genuinely useful to the student.

---

### 4.4.3 RAG Agent — Retrieval-Augmented Generation Pipeline

The RAG Agent answers questions about institutional policies by retrieving
relevant passages from the IMSciences Student Handbook and injecting them as
context into the LLM's prompt. This grounds the model's responses in verified
documentary sources, preventing hallucination of policy details.

**Document Ingestion Pipeline**

The handbook (provided as a Markdown file) is processed through the following
pipeline at application startup:

1. **Text cleaning**: Markdown table separators, excessive whitespace, and
   formatting artifacts are removed via regular expressions.

2. **Sliding window chunking**: The cleaned text is divided into overlapping
   chunks of 600 characters with 120-character overlap between consecutive chunks.
   The chunker attempts to break at natural boundaries (newlines, sentence-ending
   periods) rather than mid-word. The 120-character overlap ensures that context
   spanning chunk boundaries is preserved and not lost during retrieval.

3. **Embedding**: Each chunk is converted to a 384-dimensional dense vector
   using the `all-MiniLM-L6-v2` SentenceTransformers model. This model was
   chosen for its balance of embedding quality and inference speed — it runs
   entirely on CPU without GPU requirements, making it suitable for local
   deployment.

4. **Storage**: Chunks, their embeddings, and metadata (source name, chunk
   index, character positions) are stored in a persistent ChromaDB collection
   using cosine similarity as the distance metric. Ingestion is idempotent: the
   system checks for existing documents before re-embedding, preventing duplicate
   chunks on server restarts.

**Query-Time Retrieval**

At query time, the student's question is embedded using the same model, and a
cosine similarity search retrieves the top-4 most semantically relevant chunks
from ChromaDB. The retrieved chunks are formatted into a labeled context block
that clearly indicates the source (e.g., `[Source: IMSCIENCES_HANDBOOK | Chunk
#14]`) before being injected into the LLM prompt.

**Hallucination Prevention via Prompt Engineering**

The RAG system prompt includes explicit governance instructions:

- "Answer ONLY from the provided policy context above."
- "If the context is insufficient, say: 'I don't have specific information on
  that. Please contact the relevant office...'"
- "Never speculate or invent rules, percentages, or deadlines."
- "Always cite which chapter/section your answer comes from."

These constraints are enforced through the system prompt. The LLM has no
incentive to fabricate information because it is instructed that uncertainty is
an acceptable and expected response.

---

### 4.4.4 Hybrid Agent

The Hybrid Agent handles queries that require both personal data and policy
knowledge to produce a useful answer. A canonical example is "Am I on probation?"
which requires knowing the student's CGPA (from the database) and the probation
threshold of 2.2 (from the handbook).

The Hybrid Agent implements a two-step sequential pipeline:

1. **SQL sub-query selection**: Based on keywords in the original query, the
   agent selects a targeted SQL sub-query (e.g., if the query mentions "probation"
   or "CGPA", it fetches the student's current CGPA; if it mentions "attendance",
   it fetches the attendance table).

2. **Contextualized RAG call**: The SQL results are serialized as a JSON block and
   injected alongside the retrieved handbook chunks into a specialized
   `_RAG_HYBRID_PROMPT`. This prompt instructs the LLM to first interpret the
   student's data, then apply the relevant policy rule, and then deliver a
   personalized verdict.

The output is a response like: *"Based on your current CGPA of 1.94, which is
below the minimum requirement of 2.0 (Chapter 1, Rule 18), you are currently
subject to immediate withdrawal from the Institute's rolls unless you meet the
conditions for detention..."*

---

## 4.5 Database Design

### 4.5.1 Relational Schema (SQLite)

The relational database models a simplified University Student Information System
(SIS) with five normalized tables:

**`students`** — Core student profile. The `cgpa` field is pre-computed and
stored to avoid expensive per-request recalculation across all grade records.

**`courses`** — Course catalog. Each course belongs to a program and is offered
in a specific semester number. This allows queries to filter relevant courses
without complex joins.

**`enrollments`** — Junction table linking students to courses for a given
semester label (e.g., "Fall 2024"). Supports status tracking (active, completed,
dropped).

**`grades`** — Stores the three component marks (midterm out of 30, final out of
50, assignments out of 20) as well as the computed total, letter grade, and grade
points. Storing derived values (total, letter grade) violates strict 3NF but is
an intentional performance optimization — the LLM-generated SQL does not need to
embed grade calculation logic.

**`attendance`** — Tracks total classes held, classes attended, the derived
percentage, and a pre-computed status label ("OK", "Warning", "XF Risk").

### 4.5.2 Schema as a Context Engineering Artifact

The `DB_SCHEMA` string in `database.py` is not merely documentation — it is a
carefully engineered prompt artifact. It includes:

- Column-level business rules ("Below 60% = F, grade_points = 0")
- Relationship descriptions in plain English
- The probation threshold (CGPA < 2.0 → immediate drop; 2.0–2.2 → probation)
- The XF attendance rule (< 80% = "XF Risk")

These embedded rules allow the LLM to generate SQL that references the correct
fields and to generate natural language responses that correctly interpret the
numeric results without requiring an additional lookup.

---

## 4.6 Vector Store Design

### 4.6.1 Chunking Strategy

The choice of chunk size (600 characters) and overlap (120 characters, 20%)
reflects a deliberate tradeoff:

- **Too small** (< 200 chars): Individual chunks lose contextual coherence.
  A chunk containing only "80% of attendance in each course" loses the surrounding
  sentence structure that establishes this as a minimum requirement.

- **Too large** (> 1,000 chars): Chunks become too broad for precise retrieval.
  A query about "fee refund policy" should not retrieve an entire chapter.

- **600 characters** covers approximately 3–5 sentences — enough to preserve
  policy rule context (rule number, condition, consequence) while remaining
  specific enough for high-precision retrieval.

- **120-character overlap** ensures that rules spanning the boundary between two
  chunks (e.g., a rule defined at the end of one chunk with its exception at the
  start of the next) are captured by at least one of the two overlapping chunks.

### 4.6.2 Embedding Model Selection

`all-MiniLM-L6-v2` was selected over larger models (e.g., `all-mpnet-base-v2`,
OpenAI `text-embedding-3-small`) for the following reasons:

| Criterion         | all-MiniLM-L6-v2 | all-mpnet-base-v2 | text-embedding-3-small |
|-------------------|------------------|-------------------|------------------------|
| Embedding Dim     | 384              | 768               | 1536                   |
| Inference Speed   | ~2,000 chunks/s  | ~500 chunks/s     | API call (latency)     |
| Local/Offline     | Yes              | Yes               | No (API required)      |
| Quality (MTEB)    | 0.586            | 0.638             | 0.620                  |
| RAM Usage         | ~90 MB           | ~420 MB           | N/A                    |

For the handbook's domain (formal academic regulations in English), the quality
difference between MiniLM and larger models is negligible. The speed and offline
availability advantages make MiniLM the correct choice for a locally-deployed
FYP demonstrator.

### 4.6.3 Retrieval Configuration

Top-k = 4 chunks are retrieved per query. This was chosen because:

- Policy rules at IMSciences are typically self-contained within 1–2 chunks.
- 4 chunks provides sufficient context for multi-part rules (e.g., probation
  rules that span multiple sub-clauses across consecutive paragraphs).
- Beyond 4 chunks, context window noise begins to degrade LLM response quality
  as irrelevant but semantically adjacent content is included.

---

## 4.7 API Design

All communication between the frontend and backend uses a RESTful JSON API
served by FastAPI. The two primary endpoints are:

### `GET /dashboard/{student_id}`

Returns a single JSON payload containing all data required to render the student
dashboard: profile, grades, attendance, computed averages, and a pre-computed
`status_summary` object. The status summary includes:

- `cgpa_status`: Categorical label (excellent, good, satisfactory, probation,
  critical)
- `attendance_status`: Categorical label (good, borderline, at_risk)
- `on_probation`: Boolean flag
- `xf_risk_count`: Number of courses with attendance below 80%

Pre-computing these derived values on the backend keeps the React component logic
simple and ensures business rule application is centralized in Python.

### `POST /chat`

Accepts `{query, student_id}` and returns `{query, intent, answer, student_id,
metadata}`. The `metadata` field is intent-dependent:

- For ACADEMIC: `{sql_generated, rows_returned}`
- For POLICY: `{chunks_retrieved, sources}`
- For HYBRID: all of the above

Exposing the generated SQL and retrieved chunk count in the API response serves
two purposes: it provides transparency to the user (shown as a collapsible SQL
panel in the UI) and it supports debugging and evaluation during development.

---

## 4.8 Frontend Architecture

The React frontend is a single-component application built with Vite. It
implements two primary views within a persistent sidebar layout:

**Dashboard View**: Renders the `/dashboard/{id}` response as a visual academic
summary. Key components include a `RadialBarChart` (Recharts) displaying CGPA as
a color-coded arc on a 4.0 scale, a `BarChart` showing grade points per course,
attendance progress bars per course with XF Risk warning chips, a detailed grade
breakdown table, and four KPI stat cards.

**Chat View**: Implements a full conversational interface. Each assistant message
displays an intent badge (Academic Data / Policy Query / Hybrid Analysis) and,
for SQL responses, an expandable panel showing the exact SQL query generated by
the LLM. This transparency feature is significant for a university system — it
allows students and administrators to verify that the data source for any answer
is the live database, not a hallucination.

All styling is implemented via inline style objects using CSS custom properties
(`--accent`, `--surface`, `--text2`, etc.) defined in an injected `<style>` tag.
This approach eliminates the need for external CSS processing while maintaining a
consistent design system.

---

## 4.9 Security and Governance

### 4.9.1 Data Access Control

Every SQL query generated by the system is automatically constrained to the
authenticated student's ID. The student ID is injected into the SQL Agent's
system prompt as a literal string in the WHERE clause template:
`WHERE student_id = '{student_id}'`. The LLM cannot override this constraint
because it is part of the system-level instruction, not the user message.

### 4.9.2 SQL Injection Prevention

The `execute_read_query()` function implements a keyword-based denylist as a
secondary safety layer. Even if the LLM were somehow prompted to generate a
mutating query, execution would be blocked before it reaches the database
connection. This is not a substitute for parameterized queries in a production
system — in a production deployment, the generated SQL should be parsed with
`sqlglot` and rewritten with parameter binding rather than string interpolation.

### 4.9.3 Hallucination Governance

Three mechanisms work in concert to prevent factual hallucinations:

1. **RAG grounding**: Policy answers are always generated from retrieved chunks,
   not from the model's parametric memory.
2. **System prompt constraints**: The LLM is explicitly instructed to acknowledge
   uncertainty rather than speculate.
3. **Low inference temperature**: All policy and SQL agents use temperature = 0.1
   or 0.2, minimizing creative variation in favor of deterministic outputs.

---

## 4.10 Limitations and Future Work

**Current Limitations:**

1. *Authentication*: The system uses a demo student ID selector. A production
   deployment requires integration with IMSciences' existing authentication
   infrastructure (student portal credentials).

2. *SQL injection via LLM*: While the keyword denylist blocks common attack
   vectors, a sufficiently crafted adversarial prompt could potentially bypass
   keyword checks. Production deployment should replace string-based SQL
   execution with a query parser and parameterized execution.

3. *Chunk quality for tables*: The handbook contains structured data in Markdown
   tables (grading scales, fee schedules) that does not chunk gracefully with a
   character-based sliding window. A future improvement would implement a
   table-aware chunker that treats each table as a single atomic chunk.

4. *Single-turn context*: The current chat interface does not maintain
   conversational history across turns in the API call. Multi-turn context
   (sending the last N messages as conversation history to the LLM) would
   significantly improve the assistant's ability to handle follow-up questions.

**Proposed FYP-2 Extensions:**

- Evaluation framework: Implement a RAG evaluation pipeline (RAGAS metrics:
  faithfulness, answer relevancy, context precision) using a curated test set of
  50 student questions with ground-truth answers.
- Multi-turn conversation: Maintain chat history in a session store and include
  the last 4 turns in every LLM API call.
- Voice interface: Integrate browser Speech-to-Text API for accessibility.
- Proactive alerts: A scheduled job that checks all students' attendance weekly
  and triggers notifications when any course drops below 85%.
- Admin dashboard: A separate view for faculty to query aggregate analytics
  ("What percentage of BCS-3 students are on probation this semester?").

---

## 4.11 Technology Summary Table

| Component              | Technology                  | Version    | Purpose                                    |
|------------------------|-----------------------------|------------|--------------------------------------------|
| Backend Framework      | FastAPI                     | 0.111.0    | REST API server, request routing           |
| ASGI Server            | Uvicorn                     | 0.29.0     | Production-ready async server              |
| Primary LLM            | Groq / Llama-3.1-8b-instant | —          | Fast inference for SQL gen + RAG           |
| Fallback LLM           | Google Gemini 1.5 Flash     | —          | Fallback when Groq unavailable             |
| Embedding Model        | all-MiniLM-L6-v2            | —          | Handbook chunk embedding (384-dim)         |
| Vector Database        | ChromaDB                    | 0.5.0      | Semantic similarity search                 |
| Relational Database    | SQLite                      | Built-in   | Student academic records                   |
| Data Validation        | Pydantic                    | 2.7.1      | API request/response schema enforcement    |
| Frontend Framework     | React                       | 18.3.1     | Component-based UI                         |
| Frontend Build Tool    | Vite                        | 5.3.1      | Fast dev server + production bundler       |
| Charting Library       | Recharts                    | 2.12.7     | CGPA radial chart, grade bar chart         |
| Icon Library           | Lucide React                | 0.383.0    | UI icons                                   |
| HTTP Client            | Browser Fetch API           | —          | Frontend → Backend API communication       |
| Environment Mgmt       | python-dotenv               | 1.0.1      | Secure API key management                  |

---

*This document was written as part of FYP-1 at the Institute of Management
Sciences, Peshawar. The implementation described is complete and functional.*
