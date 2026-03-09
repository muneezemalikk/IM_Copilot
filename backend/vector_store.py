"""
vector_store.py — ChromaDB setup, document ingestion, and RAG retrieval.
Falls back to inline handbook text gracefully if ChromaDB is unavailable.
"""

import os
import re
import hashlib
from typing import Optional

# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────
CHROMA_PATH       = os.path.join(os.path.dirname(__file__), "chroma_db")
COLLECTION_NAME   = "imsciences_handbook"
EMBEDDING_MODEL   = "all-MiniLM-L6-v2"
CHUNK_SIZE        = 600
CHUNK_OVERLAP     = 120
TOP_K_RESULTS     = 4

# ─────────────────────────────────────────────────────────────
# Singleton model loader
# ─────────────────────────────────────────────────────────────
_embedding_model = None
_chroma_client   = None
_collection      = None
_chroma_available = None  # None = untested, True/False = tested


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        print(f"[VectorStore] Loading embedding model: {EMBEDDING_MODEL}")
        # Force CPU — MPS (Apple Silicon) causes encoding to hang
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL, device="cpu")
    return _embedding_model


def _is_chroma_available() -> bool:
    """Test whether chromadb can be imported and used."""
    global _chroma_available
    if _chroma_available is not None:
        return _chroma_available
    try:
        import chromadb
        _chroma_available = True
    except Exception as e:
        print(f"[VectorStore] ChromaDB not available: {e}")
        _chroma_available = False
    return _chroma_available


def _get_collection():
    global _chroma_client, _collection
    if _collection is None:
        import chromadb
        from chromadb.config import Settings
        _chroma_client = chromadb.PersistentClient(
            path=CHROMA_PATH,
            settings=Settings(anonymized_telemetry=False)
        )
        _collection = _chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )
    return _collection


# ─────────────────────────────────────────────────────────────
# Text Chunking
# ─────────────────────────────────────────────────────────────
def _clean_text(text: str) -> str:
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = re.sub(r'\|[-| ]+\|', '', text)
    text = re.sub(r'^\s*\|.*\|\s*$', '', text, flags=re.MULTILINE)
    return text.strip()


def _split_into_chunks(text: str, chunk_size: int = CHUNK_SIZE,
                        overlap: int = CHUNK_OVERLAP) -> list:
    text   = _clean_text(text)
    chunks = []
    start  = 0
    idx    = 0

    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            break_at = text.rfind('\n', start, end)
            if break_at == -1 or break_at <= start:
                break_at = text.rfind('. ', start, end)
            if break_at == -1 or break_at <= start:
                break_at = end
            else:
                break_at += 1
        else:
            break_at = len(text)

        chunk_text = text[start:break_at].strip()
        if chunk_text:
            chunks.append({
                "text":        chunk_text,
                "chunk_index": idx,
                "start_char":  start,
                "end_char":    break_at,
            })
            idx += 1

        start = break_at - overlap
        if start < 0:
            start = 0

    return chunks


def _make_chunk_id(text: str, index: int) -> str:
    h = hashlib.md5(text.encode()).hexdigest()[:8]
    return f"chunk_{index}_{h}"


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────
def ingest_document(markdown_text: str, source_name: str = "handbook") -> int:
    if not _is_chroma_available():
        print("[VectorStore] ChromaDB not available, skipping ingestion.")
        return 0

    try:
        collection = _get_collection()
    except Exception as e:
        print(f"[VectorStore] Cannot get collection: {e}")
        return 0

    existing = collection.get(where={"source": source_name}, limit=1)
    if existing and existing["ids"]:
        print(f"[VectorStore] '{source_name}' already ingested "
              f"({collection.count()} total chunks). Skipping.")
        return 0

    model  = _get_embedding_model()
    chunks = _split_into_chunks(markdown_text)
    print(f"[VectorStore] Ingesting '{source_name}': {len(chunks)} chunks...")

    BATCH_SIZE = 64
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        texts      = [c["text"]        for c in batch]
        embeddings = model.encode(texts, show_progress_bar=False).tolist()
        ids        = [_make_chunk_id(c["text"], c["chunk_index"]) for c in batch]
        metadatas  = [
            {
                "source":      source_name,
                "chunk_index": c["chunk_index"],
                "start_char":  c["start_char"],
                "end_char":    c["end_char"],
            }
            for c in batch
        ]
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

    print(f"[VectorStore] Done. Collection size: {collection.count()} chunks.")
    return len(chunks)


def retrieve_context(query: str, top_k: int = TOP_K_RESULTS) -> list:
    """
    Retrieve top-k relevant chunks. Returns empty list if ChromaDB unavailable.
    The agent.py falls back to inline text in that case.
    """
    if not _is_chroma_available():
        return []

    try:
        collection = _get_collection()
        if collection.count() == 0:
            return []

        model     = _get_embedding_model()
        query_emb = model.encode([query], show_progress_bar=False).tolist()

        results = collection.query(
            query_embeddings=query_emb,
            n_results=min(top_k, collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        retrieved = []
        for rank, (doc, meta, dist) in enumerate(zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        )):
            retrieved.append({
                "rank":        rank + 1,
                "text":        doc,
                "source":      meta.get("source", "handbook"),
                "chunk_index": meta.get("chunk_index", -1),
                "distance":    round(dist, 4),
            })
        return retrieved

    except Exception as e:
        print(f"[VectorStore] retrieve_context failed: {e}")
        return []


def build_rag_context_string(chunks: list) -> str:
    if not chunks:
        return ""
    parts = []
    for c in chunks:
        parts.append(
            f"[Source: {c['source'].upper()} | Chunk #{c['chunk_index']}]\n"
            f"{c['text']}"
        )
    return "\n\n---\n\n".join(parts)


def get_collection_stats() -> dict:
    if not _is_chroma_available():
        return {
            "collection_name": COLLECTION_NAME,
            "total_chunks":    0,
            "embedding_model": EMBEDDING_MODEL,
            "status":          "ChromaDB not available",
        }
    try:
        collection = _get_collection()
        return {
            "collection_name": COLLECTION_NAME,
            "total_chunks":    collection.count(),
            "embedding_model": EMBEDDING_MODEL,
            "chunk_size":      CHUNK_SIZE,
            "chunk_overlap":   CHUNK_OVERLAP,
        }
    except Exception as e:
        return {"error": str(e)}


def load_handbook(filepath: Optional[str] = None) -> str:
    if filepath and os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
        print(f"[VectorStore] Loaded handbook from file: {filepath}")
        return text
    else:
        print("[VectorStore] Using inline handbook text.")
        return HANDBOOK_INLINE_TEXT


def initialize_vector_store(handbook_path: Optional[str] = None) -> dict:
    # Skip embedding ingestion on startup to avoid hanging on MPS/CPU encoding.
    # RAG agent uses HANDBOOK_INLINE_TEXT fallback when collection is empty.
    # Trigger ingestion manually via POST /vector-store/reingest after server starts.
    return {"total_chunks": 0, "chunks_added_this_run": 0, "status": "skipped"}


# ─────────────────────────────────────────────────────────────
# Inline Handbook Fallback Text
# ─────────────────────────────────────────────────────────────
HANDBOOK_INLINE_TEXT = """
## Student Handbook 2023 Onwards — Institute of Management Sciences Peshawar

## CHAPTER 1: SEMESTER RULES

3. ACADEMIC YEAR: The academic year comprises two regular semesters and an optional summer semester.
Fall semester: August/September to January.
Spring semester: January/February to May/June.
Summer semester: 8 weeks duration, June to August.

4. DURATION OF SEMESTER: Each semester is 18 weeks; 16 weeks teaching, 2 weeks examinations.
There shall be a Semester Break of 1 week after every semester.
Two exams per semester: Mid Term (week 9) and Final Term (week 18).

9. ATTENDANCE: Every student must maintain at least 80% attendance in each course.
Students failing minimum attendance cannot take the final examination.
Absence below 80% results in grade 'XF' (Fail due to attendance shortage).
XF can only be cleared by repeating the course.
XF is not counted in GPA/CGPA calculation.

10. CHANGE OF COURSE: A student may change elective courses within 14 days of semester commencement.

11. CHANGE OF PROGRAM: Allowed within 14 days of semester commencement, subject to seat availability.

12. REPEATING COURSES: If a student fails or has attendance shortage, they must re-register and repeat the course.

13. IMPROVEMENT OF GRADES: A student may improve grades of C or C+ once per course, upon payment of prescribed fees.
If the improved grade is lower, the previous grade is retained.

15. SEMESTER FREEZING: Allowed under Force Majeure conditions.
Cannot be done in the first semester.
Students on probation are not eligible for semester freezing.
Freeze semester counts toward degree duration.
No fees charged if application submitted before mid-term exams.

17. TRANSFER OF CREDIT HOURS: Not allowed under any circumstances.

18. GPA REQUIREMENT / PROBATION:
Minimum CGPA of 2.2 must be maintained.
CGPA below 2.0: student is dropped from rolls immediately.
CGPA between 2.0 and 2.2: student placed on probation for one semester.
If probation student does not improve to 2.2, studies are detained.
One-time detention is applicable after the 2nd semester.
After detention, if CGPA still below 2.2, student is dropped out.

20. DEGREE PROGRAMMES AND DURATIONS:
Bachelors: 4 years minimum, 7 years maximum, 130-136 credit hours.
MBA 2.5 years: minimum 2.5 years, maximum 5 years, 66 credit hours.
MSc Computer Science: 2 years minimum, 4 years maximum, 72 credit hours.
MS programs: 1.5 years minimum, 4 years maximum, 30 credit hours.
PhD: 3 years minimum, 8 years maximum, 54 credit hours.

21. COURSE LOAD:
Undergraduate: 15-18 credit hours per semester. Minimum 15 for full-time status.
MS/MPhil: 9-12 credit hours per semester.

22. GRADING SYSTEM:
A+ : 91-100% → 4.0 Grade Points (Outstanding)
A  : 87-90%  → 4.0 Grade Points (Excellent)
B+ : 80-86%  → 3.5 Grade Points (Very Good)
B  : 72-79%  → 3.0 Grade Points (Good)
C+ : 66-71%  → 2.5 Grade Points (Satisfactory)
C  : 60-65%  → 2.0 Grade Points (Pass)
F  : Below 60% → 0 Grade Points (Fail)

23. EVALUATION WEIGHTAGE:
Quizzes/Presentations/Assignments: 20%
Mid-Term Examination: 30%
Final Examination: 50%

25-26. CGPA FOR DEGREE AWARD:
BBA/BS/BCS/MBA/MSc: Minimum CGPA of 2.2 required.
MS degree: Minimum CGPA of 2.5 required.
PhD: Minimum CGPA of 3.0 to continue research; 2.5 to pass a course.

27. MAKE-UP EXAMINATION: No make-up for attendance shortage or course failure.
Make-up allowed for: serious illness/hospitalization, road accident, terrorism, death of parent/spouse/child/sibling.
Medical certificate and documentation required.

32. RETOTALING: Appeal must be lodged within 7 days after resumption of classes.
There shall be no re-evaluation of answer books.

35. UNFAIR MEANS (UFM): Prohibited acts include receiving/giving assistance, copying, impersonation.
Penalties: financial penalty, cancellation of paper, cancellation of semester papers, expulsion.

37. GOLD MEDAL / DISTINCTION:
1st position: Gold Medal with Distinction Certificate.
2nd position: Silver Medal with Distinction Certificate.
Minimum CGPA of 3.5 required. No grade below B in any course.
No failed or repeated courses. Degree completed within 6 months of first result notification.
Students who improved grades are not eligible.

41. FEE DEPOSIT: Fees charged as lump sum per semester.
Fine charged for late payment; result withheld.
After 4 months non-payment, enrollment automatically cancelled.
50% tuition fee concession for siblings studying at IMSciences.

42. FEE REFUND POLICY:
Up to 7th day of classes: 100% refund.
Up to 14th day of classes: 50% refund.
After 14 days: only security refunded.

43. STUDENTS GRIEVANCES COMMITTEE (SGC):
Student must submit grievance in writing to Program Coordinator within 7 working days of grade notification.
SGC gives final decision within 5 working days.
Student may appeal to Semester Committee within 5 working days of SGC decision.

## CHAPTER 2: ADMISSION POLICY

BBA / BS Accounting & Finance / BS Economics / BS Social Sciences:
Eligibility: FA/FSc or equivalent, minimum 45% marks.
Merit: 50% HSSC marks, 40% written test, 10% interview.
Minimum 40% in test and interview required.
Program duration: 4 years, 8 semesters, 130-136 credit hours.

BCS / BSSE / BS Data Sciences:
Eligibility: FA/FSc or equivalent, minimum 50% marks.
Students without Mathematics must complete 6 credit hour deficiency courses within one year.
Merit: 50% HSSC, 40% test, 10% interview.

MBA:
Eligibility: 16 years of education, minimum 2.5 CGPA or 45% marks.
Business graduates: qualifying Institute test or HEC-required test with minimum 40% marks.
Non-business graduates: ETS-GRE or NTS-GAT General required.
IMSciences own graduates exempted from test and interview requirement.
Duration: 2 years minimum, 4 semesters.

PhD:
Eligibility: BS/MS/MPhil with minimum CGPA of 3.0 or First Division.
Admission test: GRE (60%), NTS-GAT General (60%), or Institute's own test (70%).
Duration: 3 years minimum, 8 years maximum.

Hafiz Quran: special credit of 20 marks added to HSSC marks.

## CHAPTER 3: LIBRARY RULES

Library has 10,000+ books. HEC Digital Library: approximately 7 million books.
Library timings: 08:00 am to 08:00 pm on all working days.
Fine for late return: Rs. 5/- per day per book.
Lost book penalty: up to 3 times original price.
Prohibited in library: smoking, food/drinks, mobile phones, noise.

## CHAPTER 4: TRANSPORT FACILITY

Institute provides subsidized transport for local day scholars.
Female students given priority.

## CHAPTER 5: STUDENTS CONDUCT & DISCIPLINE RULES

Prohibited acts include smoking, alcohol/drugs, weapons, strike/walkout, political activities.
Penalties range from classroom removal and fines up to Rs. 5000, to rustication and expulsion.
Expulsion: up to 24 months; beyond 24 months requires Director approval.
Appeals must be filed within 15 days of penalty notification.

## CHAPTER 6: HOSTEL RULES

Hostel Rent (2025-26): Rs. 55,100/- per year (1st year), Rs. 54,000/- subsequent years.
Mess charges: Rs. 7,500/- per month.
Hostel fee refund: 100% within 7 days, 50% from days 8-15, 0% after 16th day.
No weapons, alcohol, or intoxicants allowed. Smoking strictly prohibited.

## CHAPTER 7: SCHOLARSHIPS AND FINANCIAL AID

IMSciences offers multiple scholarship programs:
1. PAK-USAID Fully Funded Need Based Merit Scholarships for BBA, BS, MBA.
2. IMSciences FATA Scholarship Program (13 scholarships).
3. Chief Minister Education Endowment Fund (full tuition + Rs. 5000/month).
4. NTS Need Based Merit Scholarship (full tuition + Rs. 5000/month).
5. HEC-French Need Based Merit Scholarship (Rs. 50,000/year for 4 years).
6. HEC Need Based Merit Scholarship (full tuition + monthly stipend).
7. Prime Minister's Tuition Fee Reimbursement for students from less developed areas.
8. IMSciences Merit Based Partial Scholarships: 10% of students per program, 65-75% fee relaxation.
9. IMSciences Trust Semester-Wise Merit Scholarships: based on highest GPA each semester.
10. Dr. Hidayatullah Need Based Merit Scholarships.
11. IMSciences Brother-Sister Fee Rebate: 50% fee rebate if sibling also studies at IMSciences.
12. Workers Welfare Board KPK Scholarship: for children of registered industrial labor employees.
13. National Bank of Pakistan Student Loan Scheme: interest-free loans for meritorious, needy students.
"""