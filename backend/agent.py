"""
agent.py — Hybrid AI Agent for IM|Copilot
Intelligently routes between SQL Agent (personal data) and RAG Agent (policies).
"""

import os
import re
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)

from database import DB_SCHEMA as DATABASE_SCHEMA, execute_read_query as execute_safe_sql
from vector_store import retrieve_context as retrieve_relevant_chunks, build_rag_context_string as build_rag_context, HANDBOOK_INLINE_TEXT

# ── API Keys ───────────────────────────────────
GROQ_API_KEY   = os.getenv("GROQ_API_KEY",   "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
LLM_PROVIDER   = os.getenv("LLM_PROVIDER",  "groq").strip().lower()

print(f"[Agent] Provider : {LLM_PROVIDER}")
print(f"[Agent] Groq key : {'SET ✓' if GROQ_API_KEY else 'MISSING ✗'}")
print(f"[Agent] Gemini key: {'SET ✓' if GEMINI_API_KEY else 'MISSING ✗'}")


# ─────────────────────────────────────────────────
# LLM CALL (Groq or Gemini)
# ─────────────────────────────────────────────────
def call_llm(system_prompt: str, user_prompt: str, temperature: float = 0.1, history: list[dict] = None) -> str:
    """Call the configured LLM provider and return the text response."""
    history = history or []

    if LLM_PROVIDER == "groq" and GROQ_API_KEY:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        messages.append({"role": "user", "content": user_prompt})

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=temperature,
            max_tokens=1024,
        )
        return response.choices[0].message.content.strip()

    elif GEMINI_API_KEY:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=system_prompt
        )
        gemini_history = []
        for msg in history:
            role = "user" if msg.get("role") == "user" else "model"
            gemini_history.append({"role": role, "parts": [msg.get("content", "")]})
            
        chat = model.start_chat(history=gemini_history)
        response = chat.send_message(user_prompt)
        return response.text.strip()

    else:
        raise RuntimeError(
            "No LLM provider available. "
            "Add GROQ_API_KEY or GEMINI_API_KEY to backend/.env"
        )


# ─────────────────────────────────────────────────
# INTENT ROUTER — keyword-first, LLM as fallback
# ─────────────────────────────────────────────────

# Strong signals that mean "give me MY data from the database"
ACADEMIC_KEYWORDS = [
    # GPA / grades
    "gpa", "cgpa", "sgpa", "grade", "grades", "marks", "score", "result",
    "grade point", "semester result", "my result", "my grade",
    # Attendance
    "attendance", "absent", "absences", "present", "classes attended",
    "how many classes", "attendance percentage", "my attendance", "xf",
    # Courses
    "my course", "enrolled", "enrollment", "current courses", "subjects",
    "my subjects", "registered courses", "taking this semester", "improve",
    # Personal academic
    "my cgpa", "my gpa", "my marks", "my score", "my performance",
    "academic standing", "probation status", "my status",
    "credit hours", "passed courses", "failed courses",
    # Dashboard-style
    "dashboard", "academic summary", "semester summary",
    "show my", "what is my", "tell me my", "display my",
    "how am i doing", "my academic",
]

# Strong signals that mean "explain a policy / rule"
POLICY_KEYWORDS = [
    "policy", "rule", "regulation", "handbook", "procedure",
    "what is the", "how does", "explain", "define", "what are the requirements",
    "eligibility", "criteria", "allowed", "permitted", "prohibited",
    "penalty", "fine", "scholarship", "hostel", "library", "transport",
    "freeze semester", "drop course", "withdraw", "make-up exam",
    "gold medal", "distinction", "degree requirement",
    "minimum attendance", "probation policy", "grading system",
    "how many credit", "duration of", "academic year", "xf",
]


def classify_intent(query: str, student_id: str = None) -> str:
    """
    Classify query intent using keyword matching first (fast + reliable).
    Falls back to LLM classification only when truly ambiguous.

    Returns: 'academic_query' | 'policy_query' | 'hybrid_query'
    """
    q_lower = query.lower().strip()

    # ── Personal pronouns + academic terms → always SQL ──
    has_my = any(w in q_lower for w in ["my ", "i ", "me ", "am i", "do i", "i have", "i am"])
    has_academic = any(k in q_lower for k in ACADEMIC_KEYWORDS)
    has_policy   = any(k in q_lower for k in POLICY_KEYWORDS)

    # Has both → hybrid
    if has_academic and has_policy:
        return "hybrid_query"

    # Personal data question → SQL
    if has_my and has_academic:
        return "academic_query"

    # Pure personal data (no "my" needed for obvious queries)
    if any(k in q_lower for k in [
        "gpa", "cgpa", "sgpa", "attendance percentage",
        "my grade", "my marks", "my score", "my result",
        "show my", "display my", "what is my", "tell me my"
    ]):
        return "academic_query"

    # Pure policy question
    if has_policy and not has_academic:
        return "policy_query"

    # Ambiguous — ask LLM (fast classification call)
    try:
        classification = call_llm(
            system_prompt=(
                "You are a query classifier for a university academic assistant.\n"
                "Classify the user query into EXACTLY one of these categories:\n\n"
                "- academic_query: asking about personal student data (GPA, grades, attendance, enrolled courses, results)\n"
                "- policy_query: asking about university rules, policies, regulations, procedures, requirements\n"
                "- hybrid_query: asking about both personal data AND policies\n\n"
                "Reply with ONLY the category name, nothing else."
            ),
            user_prompt=f"Query: {query}",
            temperature=0.0
        )
        intent = classification.strip().lower()
        if intent in ("academic_query", "policy_query", "hybrid_query"):
            return intent
        # If LLM gives unexpected output, default to academic if student_id is present
        return "academic_query" if student_id else "policy_query"

    except Exception:
        # Safe fallback
        return "academic_query" if student_id and has_academic else "policy_query"


# ─────────────────────────────────────────────────
# SQL AGENT
# ─────────────────────────────────────────────────
def run_sql_agent(query: str, student_id: str = None, is_admin: bool = False, format_response: bool = True, history: list = None) -> dict:
    """
    Generates SQL from the user's natural language query,
    executes it safely, and returns a natural language answer.
    """
    history = history or []

    if is_admin:
        user_context = "CURRENT USER: ADMINISTRATOR (Full access to all students. Use aggregations like COUNT, AVG, SUM, GROUP BY.)"
        rule_3 = "3. You may query across all students and programs without restriction."
    else:
        user_context = f"CURRENT USER:\n- Student ID: {student_id}\n- You MUST always filter queries using: WHERE student_id = '{student_id}'"
        rule_3 = f"3. Always include student_id = '{student_id}' in the WHERE clause."

    # ── Step 1: Generate SQL ──────────────────────
    sql_system_prompt = f"""You are an expert SQL generator for a university academic database.

{DATABASE_SCHEMA}

{user_context}

YOUR TASK:
1. Read the user's question carefully.
2. Generate a single, valid SQLite SELECT query that answers it.
{rule_3}
4. Return ONLY the raw SQL query — no explanation, no markdown, no backticks.
5. Do NOT generate INSERT, UPDATE, DELETE, DROP, or any mutating SQL.

COMMON QUERY PATTERNS:
{"- Admin queries: SELECT COUNT(*) FROM students WHERE cgpa < 2.0" if is_admin else "- For GPA/CGPA: SELECT cgpa FROM students WHERE student_id = '{student_id}'"}
"""

    sql_user_prompt = f"Generate SQL to answer the latest question: {query}"

    try:
        raw_sql = call_llm(sql_system_prompt, sql_user_prompt, temperature=0.0, history=history)
    except RuntimeError as e:
        return {
            "response": f"❌ AI service unavailable: {str(e)}\n\nCheck that GROQ_API_KEY or GEMINI_API_KEY is set in backend/.env",
            "intent":   "error",
            "sources":  [],
            "sql_used": None,
            "raw_rows": []
        }

    # ── Clean the generated SQL ───────────────────
    sql = raw_sql.strip()
    sql = re.sub(r"```(?:sql)?", "", sql, flags=re.IGNORECASE)
    sql = sql.replace("```", "").strip()

    # ── Step 2: Execute SQL safely ────────────────
    try:
        rows = execute_safe_sql(sql)
    except ValueError as e:
        # SQL execution failed — try a safe fallback query
        fallback_sql = f"SELECT * FROM students WHERE student_id = '{student_id}'"
        try:
            rows = execute_safe_sql(fallback_sql)
            sql  = fallback_sql
        except Exception:
            return {
                "response": f"I had trouble retrieving your data. The query encountered an error: {str(e)}",
                "intent":   "academic_query",
                "sources":  [],
                "sql_used": sql,
                "rows_returned": 0,
                "raw_rows": []
            }

    if not format_response:
        return {
            "response": "",
            "intent":   "academic_query",
            "sources":  ["Student Academic Database"],
            "sql_used": sql,
            "rows_returned": len(rows),
            "raw_rows": rows
        }

    # ── Step 3: Format results into natural language ──
    format_system_prompt = """You are a friendly, helpful academic advisor assistant at IMSciences.
You are given structured database results and must convert them into a clear, natural response.

RULES:
- Be direct and specific — mention exact numbers (GPA values, percentages, grades)
- Use a warm, supportive tone
- If attendance is below 75% in any course, gently flag it as a concern
- If CGPA is >= 2.0 and < 2.2, mention that the student is on probation
- If CGPA is < 2.0, mention that the student is at risk of being dropped
- Format numbers clearly (e.g., "3.45 out of 4.0", "85%")
- Do NOT say you cannot access data — you have the data in front of you
- Keep the response concise but complete
- Use bullet points or short paragraphs for multiple items
"""

    format_user_prompt = f"""Student's latest question: "{query}"

Database results:
{rows}
"""

    if not rows:
        format_user_prompt += "\nNote: The query returned empty results ([]). This means the student has no records matching their criteria (e.g., no bad grades, no courses with low attendance). DO NOT say 'your database is empty' or 'you have a clean slate'. Reassure them naturally (e.g., 'I checked your profile and you don't have any courses flagged')."
    else:
        format_user_prompt += "\nWrite a helpful, natural language response using these exact results."

    try:
        response_text = call_llm(format_system_prompt, format_user_prompt, temperature=0.3, history=history)
    except Exception:
        # Fallback: just format the raw data
        response_text = format_rows_as_text(query, rows)

    return {
        "response": response_text,
        "intent":   "academic_query",
        "sources":  ["Student Academic Database"],
        "sql_used": sql,
        "rows_returned": len(rows),
        "raw_rows": rows
    }


def format_rows_as_text(query: str, rows: list[dict]) -> str:
    """Simple fallback formatter if LLM call fails."""
    if not rows:
        return "No data found."
    if len(rows) == 1:
        row = rows[0]
        lines = [f"**{k.replace('_', ' ').title()}**: {v}" for k, v in row.items() if v is not None]
        return "\n".join(lines)
    lines = []
    for i, row in enumerate(rows, 1):
        parts = ", ".join(f"{k}: {v}" for k, v in row.items() if v is not None)
        lines.append(f"{i}. {parts}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────
# RAG AGENT
# ─────────────────────────────────────────────────
def run_rag_agent(query: str, history: list = None) -> dict:
    """
    Retrieves relevant policy chunks from ChromaDB and
    generates a grounded, cited answer.
    """
    history = history or []

    # ── Retrieve chunks ───────────────────────────
    chunks = retrieve_relevant_chunks(query, top_k=4)
    context = build_rag_context(chunks)
    sources = list({c["source"] for c in chunks})

    if not context:
        context = f"FALLBACK HANDBOOK CONTEXT:\n{HANDBOOK_INLINE_TEXT}"
        sources = ["Inline Handbook Fallback"]

    # ── Generate answer ───────────────────────────
    rag_system_prompt = """You are an expert academic policy advisor for the Institute of Management Sciences (IMSciences), Peshawar.

You answer students' questions about university rules, policies, and regulations using ONLY the provided handbook excerpts.

RULES:
- Base your answer ONLY on the provided context below
- Be specific — quote relevant numbers, percentages, and thresholds
- If the context doesn't contain enough information, say so clearly and suggest contacting the relevant office
- Do NOT make up policies or rules
- Keep the tone helpful, professional, and student-friendly
- Structure longer answers with clear points
"""

    rag_user_prompt = f"""Student's latest question: {query}

Relevant Handbook Excerpts:
{context}

Provide a clear, accurate answer based strictly on the above excerpts."""

    try:
        response_text = call_llm(rag_system_prompt, rag_user_prompt, temperature=0.2, history=history)
    except RuntimeError as e:
        return {
            "response": f"❌ AI service unavailable: {str(e)}\n\nCheck that GROQ_API_KEY or GEMINI_API_KEY is set in backend/.env",
            "intent":   "error",
            "sources":  [],
            "chunks_retrieved": 0
        }

    return {
        "response": response_text,
        "intent":   "policy_query",
        "sources":  sources,
        "sql_used": None,
        "chunks_retrieved": len(chunks)
    }


# ─────────────────────────────────────────────────
# HYBRID AGENT (both personal data + policy)
# ─────────────────────────────────────────────────
def run_hybrid_agent(query: str, student_id: str = None, is_admin: bool = False, history: list = None) -> dict:
    """Runs both SQL and RAG pipelines and combines their outputs holistically via a single LLM prompt."""
    history = history or []
    if not is_admin and not student_id:
        return run_rag_agent(query, history=history)

    # 1. Fetch SQL data (skip natural language formatting step)
    sql_result = run_sql_agent(query, student_id=student_id, is_admin=is_admin, format_response=False, history=history)
    raw_rows = sql_result.get("raw_rows", [])
    sql_used = sql_result.get("sql_used")

    # 2. Fetch Policy chunks
    chunks = retrieve_relevant_chunks(query, top_k=4)
    context = build_rag_context(chunks)
    sources = list({c["source"] for c in chunks})

    if not context:
        context = f"FALLBACK HANDBOOK CONTEXT:\n{HANDBOOK_INLINE_TEXT}"
        if "Inline Handbook Fallback" not in sources:
            sources.append("Inline Handbook Fallback")

    # 3. Generate Holistic Response
    hybrid_system_prompt = """You are an expert academic advisor for IMSciences Peshawar.
You are given a student's personal database records AND official university policy excerpts.
Your task is to provide a single, unified, conversational response that answers the student's question by applying the policy rules to their specific data.

RULES:
- Interpret the student's database records using the policy context.
- Quote specific numbers from their data (e.g., "Your attendance in CS101 is 78%").
- Cite the relevant policy rule clearly.
- Be warm, direct, and helpful. 
- NEVER use disjointed headers like "Your Academic Data:" or "Relevant Policy:". Write a natural, cohesive response.
- If the database records are empty ([]), it means no negative records matched their query. DO NOT use robotic phrases like "your database records are empty" or "clean slate". Instead, naturally reassure them (e.g., "I checked your profile and you currently don't have any courses falling below the threshold"), then explain the policy."""

    hybrid_user_prompt = f"""Student's latest question: "{query}"

Database Records (JSON):
{raw_rows}

Policy Handbook Excerpts:
{context}

Provide a personalized, holistic analysis:"""

    try:
        response_text = call_llm(hybrid_system_prompt, hybrid_user_prompt, temperature=0.2, history=history)
    except Exception as e:
        response_text = f"❌ AI service unavailable: {str(e)}"

    db_source = ["Student Academic Database"] if sql_used else []

    return {
        "response": response_text,
        "intent":   "hybrid_query",
        "sources":  sources + db_source,
        "sql_used": sql_used,
        "rows_returned": len(raw_rows),
        "chunks_retrieved": len(chunks)
    }


# ─────────────────────────────────────────────────
# MAIN ROUTER
# ─────────────────────────────────────────────────
def run_chat_agent(query: str, student_id: str = None, user_role: str = "student", history: list = None) -> dict:
    """
    Main entry point. Routes query to the correct agent.

    Args:
        query:      The user's natural language question
        student_id: The authenticated student's ID (from JWT token)
        user_role:  'student' or 'admin'

    Returns:
        dict with keys: response, intent, sources, sql_used
    """
    if not query.strip():
        return {
            "response": "Please ask me a question!",
            "intent":   "error",
            "sources":  [],
            "sql_used": None
        }

    print(f"\n[Agent] Query     : {query}")
    print(f"[Agent] Student ID: {student_id}")
    print(f"[Agent] Role      : {user_role}")

    # ── Classify intent ───────────────────────────
    intent = classify_intent(query, student_id)
    print(f"[Agent] Intent    : {intent}")

    # ── Route to correct agent ────────────────────
    try:
        is_admin = (user_role == "admin")

        if intent == "academic_query":
            if not is_admin and not student_id:
                return {
                    "response": "I need your student ID to look up academic data. Please make sure you're logged in.",
                    "intent":   "academic_query",
                    "sources":  [],
                    "sql_used": None
                }
            return run_sql_agent(query, student_id=student_id, is_admin=is_admin, history=history)

        elif intent == "policy_query":
            return run_rag_agent(query, history=history)

        elif intent == "hybrid_query":
            return run_hybrid_agent(query, student_id=student_id, is_admin=is_admin, history=history)

        else:
            return run_rag_agent(query, history=history)

    except Exception as e:
        print(f"[Agent] ERROR: {e}")
        return {
            "response": f"I encountered an unexpected error: {str(e)}. Please try again.",
            "intent":   "error",
            "sources":  [],
            "sql_used": None
        }


# ─────────────────────────────────────────────────
# STANDALONE TEST
# ─────────────────────────────────────────────────
if __name__ == "__main__":
    from database import initialize_database
    initialize_database()

    test_student = "STU-2021-001"
    test_cases = [
        ("What is my CGPA?",                         test_student),
        ("Show my attendance for this semester",      test_student),
        ("What are my grades?",                       test_student),
        ("What is the probation policy?",             None),
        ("What is the minimum attendance required?",  None),
        ("Am I at risk of probation based on my GPA?",test_student),
    ]

    print("\n" + "="*60)
    for query, sid in test_cases:
        print(f"\nQ: {query}")
        print(f"   Student ID: {sid}")
        result = run_chat_agent(query, student_id=sid)
        print(f"   Intent : {result['intent']}")
        print(f"   Answer : {result['response'][:200]}...")
        print("-"*60)
