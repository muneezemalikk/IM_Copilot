"""
main.py — FastAPI application for IM|Copilot.

Endpoints:
  GET  /                          Health check
  GET  /dashboard/{student_id}    Full student dashboard data
  POST /chat                      Main AI chat endpoint
  GET  /students                  List all students (dev/demo)
  GET  /vector-store/stats        ChromaDB stats
  POST /vector-store/reingest     Force re-ingestion of handbook
  GET  /intent-test               Dev tool: classify a query intent
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from database import initialize_database, get_student_dashboard, execute_read_query
from vector_store import initialize_vector_store, get_collection_stats
from agent import process_query, classify_intent

# ─────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("imcopilot")


# ─────────────────────────────────────────────────────────────
# Lifespan: startup & shutdown
# ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 50)
    logger.info("IM|Copilot — Starting Up")
    logger.info("=" * 50)

    # 1. Initialize SQLite
    logger.info("[Startup] Initializing SQLite...")
    initialize_database()
    logger.info("[Startup] SQLite ready.")

    # 2. Initialize ChromaDB - Temporarily disabled due to NumPy compatibility issues
    # handbook_path = os.path.abspath(
    #     os.path.join(os.path.dirname(__file__), "..", "handbook.md")
    # )
    # logger.info("[Startup] Initializing ChromaDB...")
    # stats = initialize_vector_store(
    #     handbook_path if os.path.exists(handbook_path) else None
    # )
    # logger.info(f"[Startup] Vector store ready: {stats}")
    logger.info("[Startup] Vector store initialization skipped (NumPy compatibility issue).")
    logger.info("[Startup] Ready to serve.")

    yield

    logger.info("[Shutdown] Goodbye.")


# ─────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="IM|Copilot API",
    description=(
        "Hybrid AI Academic Assistant for IMSciences Peshawar. "
        "Combines RAG (policy queries) with Text-to-SQL (academic data)."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────
# Request / Response Models
# ─────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    query:      str = Field(..., min_length=1, max_length=1000)
    student_id: str = Field(default="S001")

    class Config:
        json_schema_extra = {
            "example": {
                "query":      "What is my current CGPA and am I on probation?",
                "student_id": "S001",
            }
        }


class ChatResponse(BaseModel):
    query:      str
    intent:     str
    answer:     str
    student_id: str
    metadata:   dict


class DashboardResponse(BaseModel):
    student_id:       str
    student:          dict
    semester_label:   str
    grades:           list
    attendance:       list
    avg_attendance:   float
    at_risk_courses:  list
    total_courses:    int
    status_summary:   dict


# ─────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def health_check():
    return {
        "status":  "running",
        "service": "IM|Copilot API",
        "version": "1.0.0",
        "docs":    "/docs",
    }


@app.get(
    "/dashboard/{student_id}",
    response_model=DashboardResponse,
    tags=["Dashboard"],
    summary="Get full student dashboard",
)
async def get_dashboard(student_id: str):
    """
    Returns all data needed to render the student dashboard:
    - Student profile (name, program, semester, CGPA)
    - Grades per course (midterm, final, assignments, letter grade)
    - Attendance per course (attended/total, percentage, status)
    - At-risk courses (attendance < 80%)
    - Status summary (probation flag, XF risk count)
    """
    data = get_student_dashboard(student_id.upper())
    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"Student '{student_id}' not found. Available IDs: S001–S010.",
        )

    cgpa    = data["student"].get("cgpa", 0.0)
    avg_att = data["avg_attendance"]

    # GPA status label
    if   cgpa >= 3.5: gpa_status = "excellent"
    elif cgpa >= 2.5: gpa_status = "good"
    elif cgpa >= 2.2: gpa_status = "satisfactory"
    elif cgpa >= 2.0: gpa_status = "probation"
    else:             gpa_status = "critical"

    # Attendance status label
    if   avg_att >= 85: att_status = "good"
    elif avg_att >= 80: att_status = "borderline"
    else:               att_status = "at_risk"

    status_summary = {
        "cgpa_status":           gpa_status,
        "attendance_status":     att_status,
        "on_probation":          cgpa < 2.2,
        "xf_risk_count":         len(data["at_risk_courses"]),
        "probation_threshold":   2.2,
        "attendance_threshold":  80.0,
    }

    return DashboardResponse(
        student_id=student_id.upper(),
        **data,
        status_summary=status_summary,
    )


@app.post(
    "/chat",
    response_model=ChatResponse,
    tags=["Chat"],
    summary="Send a message to IM|Copilot",
)
async def chat(request: ChatRequest):
    """
    Main AI chat endpoint. Routes through the Intent Router:

    - **ACADEMIC** → SQL Agent: Text-to-SQL on the student database
    - **POLICY**   → RAG Agent: ChromaDB handbook retrieval + LLM
    - **HYBRID**   → Both agents: personalized policy-aware answer
    - **GREETING** → Friendly welcome response

    The `metadata` field contains agent-specific info:
    - For ACADEMIC: `sql_generated`, `rows_returned`
    - For POLICY:   `chunks_retrieved`, `sources`
    - For HYBRID:   both of the above
    """
    logger.info(
        f"[/chat] student={request.student_id} "
        f"query='{request.query[:60]}'"
    )

    result = process_query(
        query=request.query,
        student_id=request.student_id.upper(),
    )

    intent = result.get("intent", "unknown")

    metadata: dict = {"error": result.get("error")}

    if intent == "academic":
        metadata["sql_generated"] = result.get("sql")
        metadata["rows_returned"] = len(result.get("data") or [])

    elif intent == "policy":
        metadata["chunks_retrieved"] = len(result.get("chunks") or [])
        metadata["sources"] = list({
            c.get("source", "handbook")
            for c in (result.get("chunks") or [])
        })

    elif intent == "hybrid":
        metadata["sql_generated"]    = result.get("sql")
        metadata["rows_returned"]    = len(result.get("data") or [])
        metadata["chunks_retrieved"] = len(result.get("chunks") or [])

    return ChatResponse(
        query=request.query,
        intent=intent,
        answer=result.get("answer", "I could not generate a response."),
        student_id=request.student_id.upper(),
        metadata=metadata,
    )


@app.get("/students", tags=["Dev / Demo"])
async def list_students(
    program: Optional[str] = Query(
        None,
        description="Filter by program: BBA, BCS, MBA"
    )
):
    """
    Lists all students. Used by the demo login selector on the frontend.
    """
    if program:
        sql = (
            f"SELECT student_id, name, program, semester, cgpa "
            f"FROM students WHERE UPPER(program) = '{program.upper()}' "
            f"ORDER BY student_id"
        )
    else:
        sql = (
            "SELECT student_id, name, program, semester, cgpa "
            "FROM students ORDER BY student_id"
        )

    try:
        rows = execute_read_query(sql)
        return {"students": rows, "count": len(rows)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/students/{student_id}", tags=["Dev / Demo"])
async def get_student(student_id: str):
    """Returns basic profile for a single student."""
    try:
        rows = execute_read_query(
            f"SELECT * FROM students WHERE student_id = '{student_id.upper()}'"
        )
        if not rows:
            raise HTTPException(status_code=404, detail="Student not found.")
        return rows[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/vector-store/stats", tags=["Vector Store"])
async def vector_store_stats():
    """Returns ChromaDB collection stats."""
    return get_collection_stats()


@app.post("/vector-store/reingest", tags=["Vector Store"])
async def reingest_handbook():
    """
    Clears and re-ingests the handbook into ChromaDB.
    Use this when the handbook document is updated.
    """
    try:
        import chromadb
        from vector_store import CHROMA_PATH, COLLECTION_NAME
        from chromadb.config import Settings
        import vector_store as vs

        client = chromadb.PersistentClient(
            path=CHROMA_PATH,
            settings=Settings(anonymized_telemetry=False)
        )
        try:
            client.delete_collection(COLLECTION_NAME)
            logger.info("[Reingest] Old collection deleted.")
        except Exception:
            pass

        vs._collection = None  # Reset singleton

        handbook_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "handbook.md")
        )
        stats = initialize_vector_store(
            handbook_path if os.path.exists(handbook_path) else None
        )
        return {"status": "success", "stats": stats}

    except Exception as e:
        logger.error(f"[Reingest] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/intent-test", tags=["Dev / Demo"])
async def test_intent(
    q: str = Query(..., description="Query string to classify")
):
    """
    Development tool: classifies a query's intent without running the full agent.
    Useful for debugging the Intent Router.
    """
    intent = classify_intent(q)
    return {"query": q, "intent": intent.value}


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
