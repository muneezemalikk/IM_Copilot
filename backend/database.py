"""
database.py — SQLite setup, schema definition, and dummy data generation.
Simulates a university student information system (SIS).
"""

import sqlite3
import os
import random
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "imcopilot.db")

# ─────────────────────────────────────────────────────────────
# SCHEMA (injected into LLM system prompt for Zero-Shot SQL)
# ─────────────────────────────────────────────────────────────
DB_SCHEMA = """
DATABASE SCHEMA (SQLite):

TABLE: students
  - student_id       TEXT PRIMARY KEY   (e.g., 'S001')
  - name             TEXT               (full name)
  - program          TEXT               (e.g., 'BBA', 'BCS', 'MBA')
  - semester         INTEGER            (current semester number, 1–8)
  - cgpa             REAL               (cumulative GPA on 4.0 scale)
  - email            TEXT
  - enrollment_year  INTEGER

TABLE: courses
  - course_id        TEXT PRIMARY KEY   (e.g., 'CS301')
  - course_name      TEXT
  - credit_hours     INTEGER
  - program          TEXT               (program this course belongs to)
  - semester         INTEGER            (semester in which it is offered)

TABLE: enrollments
  - enrollment_id    INTEGER PRIMARY KEY AUTOINCREMENT
  - student_id       TEXT               (FK → students.student_id)
  - course_id        TEXT               (FK → courses.course_id)
  - semester_label   TEXT               (e.g., 'Fall 2024')
  - status           TEXT               ('active', 'completed', 'dropped')

TABLE: grades
  - grade_id         INTEGER PRIMARY KEY AUTOINCREMENT
  - student_id       TEXT               (FK → students.student_id)
  - course_id        TEXT               (FK → courses.course_id)
  - semester_label   TEXT
  - midterm_marks    REAL               (out of 30)
  - final_marks      REAL               (out of 50)
  - assignment_marks REAL               (out of 20)
  - total_marks      REAL               (computed: sum of above, out of 100)
  - letter_grade     TEXT               (A+, A, B+, B, C+, C, F)
  - grade_points     REAL               (4.0 scale)

TABLE: attendance
  - attendance_id    INTEGER PRIMARY KEY AUTOINCREMENT
  - student_id       TEXT               (FK → students.student_id)
  - course_id        TEXT               (FK → courses.course_id)
  - semester_label   TEXT
  - total_classes    INTEGER
  - attended_classes INTEGER
  - attendance_pct   REAL               (percentage, e.g., 85.5)
  - status           TEXT               ('OK', 'Warning', 'XF Risk')

RELATIONSHIPS:
  enrollments.student_id → students.student_id
  enrollments.course_id  → courses.course_id
  grades.student_id      → students.student_id
  grades.course_id       → courses.course_id
  attendance.student_id  → students.student_id
  attendance.course_id   → courses.course_id

NOTES:
  - Minimum attendance required: 80%. Below 80% = 'XF Risk'.
  - Passing grade: C (60%). Below 60% = F (grade_points = 0).
  - GPA scale: A+(4.0), A(4.0), B+(3.5), B(3.0), C+(2.5), C(2.0), F(0.0)
  - Probation: CGPA between 2.0 and 2.2. Drop: CGPA below 2.0.
"""


def get_schema() -> str:
    """Returns the schema string for injection into LLM system prompts."""
    return DB_SCHEMA


def get_connection() -> sqlite3.Connection:
    """Returns a SQLite connection with row factory for dict-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _letter_grade(total: float) -> tuple[str, float]:
    """Convert total marks (0–100) to letter grade and grade points."""
    if total >= 91:
        return "A+", 4.0
    elif total >= 87:
        return "A", 4.0
    elif total >= 80:
        return "B+", 3.5
    elif total >= 72:
        return "B", 3.0
    elif total >= 66:
        return "C+", 2.5
    elif total >= 60:
        return "C", 2.0
    else:
        return "F", 0.0


def initialize_database():
    """Creates tables and populates with realistic dummy data if not exists."""
    conn = get_connection()
    cur = conn.cursor()

    # ── Create Tables ──────────────────────────────────────────
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            student_id      TEXT PRIMARY KEY,
            name            TEXT NOT NULL,
            program         TEXT NOT NULL,
            semester        INTEGER NOT NULL,
            cgpa            REAL NOT NULL,
            email           TEXT,
            enrollment_year INTEGER
        );

        CREATE TABLE IF NOT EXISTS courses (
            course_id    TEXT PRIMARY KEY,
            course_name  TEXT NOT NULL,
            credit_hours INTEGER NOT NULL,
            program      TEXT NOT NULL,
            semester     INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS enrollments (
            enrollment_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id     TEXT NOT NULL,
            course_id      TEXT NOT NULL,
            semester_label TEXT NOT NULL,
            status         TEXT DEFAULT 'active'
        );

        CREATE TABLE IF NOT EXISTS grades (
            grade_id        INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id      TEXT NOT NULL,
            course_id       TEXT NOT NULL,
            semester_label  TEXT NOT NULL,
            midterm_marks   REAL,
            final_marks     REAL,
            assignment_marks REAL,
            total_marks     REAL,
            letter_grade    TEXT,
            grade_points    REAL
        );

        CREATE TABLE IF NOT EXISTS attendance (
            attendance_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id      TEXT NOT NULL,
            course_id       TEXT NOT NULL,
            semester_label  TEXT NOT NULL,
            total_classes   INTEGER,
            attended_classes INTEGER,
            attendance_pct  REAL,
            status          TEXT
        );
    """)

    # ── Check if data already exists ───────────────────────────
    cur.execute("SELECT COUNT(*) FROM students")
    if cur.fetchone()[0] > 0:
        conn.close()
        return  # Already initialized

    # ── Seed Courses ───────────────────────────────────────────
    courses = [
        # BBA Courses
        ("BBA101", "Principles of Management",      3, "BBA", 1),
        ("BBA102", "Business Mathematics",          3, "BBA", 1),
        ("BBA103", "Introduction to Economics",     3, "BBA", 1),
        ("BBA104", "Business Communication",        3, "BBA", 1),
        ("BBA201", "Financial Accounting",          3, "BBA", 2),
        ("BBA202", "Marketing Management",          3, "BBA", 2),
        ("BBA203", "Organizational Behavior",       3, "BBA", 2),
        ("BBA301", "Business Finance",              3, "BBA", 3),
        ("BBA302", "Human Resource Management",     3, "BBA", 3),
        ("BBA303", "Operations Management",         3, "BBA", 3),
        # BCS Courses
        ("CS101",  "Programming Fundamentals",      4, "BCS", 1),
        ("CS102",  "Discrete Mathematics",          3, "BCS", 1),
        ("CS103",  "Digital Logic Design",          3, "BCS", 1),
        ("CS201",  "Data Structures & Algorithms",  4, "BCS", 2),
        ("CS202",  "Object Oriented Programming",   4, "BCS", 2),
        ("CS203",  "Database Systems",              3, "BCS", 2),
        ("CS301",  "Operating Systems",             3, "BCS", 3),
        ("CS302",  "Computer Networks",             3, "BCS", 3),
        ("CS303",  "Software Engineering",          3, "BCS", 3),
        # MBA Courses
        ("MBA101", "Managerial Economics",          3, "MBA", 1),
        ("MBA102", "Corporate Finance",             3, "MBA", 1),
        ("MBA103", "Strategic Management",          3, "MBA", 1),
        ("MBA201", "Business Research Methods",     3, "MBA", 2),
        ("MBA202", "Project Management",            3, "MBA", 2),
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO courses VALUES (?,?,?,?,?)", courses
    )

    # ── Seed Students ──────────────────────────────────────────
    students_raw = [
        ("S001", "Ali Hassan",        "BCS", 3, "ali.hassan@imsciences.edu.pk",    2022),
        ("S002", "Fatima Malik",      "BBA", 2, "fatima.malik@imsciences.edu.pk",  2023),
        ("S003", "Ahmed Khan",        "MBA", 1, "ahmed.khan@imsciences.edu.pk",    2024),
        ("S004", "Zara Qureshi",      "BCS", 2, "zara.qureshi@imsciences.edu.pk",  2023),
        ("S005", "Bilal Afridi",      "BBA", 3, "bilal.afridi@imsciences.edu.pk",  2022),
        ("S006", "Hira Baig",         "BCS", 1, "hira.baig@imsciences.edu.pk",     2024),
        ("S007", "Usman Tariq",       "MBA", 2, "usman.tariq@imsciences.edu.pk",   2023),
        ("S008", "Sana Rehman",       "BBA", 1, "sana.rehman@imsciences.edu.pk",   2024),
        ("S009", "Hamza Yousaf",      "BCS", 3, "hamza.yousaf@imsciences.edu.pk",  2022),
        ("S010", "Ayesha Noor",       "BBA", 2, "ayesha.noor@imsciences.edu.pk",   2023),
    ]

    semester_labels = {1: "Fall 2024", 2: "Fall 2024", 3: "Spring 2024"}

    random.seed(42)  # Reproducible dummy data

    for sid, name, program, sem, email, yr in students_raw:
        # Select courses for this student's program and semester
        student_courses = [
            c for c in courses if c[3] == program and c[4] <= sem
        ]
        # Take current semester courses (last semester courses)
        current_courses = [c for c in courses if c[3] == program and c[4] == sem]
        sem_label = semester_labels.get(sem, "Spring 2024")

        # Generate grades for current semester
        gpa_points = []
        for course in current_courses:
            cid = course[0]
            mid    = round(random.uniform(15, 28), 1)   # out of 30
            final  = round(random.uniform(28, 48), 1)   # out of 50
            assign = round(random.uniform(12, 19), 1)   # out of 20
            total  = round(mid + final + assign, 1)
            lg, gp = _letter_grade(total)

            gpa_points.append((gp, course[2]))  # (grade_point, credit_hours)

            cur.execute(
                """INSERT INTO enrollments (student_id, course_id, semester_label, status)
                   VALUES (?,?,?,'active')""",
                (sid, cid, sem_label)
            )
            cur.execute(
                """INSERT INTO grades
                   (student_id, course_id, semester_label,
                    midterm_marks, final_marks, assignment_marks,
                    total_marks, letter_grade, grade_points)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (sid, cid, sem_label, mid, final, assign, total, lg, gp)
            )

            # Attendance (some students at risk)
            total_cls = 32
            if sid in ("S005", "S009"):  # Purposely low attendance
                attended = random.randint(22, 25)
            else:
                attended = random.randint(26, 32)
            pct = round((attended / total_cls) * 100, 1)
            if pct >= 80:
                att_status = "OK"
            elif pct >= 75:
                att_status = "Warning"
            else:
                att_status = "XF Risk"

            cur.execute(
                """INSERT INTO attendance
                   (student_id, course_id, semester_label,
                    total_classes, attended_classes, attendance_pct, status)
                   VALUES (?,?,?,?,?,?,?)""",
                (sid, cid, sem_label, total_cls, attended, pct, att_status)
            )

        # Compute CGPA (weighted average)
        if gpa_points:
            total_weighted = sum(gp * ch for gp, ch in gpa_points)
            total_credits  = sum(ch for _, ch in gpa_points)
            cgpa = round(total_weighted / total_credits, 2)
        else:
            cgpa = 0.0

        cur.execute(
            """INSERT INTO students
               (student_id, name, program, semester, cgpa, email, enrollment_year)
               VALUES (?,?,?,?,?,?,?)""",
            (sid, name, program, sem, cgpa, email, yr)
        )

    conn.commit()
    conn.close()
    print(f"[DB] Database initialized at: {DB_PATH}")


def execute_read_query(sql: str) -> list[dict]:
    """
    Safely executes a READ-ONLY SQL query.
    Raises ValueError if a mutating statement is detected.
    Returns a list of row dicts.
    """
    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE"]
    sql_upper = sql.strip().upper()
    for keyword in forbidden:
        if keyword in sql_upper:
            raise ValueError(
                f"[SECURITY] Mutating SQL keyword '{keyword}' is not permitted."
            )

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_student_dashboard(student_id: str) -> dict:
    """
    Returns a comprehensive dashboard payload for a given student.
    Used by the /dashboard/{student_id} endpoint.
    """
    conn = get_connection()
    cur  = conn.cursor()

    # Basic info
    cur.execute("SELECT * FROM students WHERE student_id = ?", (student_id,))
    student = cur.fetchone()
    if not student:
        conn.close()
        return {}

    student = dict(student)

    # Current semester label (most recent)
    cur.execute(
        """SELECT semester_label FROM enrollments
           WHERE student_id = ? ORDER BY enrollment_id DESC LIMIT 1""",
        (student_id,)
    )
    row = cur.fetchone()
    sem_label = row["semester_label"] if row else "N/A"

    # Grades for current semester
    cur.execute(
        """SELECT g.course_id, c.course_name, c.credit_hours,
                  g.midterm_marks, g.final_marks, g.assignment_marks,
                  g.total_marks, g.letter_grade, g.grade_points
           FROM grades g
           JOIN courses c ON g.course_id = c.course_id
           WHERE g.student_id = ? AND g.semester_label = ?""",
        (student_id, sem_label)
    )
    grades = [dict(r) for r in cur.fetchall()]

    # Attendance for current semester
    cur.execute(
        """SELECT a.course_id, c.course_name,
                  a.total_classes, a.attended_classes,
                  a.attendance_pct, a.status
           FROM attendance a
           JOIN courses c ON a.course_id = c.course_id
           WHERE a.student_id = ? AND a.semester_label = ?""",
        (student_id, sem_label)
    )
    attendance = [dict(r) for r in cur.fetchall()]

    conn.close()

    # Aggregate stats
    avg_attendance = (
        round(sum(a["attendance_pct"] for a in attendance) / len(attendance), 1)
        if attendance else 0.0
    )
    at_risk_courses = [a for a in attendance if a["status"] == "XF Risk"]

    return {
        "student":         student,
        "semester_label":  sem_label,
        "grades":          grades,
        "attendance":      attendance,
        "avg_attendance":  avg_attendance,
        "at_risk_courses": at_risk_courses,
        "total_courses":   len(grades),
    }


if __name__ == "__main__":
    initialize_database()
    # Quick sanity check
    rows = execute_read_query(
        "SELECT student_id, name, program, semester, cgpa FROM students"
    )
    print("\n── Students ──")
    for r in rows:
        print(r)
