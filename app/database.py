import json
import sqlite3
from contextlib import contextmanager

try:
    from src.common import data_path
except ImportError:
    from src.common import data_path

# Database file lives in the writable app data directory.
DB_PATH = data_path("ars.db")

def get_connection():
    """Return a new SQLite connection with row_factory for dict-like access."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn

@contextmanager
def db_session():
    """Context manager for SQLite database transactions with auto-commit/rollback and automatic cleanup."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    """Create tables and indexes if they don't already exist. Safe to call on every app start."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            run_type   TEXT NOT NULL,
            run_date   TEXT NOT NULL DEFAULT (date('now')),
            run_ts     TEXT NOT NULL DEFAULT (datetime('now')),
            status     TEXT DEFAULT 'RUNNING',
            metadata   TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS candidates (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id       INTEGER NOT NULL REFERENCES pipeline_runs(id),
            name         TEXT NOT NULL,
            email        TEXT DEFAULT '',
            source_file  TEXT DEFAULT '',
            score        REAL DEFAULT 0,
            skills       TEXT DEFAULT '[]',
            created_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS schedules (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id         INTEGER NOT NULL REFERENCES pipeline_runs(id),
            candidate_name TEXT NOT NULL,
            job_title      TEXT DEFAULT '',
            rank           INTEGER DEFAULT 0,
            score          REAL DEFAULT 0,
            offered_slots  TEXT DEFAULT '[]',
            selected_slot  TEXT DEFAULT '',
            status         TEXT DEFAULT 'PENDING',
            email_sent     INTEGER DEFAULT 0,
            created_at     TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS email_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id        INTEGER REFERENCES pipeline_runs(id),
            schedule_id   INTEGER REFERENCES schedules(id),
            recipient     TEXT NOT NULL,
            subject       TEXT DEFAULT '',
            status        TEXT DEFAULT 'SENT',
            error         TEXT DEFAULT '',
            sent_at       TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS interview_tokens (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            token           TEXT NOT NULL UNIQUE,
            candidate_name  TEXT NOT NULL,
            source_file     TEXT NOT NULL,
            job_title       TEXT DEFAULT '',
            rank            INTEGER DEFAULT 0,
            score           REAL DEFAULT 0,
            used            INTEGER DEFAULT 0,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS job_templates (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            jd_text     TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        -- ── Auth: HR users ──────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS hr_users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role          TEXT NOT NULL DEFAULT 'hr',
            created_at    TEXT DEFAULT (datetime('now'))
        );

        -- ── Auth: Server-side JWT session records ────────────────────────────
        CREATE TABLE IF NOT EXISTS hr_sessions (
            jti        TEXT PRIMARY KEY,
            user_id    INTEGER NOT NULL,
            username   TEXT NOT NULL,
            role       TEXT NOT NULL,
            issued_at  TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at TEXT NOT NULL,
            revoked    INTEGER NOT NULL DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_candidates_run_id ON candidates(run_id);
        CREATE INDEX IF NOT EXISTS idx_schedules_run_id ON schedules(run_id);
        CREATE INDEX IF NOT EXISTS idx_schedules_status ON schedules(status);
        CREATE INDEX IF NOT EXISTS idx_interview_tokens_token ON interview_tokens(token);
        CREATE INDEX IF NOT EXISTS idx_hr_sessions_user ON hr_sessions(user_id);
    """)
    conn.commit()

    # ── Migration: rebuild hr_sessions without FK if old schema present ───────
    # The first deployment created hr_sessions with REFERENCES hr_users(id).
    # SQLite cannot ALTER TABLE to drop constraints, so we recreate the table.
    tbl_sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='hr_sessions'"
    ).fetchone()
    if tbl_sql and "REFERENCES" in (tbl_sql[0] or ""):
        conn.executescript("""
            PRAGMA foreign_keys = OFF;
            BEGIN;
            ALTER TABLE hr_sessions RENAME TO _hr_sessions_old;
            CREATE TABLE hr_sessions (
                jti        TEXT PRIMARY KEY,
                user_id    INTEGER NOT NULL,
                username   TEXT NOT NULL,
                role       TEXT NOT NULL,
                issued_at  TEXT NOT NULL DEFAULT (datetime('now')),
                expires_at TEXT NOT NULL,
                revoked    INTEGER NOT NULL DEFAULT 0
            );
            INSERT INTO hr_sessions SELECT jti, user_id, username, role,
                issued_at, expires_at, revoked FROM _hr_sessions_old;
            DROP TABLE _hr_sessions_old;
            COMMIT;
            PRAGMA foreign_keys = ON;
        """)
        print("[DB] Migration: hr_sessions FK constraint removed.")

    conn.close()
    print("[DB] Database initialised:", DB_PATH)

    # Ensure GDPR tables and consent columns exist
    from app.gdpr import ensure_gdpr_schema
    ensure_gdpr_schema()


# ─── Pipeline run helpers ───

def create_run(run_type, metadata=None):
    """Create a new pipeline run and return its id. run_type: 'nlp', 'ranking', 'scheduling', 'email'."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO pipeline_runs (run_type, metadata) VALUES (?, ?)",
            (run_type, json.dumps(metadata or {})),
        )
        run_id = cur.lastrowid
        conn.commit()
        return run_id
    finally:
        conn.close()

def finish_run(run_id, status="COMPLETED", metadata=None):
    """Mark a pipeline run as completed/failed and optionally update metadata."""
    conn = get_connection()
    try:
        if metadata is not None:
            conn.execute(
                "UPDATE pipeline_runs SET status=?, metadata=? WHERE id=?",
                (status, json.dumps(metadata), run_id),
            )
        else:
            conn.execute("UPDATE pipeline_runs SET status=? WHERE id=?", (status, run_id))
        conn.commit()
    finally:
        conn.close()

def get_runs(run_type=None, limit=20):
    """Return recent pipeline runs, optionally filtered by type."""
    conn = get_connection()
    try:
        if run_type:
            rows = conn.execute(
                "SELECT * FROM pipeline_runs WHERE run_type=? ORDER BY id DESC LIMIT ?",
                (run_type, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

# ─── Candidate helpers ───

def upsert_candidate(run_id, name, email="", source_file="", score=0, skills=None):
    """Insert or update a candidate within a run. Returns the candidate id."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "SELECT id FROM candidates WHERE run_id=? AND name=?", (run_id, name)
        )
        row = cur.fetchone()
        skills_json = json.dumps(skills or [])
        if row:
            conn.execute(
                "UPDATE candidates SET email=?, source_file=?, score=?, skills=? WHERE id=?",
                (email, source_file, score, skills_json, row["id"]),
            )
            cid = row["id"]
        else:
            cur = conn.execute(
                "INSERT INTO candidates (run_id, name, email, source_file, score, skills) VALUES (?,?,?,?,?,?)",
                (run_id, name, email, source_file, score, skills_json),
            )
            cid = cur.lastrowid
        conn.commit()
        return cid
    finally:
        conn.close()

def get_candidate_by_name(name, run_id=None):
    """Return candidate row or None. If run_id given, scoped to that run."""
    conn = get_connection()
    try:
        if run_id:
            row = conn.execute(
                "SELECT * FROM candidates WHERE name=? AND run_id=?", (name, run_id)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM candidates WHERE name=? ORDER BY id DESC LIMIT 1", (name,)
            ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_all_candidates(run_id=None):
    """Return candidates as a list of dicts. If run_id given, scoped to that run."""
    conn = get_connection()
    try:
        if run_id:
            rows = conn.execute(
                "SELECT * FROM candidates WHERE run_id=? ORDER BY score DESC", (run_id,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM candidates ORDER BY score DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

# ─── Schedule helpers ───

def save_schedule(run_id, entries, job_title):
    """Bulk-save a list of scheduled entries under a run. Returns list of schedule ids."""
    conn = get_connection()
    try:
        ids = []
        for e in entries:
            cur = conn.execute(
                """INSERT INTO schedules
                   (run_id, candidate_name, job_title, rank, score, offered_slots, selected_slot, status)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    run_id,
                    e.get("candidate_name", ""),
                    job_title,
                    e.get("rank", 0),
                    e.get("score", 0),
                    json.dumps(e.get("offered_slots", [])),
                    e.get("selected_slot", ""),
                    e.get("status", "PENDING"),
                ),
            )
            ids.append(cur.lastrowid)
        conn.commit()
        return ids
    finally:
        conn.close()

def get_latest_schedule(run_id=None):
    """Return the most recent batch of scheduled entries."""
    conn = get_connection()
    try:
        if run_id:
            rows = conn.execute(
                "SELECT * FROM schedules WHERE run_id=? ORDER BY rank", (run_id,)
            ).fetchall()
        else:
            row = conn.execute("SELECT run_id FROM schedules ORDER BY id DESC LIMIT 1").fetchone()
            if not row:
                return []
            rows = conn.execute(
                "SELECT * FROM schedules WHERE run_id=? ORDER BY rank", (row["run_id"],)
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_confirmed_not_emailed(run_id=None):
    """Return confirmed schedule entries that haven't been emailed yet."""
    conn = get_connection()
    try:
        if run_id:
            rows = conn.execute(
                "SELECT * FROM schedules WHERE run_id=? AND status='CONFIRMED' AND email_sent=0 ORDER BY rank",
                (run_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM schedules WHERE status='CONFIRMED' AND email_sent=0 ORDER BY rank"
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def mark_email_sent(schedule_id):
    """Mark a schedule entry as emailed."""
    conn = get_connection()
    try:
        conn.execute("UPDATE schedules SET email_sent=1 WHERE id=?", (schedule_id,))
        conn.commit()
    finally:
        conn.close()

def log_email(run_id, schedule_id, recipient, subject, status="SENT", error=""):
    """Log an email send attempt."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO email_log (run_id, schedule_id, recipient, subject, status, error) VALUES (?,?,?,?,?,?)",
            (run_id, schedule_id, recipient, subject, status, error),
        )
        conn.commit()
    finally:
        conn.close()

def update_schedule_slot(candidate_name, selected_slot):
    """Update the selected slot for the most recent schedule entry matching this candidate."""
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE schedules SET selected_slot=?, status='CONFIRMED'
               WHERE id = (
                   SELECT id FROM schedules WHERE candidate_name=? ORDER BY id DESC LIMIT 1
               )""",
            (selected_slot, candidate_name),
        )
        conn.commit()
    finally:
        conn.close()

# ─── Interview token helpers ───

def create_interview_token(token, candidate_name, source_file, job_title="", rank=0, score=0):
    """Create a unique interview token for a candidate. Returns the token string."""
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO interview_tokens (token, candidate_name, source_file, job_title, rank, score)
               VALUES (?,?,?,?,?,?)""",
            (token, candidate_name, source_file, job_title, rank, score),
        )
        conn.commit()
        return token
    finally:
        conn.close()

def get_interview_token(token):
    """Look up a token. Returns dict or None."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM interview_tokens WHERE token=?", (token,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def mark_token_used(token):
    """Mark a token as used after the interview finishes."""
    conn = get_connection()
    try:
        conn.execute("UPDATE interview_tokens SET used=1 WHERE token=?", (token,))
        conn.commit()
    finally:
        conn.close()

def get_all_tokens():
    """Return all interview tokens as list of dicts."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM interview_tokens ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def delete_all_tokens():
    """Delete all interview tokens (for regeneration)."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM interview_tokens")
        conn.commit()
    finally:
        conn.close()


# ─── Job Template Helpers ───

def save_job_template(title: str, jd_text: str) -> int:
    """Save a new job description template. Returns the template ID."""
    with db_session() as conn:
        cur = conn.execute(
            "INSERT INTO job_templates (title, jd_text) VALUES (?, ?)",
            (title.strip(), jd_text.strip()),
        )
        return cur.lastrowid


def get_all_job_templates() -> list:
    """Return all job templates as a list of dicts ordered by newest first."""
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM job_templates ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]


def delete_job_template(template_id: int) -> bool:
    """Delete a job template by ID."""
    with db_session() as conn:
        conn.execute("DELETE FROM job_templates WHERE id=?", (template_id,))
        return True


# ─── Auth: HR Users ───────────────────────────────────────────────────────────

def get_user_by_username(username: str) -> dict | None:
    """Return hr_users row as dict, or None if not found."""
    with db_session() as conn:
        row = conn.execute(
            "SELECT * FROM hr_users WHERE username=?", (username,)
        ).fetchone()
        return dict(row) if row else None


def upsert_hr_admin(username: str, password_hash: str, role: str = "admin") -> int:
    """Insert or update the built-in admin user. Returns user id."""
    with db_session() as conn:
        existing = conn.execute(
            "SELECT id FROM hr_users WHERE username=?", (username,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE hr_users SET password_hash=?, role=? WHERE username=?",
                (password_hash, role, username),
            )
            return existing["id"]
        cur = conn.execute(
            "INSERT INTO hr_users (username, password_hash, role) VALUES (?,?,?)",
            (username, password_hash, role),
        )
        return cur.lastrowid


# ─── Auth: HR Sessions (JWT jti tracking) ────────────────────────────────────

def create_session_record(jti: str, user_id: int, username: str, role: str, expires_at: str) -> None:
    """Persist a JWT session record. Called immediately after token issuance."""
    with db_session() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO hr_sessions
               (jti, user_id, username, role, expires_at)
               VALUES (?,?,?,?,?)""",
            (jti, user_id, username, role, expires_at),
        )


def get_session_record(jti: str) -> dict | None:
    """Return a session record by JWT id claim, or None."""
    with db_session() as conn:
        row = conn.execute(
            "SELECT * FROM hr_sessions WHERE jti=?", (jti,)
        ).fetchone()
        return dict(row) if row else None


def revoke_session(jti: str) -> None:
    """Mark a JWT session as revoked (used on logout)."""
    with db_session() as conn:
        conn.execute("UPDATE hr_sessions SET revoked=1 WHERE jti=?", (jti,))


def purge_expired_sessions() -> int:
    """Delete sessions that have already expired. Returns number of rows deleted."""
    with db_session() as conn:
        cur = conn.execute(
            "DELETE FROM hr_sessions WHERE expires_at < datetime('now')"
        )
        return cur.rowcount
