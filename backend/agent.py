"""
agent.py — The brain of IM|Copilot.

Architecture:
  User Query
      |
  Intent Router  (rule-based keywords + LLM fallback)
      |          |
  ACADEMIC     POLICY      HYBRID
      |          |            |
  SQL Agent   RAG Agent   Both agents
      |          |            |
  Response Builder (natural language formatting)
"""

import os
import re
import json
import logging
from enum import Enum
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

from database import get_schema, execute_read_query
from vector_store import retrieve_context, build_rag_context_string

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# LLM Provider Setup
# ─────────────────────────────────────────────────────────────

GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

_groq_client  = None
_gemini_model = None


def _get_groq_client():
    global _groq_client
    if _groq_client is None and GROQ_API_KEY:
        from groq import Groq
        # Explicitly disable proxies to avoid httpx proxy issues
        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client


def _get_gemini_model():
    global _gemini_model
    if _gemini_model is None and GEMINI_API_KEY:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        _gemini_model = genai.GenerativeModel("gemini-2.0-flash")
    return _gemini_model


def _call_llm(system_prompt: str, user_message: str,
              temperature: float = 0.1, max_tokens: int = 1024) -> str:
    """
    Unified LLM caller. Tries Groq (Llama-3.1) first, falls back to Gemini.
    Low temperature enforces factual, deterministic responses.
    """
    # Try Groq
    groq = _get_groq_client()
    if groq:
        try:
            response = groq.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_message},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"[LLM] Groq failed: {e}. Trying Gemini.")
            logger.warning(f"[LLM] Groq error type: {type(e).__name__}")

    # Try Gemini
    gemini = _get_gemini_model()
    if gemini:
        try:
            full_prompt = f"{system_prompt}\n\nUser: {user_message}"
            response = gemini.generate_content(full_prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"[LLM] Gemini also failed: {e}")
            logger.error(f"[LLM] Gemini error type: {type(e).__name__}")
            raise RuntimeError("Both LLM providers failed. Check your API keys.")

    raise RuntimeError(
        "No LLM provider configured. Set GROQ_API_KEY or GEMINI_API_KEY in .env"
    )


# ─────────────────────────────────────────────────────────────
# Intent Classification
# ─────────────────────────────────────────────────────────────

class QueryIntent(str, Enum):
    ACADEMIC = "academic"   # Personal data queries → SQL Agent
    POLICY   = "policy"     # Policy/rule queries   → RAG Agent
    HYBRID   = "hybrid"     # Needs both agents
    GREETING = "greeting"   # Greetings/small talk


# Fast keyword patterns — avoid LLM call for obvious cases
_ACADEMIC_KW = [
    "my gpa", "my cgpa", "my grade", "my attendance", "my marks",
    "my courses", "my enrollment", "my score", "my result",
    "how am i doing", "am i passing", "my performance",
    "my midterm", "my final", "what did i get",
    "courses i am", "courses i'm", "my transcript",
    "show me my", "what are my",
]

_POLICY_KW = [
    "policy", "rule", "regulation", "handbook",
    "probation", "freeze", "freezing",
    "attendance requirement", "minimum attendance", "xf grade",
    "gold medal", "distinction", "scholarship", "fee refund",
    "make-up", "makeup exam", "retotal", "unfair means",
    "credit hours requirement", "grading system",
    "what is the", "how many credit", "can a student",
    "eligibility", "admission criteria", "library rule",
    "hostel rule", "transfer of credit", "semester load",
    "degree duration", "drop policy", "dropout",
]

_GREETING_KW = [
    "hello", "hi ", "hey ", "good morning", "good afternoon",
    "good evening", "thanks", "thank you", "bye", "goodbye",
]

# Hybrid patterns: personal + policy overlap
_HYBRID_PATTERNS = [
    r"am i (on probation|at risk|going to fail|eligible for medal)",
    r"will i (be dropped|get xf|fail|qualify for)",
    r"do i (qualify|meet the requirement|have enough attendance)",
    r"should i (freeze|drop|repeat|be worried)",
    r"am i (safe|in danger|at risk)",
]


def classify_intent(query: str) -> QueryIntent:
    """
    Two-stage classifier:
      Stage 1 — Keyword matching (zero LLM cost, instant)
      Stage 2 — LLM classification (only for ambiguous queries)
    """
    q = query.lower().strip()

    # Greeting check first
    if any(kw in q for kw in _GREETING_KW) and len(q) < 60:
        return QueryIntent.GREETING

    academic_hit = any(kw in q for kw in _ACADEMIC_KW)
    policy_hit   = any(kw in q for kw in _POLICY_KW)

    # Hybrid pattern check
    if any(re.search(p, q) for p in _HYBRID_PATTERNS):
        return QueryIntent.HYBRID

    # Clear wins
    if academic_hit and not policy_hit:
        return QueryIntent.ACADEMIC
    if policy_hit and not academic_hit:
        return QueryIntent.POLICY

    # Ambiguous — use LLM
    if academic_hit and policy_hit:
        return _llm_classify(query)

    # Default to POLICY (safer than exposing DB)
    return QueryIntent.POLICY


def _llm_classify(query: str) -> QueryIntent:
    """LLM-based intent disambiguation for edge cases."""
    prompt = (
        "Classify this university student query into ONE category:\n"
        "ACADEMIC = personal data (GPA, grades, attendance, enrolled courses)\n"
        "POLICY   = university rules, regulations, policies, fees, procedures\n"
        "HYBRID   = needs both personal data AND policy knowledge\n\n"
        "Respond with ONLY one word: ACADEMIC, POLICY, or HYBRID."
    )
    try:
        result = _call_llm(prompt, query, temperature=0.0, max_tokens=10)
        result = result.strip().upper()
        if "ACADEMIC" in result:
            return QueryIntent.ACADEMIC
        elif "HYBRID" in result:
            return QueryIntent.HYBRID
        else:
            return QueryIntent.POLICY
    except Exception:
        return QueryIntent.POLICY


# ─────────────────────────────────────────────────────────────
# SQL Agent
# ─────────────────────────────────────────────────────────────

def _build_sql_system_prompt(student_id: str) -> str:
    """
    Context Engineering: injects the full DB schema + student_id
    so the LLM can generate valid Zero-Shot SQL.
    """
    schema = get_schema()
    return f"""You are an expert SQLite query generator for a university student information system.
Your ONLY job is to produce a single valid SELECT statement.

{schema}

HARD RULES — never violate:
1. Only SELECT statements. Never INSERT, UPDATE, DELETE, DROP, ALTER, CREATE.
2. Always filter: WHERE student_id = '{student_id}' (for student-specific data).
3. Use JOINs when course names are needed (join with courses table).
4. Add LIMIT 20 to all queries.
5. Return ONLY raw SQL — no markdown, no backticks, no explanation.
6. If the question cannot be answered from the schema, return exactly:
   SELECT 'DATA_NOT_AVAILABLE' AS message;

QUICK EXAMPLES:
Q: "What is my CGPA?"
A: SELECT name, program, semester, cgpa FROM students WHERE student_id = '{student_id}';

Q: "Show my grades"
A: SELECT g.course_id, c.course_name, g.midterm_marks, g.final_marks, g.assignment_marks, g.total_marks, g.letter_grade, g.grade_points FROM grades g JOIN courses c ON g.course_id = c.course_id WHERE g.student_id = '{student_id}' ORDER BY g.semester_label DESC LIMIT 20;

Q: "Which courses have attendance issues?"
A: SELECT a.course_id, c.course_name, a.attended_classes, a.total_classes, a.attendance_pct, a.status FROM attendance a JOIN courses c ON a.course_id = c.course_id WHERE a.student_id = '{student_id}' ORDER BY a.attendance_pct ASC LIMIT 20;"""


_SQL_FORMAT_PROMPT = """You are IM|Copilot, a helpful academic assistant for IMSciences students.

Student asked: "{query}"

Database result:
{data}

Write a clear, friendly response:
- Summarize key numbers (round to 2 decimal places).
- If CGPA < 2.2, mention probation risk.
- If CGPA < 2.0, mention immediate drop risk.
- If any attendance < 80%, warn about XF grade risk.
- Use bullet points for multiple items.
- End with one practical tip if the data suggests a concern.
- Do NOT invent numbers not in the data."""


def run_sql_agent(query: str, student_id: str) -> dict:
    """
    SQL Agent:
      1. Build schema-injected system prompt
      2. LLM generates Zero-Shot SQL
      3. Sanitize and execute (read-only)
      4. LLM formats results into natural language
    """
    system_prompt = _build_sql_system_prompt(student_id)

    # Step 1: Generate SQL
    try:
        raw_sql = _call_llm(system_prompt, query, temperature=0.0, max_tokens=300)
    except Exception as e:
        return {
            "intent": "academic", "answer": f"AI service unavailable: {e}",
            "sql": None, "data": None, "error": str(e),
        }

    sql = _extract_sql(raw_sql)
    logger.info(f"[SQL Agent] Generated: {sql}")

    # Step 2: Execute (read-only guard inside execute_read_query)
    try:
        rows = execute_read_query(sql)
    except ValueError as e:
        return {
            "intent": "academic",
            "answer": "Security restriction: that query type is not permitted.",
            "sql": sql, "data": None, "error": str(e),
        }
    except Exception as e:
        logger.error(f"[SQL Agent] DB error: {e}")
        return {
            "intent": "academic",
            "answer": "I had trouble retrieving your data. Please try again.",
            "sql": sql, "data": None, "error": str(e),
        }

    if not rows:
        return {
            "intent": "academic",
            "answer": "No records found for your query. "
                      "This semester's data may not be available yet.",
            "sql": sql, "data": [], "error": None,
        }

    # Step 3: Format results as natural language
    data_str = json.dumps(rows, indent=2)
    fmt_prompt = _SQL_FORMAT_PROMPT.format(query=query, data=data_str)

    try:
        answer = _call_llm(
            "You are IM|Copilot, a friendly academic assistant for IMSciences.",
            fmt_prompt,
            temperature=0.3,
            max_tokens=600
        )
    except Exception:
        answer = f"Here is your requested data:\n\n{data_str}"

    return {
        "intent": "academic",
        "answer": answer,
        "sql":    sql,
        "data":   rows,
        "error":  None,
    }


def _extract_sql(raw: str) -> str:
    """Strips markdown fences and extracts the SQL SELECT statement."""
    raw = re.sub(r"```sql", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"```",    "", raw)
    match = re.search(r"(SELECT\b.+?)(?:;|$)", raw, re.IGNORECASE | re.DOTALL)
    if match:
        sql = match.group(1).strip()
        return sql if sql.endswith(";") else sql + ";"
    return raw.strip()


# ─────────────────────────────────────────────────────────────
# RAG Agent
# ─────────────────────────────────────────────────────────────

_RAG_SYSTEM_PROMPT = """You are IM|Copilot, the official AI assistant for the Institute of Management Sciences (IMSciences), Peshawar.

RETRIEVED POLICY CONTEXT (from the official IMSciences Student Handbook):
{context}

YOUR RULES:
1. Answer ONLY from the context above. Do not use outside knowledge for policy details.
2. If the context is insufficient, say: "I don't have specific information on that. Please contact the relevant office or consult the official Student Handbook."
3. Never speculate or invent rules, percentages, or deadlines.
4. Cite the chapter/section when answering (e.g., "According to Chapter 1, Rule 9...").
5. Be clear, concise, and student-friendly. Use bullet points for multi-part answers.
6. If a rule has conditions or exceptions, state them explicitly."""


_RAG_HYBRID_PROMPT = """You are IM|Copilot, the official AI assistant for IMSciences.

The student's question requires comparing their personal data with a university policy.

POLICY CONTEXT (from the IMSciences Student Handbook):
{context}

STUDENT'S CURRENT ACADEMIC DATA:
{student_data}

Student's question: {query}

Instructions:
1. Interpret the student's data (e.g., "Your current CGPA is 1.9...").
2. Apply the relevant policy rule from the context.
3. Give a direct, personalized verdict (e.g., "Based on Rule 18, you are currently on probation...").
4. If the situation is concerning, be empathetic and suggest concrete next steps.
5. Cite the exact rule you are applying.
6. Do NOT invent data or policy details not present above."""


def run_rag_agent(query: str, student_id: Optional[str] = None,
                  student_data: Optional[list] = None) -> dict:
    """
    RAG Agent:
      1. Embed query → retrieve top-4 handbook chunks from ChromaDB
      2. Format chunks into context block
      3. Inject context into system prompt
      4. LLM generates grounded, cited answer
    """
    try:
        chunks      = retrieve_context(query, top_k=4)
        context_str = build_rag_context_string(chunks)
    except Exception as e:
        # Fallback when ChromaDB is not available
        logger.warning(f"RAG Agent fallback: ChromaDB unavailable ({e})")
        return {
            "intent":  "policy" if not student_data else "hybrid",
            "answer":  "I'm sorry, but the handbook search feature is currently unavailable due to a technical issue. Please try asking about your academic records instead.",
            "chunks":  [],
            "context": "",
            "error":   f"Vector store unavailable: {str(e)}",
        }

    if student_data:
        system_prompt = _RAG_HYBRID_PROMPT.format(
            context=context_str,
            student_data=json.dumps(student_data, indent=2),
            query=query,
        )
        user_message = query
    else:
        system_prompt = _RAG_SYSTEM_PROMPT.format(context=context_str)
        user_message  = query

    try:
        answer = _call_llm(system_prompt, user_message, temperature=0.2, max_tokens=800)
    except Exception as e:
        return {
            "intent":  "policy",
            "answer":  f"AI service unavailable. Please try again. ({e})",
            "chunks":  chunks,
            "context": context_str,
            "error":   str(e),
        }

    return {
        "intent":  "policy" if not student_data else "hybrid",
        "answer":  answer,
        "chunks":  [{"rank": c["rank"], "source": c["source"],
                     "distance": c["distance"]} for c in chunks],
        "context": context_str,
        "error":   None,
    }


# ─────────────────────────────────────────────────────────────
# Hybrid Agent
# ─────────────────────────────────────────────────────────────

def run_hybrid_agent(query: str, student_id: str) -> dict:
    """
    Combines SQL + RAG:
      1. Fetch relevant student data via SQL Agent
      2. Feed that data + policy chunks into RAG Agent
      3. Return personalized policy-aware answer
    """
    q = query.lower()

    # Choose the most relevant SQL sub-query
    if any(w in q for w in ["probation", "cgpa", "gpa", "dropped"]):
        sub_query = "What is my current CGPA and program?"
    elif any(w in q for w in ["attendance", "xf", "absent"]):
        sub_query = "Show me my attendance percentage in all courses this semester"
    elif any(w in q for w in ["grade", "fail", "medal", "distinction"]):
        sub_query = "Show me all my grades and letter grades this semester"
    else:
        sub_query = "Show me my CGPA, program, semester, and current grades"

    sql_result   = run_sql_agent(sub_query, student_id)
    student_data = sql_result.get("data", [])

    rag_result = run_rag_agent(
        query,
        student_id=student_id,
        student_data=student_data,
    )

    return {
        "intent": "hybrid",
        "answer": rag_result["answer"],
        "sql":    sql_result.get("sql"),
        "data":   student_data,
        "chunks": rag_result.get("chunks", []),
        "error":  rag_result.get("error"),
    }


# ─────────────────────────────────────────────────────────────
# Greeting Handler
# ─────────────────────────────────────────────────────────────

_GREETING_PROMPT = """You are IM|Copilot, a friendly AI academic assistant for IMSciences Peshawar.
Greet the student warmly in 2-3 sentences. Mention you can help with:
university policies, GPA/grades, attendance, scholarships, and academic rules.
Be professional and welcoming."""


def run_greeting_handler(query: str) -> dict:
    try:
        answer = _call_llm(_GREETING_PROMPT, query, temperature=0.5, max_tokens=120)
    except Exception:
        answer = (
            "Hello! I'm IM|Copilot, your AI academic assistant for IMSciences. "
            "Ask me about your GPA, attendance, university policies, "
            "scholarships, or any academic rules. I'm here to help!"
        )
    return {"intent": "greeting", "answer": answer, "error": None}


# ─────────────────────────────────────────────────────────────
# Main Router — Public Entry Point
# ─────────────────────────────────────────────────────────────

def process_query(query: str, student_id: str) -> dict:
    """
    Central entry point for all chat queries.

    Args:
        query:      Natural language question from the student.
        student_id: Authenticated student ID (e.g., 'S001').

    Returns:
        dict with keys: intent, answer, and agent-specific metadata.
    """
    if not query or not query.strip():
        return {
            "intent": "error",
            "answer": "Please enter a valid question.",
            "error":  "Empty query",
        }

    intent = classify_intent(query)
    logger.info(f"[Router] '{query[:55]}' → {intent.value.upper()}")

    if intent == QueryIntent.GREETING:
        return run_greeting_handler(query)
    elif intent == QueryIntent.ACADEMIC:
        return run_sql_agent(query, student_id)
    elif intent == QueryIntent.POLICY:
        return run_rag_agent(query)
    elif intent == QueryIntent.HYBRID:
        return run_hybrid_agent(query, student_id)
    else:
        return run_rag_agent(query)


# ─────────────────────────────────────────────────────────────
# Self-test
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        ("What is the minimum attendance requirement?", "POLICY"),
        ("What is my current CGPA?",                   "ACADEMIC"),
        ("Show me my grades this semester",             "ACADEMIC"),
        ("Am I on probation?",                          "HYBRID"),
        ("What happens if I get XF?",                   "POLICY"),
        ("Hello!",                                      "GREETING"),
        ("Can I freeze my semester?",                   "POLICY"),
        ("Do I qualify for gold medal?",                "HYBRID"),
    ]

    print("=" * 55)
    print("IM|Copilot — Intent Router Test Suite")
    print("=" * 55)
    passed = 0
    for q, expected in tests:
        intent = classify_intent(q)
        got    = intent.value.upper()
        status = "PASS" if got == expected else "FAIL"
        if status == "PASS":
            passed += 1
        print(f"  [{status}] {q[:45]:<45} → {got}")
    print(f"\nResult: {passed}/{len(tests)} passed")
