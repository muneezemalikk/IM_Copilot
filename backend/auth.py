"""
auth.py — Login system for IM|Copilot.
Roles: student, admin
Passwords stored as SHA-256 hashes.
"""

import hashlib
from database import get_connection


DEFAULT_USERS = [
    # (username,  password,     role,      student_id)
    ("S001",  "ali123",     "student", "S001"),
    ("S002",  "fatima123",  "student", "S002"),
    ("S003",  "ahmed123",   "student", "S003"),
    ("S004",  "zara123",    "student", "S004"),
    ("S005",  "bilal123",   "student", "S005"),
    ("S006",  "hira123",    "student", "S006"),
    ("S007",  "usman123",   "student", "S007"),
    ("S008",  "sana123",    "student", "S008"),
    ("S009",  "hamza123",   "student", "S009"),
    ("S010",  "ayesha123",  "student", "S010"),
    ("admin", "admin123",   "admin",   None),
]


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def initialize_auth():
    """Create users table and seed default accounts if empty."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username   TEXT PRIMARY KEY,
            password   TEXT NOT NULL,
            role       TEXT NOT NULL DEFAULT 'student',
            student_id TEXT
        )
    """)
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        for username, password, role, sid in DEFAULT_USERS:
            cur.execute(
                "INSERT OR IGNORE INTO users VALUES (?, ?, ?, ?)",
                (username, _hash(password), role, sid)
            )
    conn.commit()
    conn.close()


def login(username: str, password: str) -> dict | None:
    """
    Returns { username, role, student_id } on success, None on failure.
    """
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        "SELECT username, role, student_id FROM users WHERE username = ? AND password = ?",
        (username.strip(), _hash(password.strip()))
    )
    row = cur.fetchone()
    conn.close()
    if row:
        return {
            "username":   row["username"],
            "role":       row["role"],
            "student_id": row["student_id"],
        }
    return None