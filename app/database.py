import json
import secrets
import sqlite3
import time
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key          TEXT PRIMARY KEY,
            value        TEXT NOT NULL,
            is_encrypted INTEGER DEFAULT 0,
            updated_at   TEXT DEFAULT (datetime('now'))
        )
    """)
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

        CREATE TABLE IF NOT EXISTS app_settings (
            key          TEXT PRIMARY KEY,
            value        TEXT NOT NULL,
            is_encrypted INTEGER DEFAULT 0,
            updated_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS interview_sessions (
            session_id     TEXT PRIMARY KEY,
            token          TEXT NOT NULL,
            candidate_name TEXT NOT NULL,
            job_title      TEXT DEFAULT '',
            session_data   TEXT NOT NULL,
            created_at     REAL NOT NULL,
            updated_at     TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS candidate_embeddings (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_name TEXT NOT NULL UNIQUE,
            source_file    TEXT DEFAULT '',
            domain         TEXT DEFAULT '',
            skills_json    TEXT DEFAULT '[]',
            profile_text   TEXT DEFAULT '',
            vector_json    TEXT DEFAULT '[]',
            updated_at     TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS ai_telemetry (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            provider          TEXT NOT NULL,
            model             TEXT NOT NULL,
            prompt_tokens     INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            latency_seconds   REAL DEFAULT 0.0,
            status            TEXT DEFAULT 'SUCCESS',
            cost_usd          REAL DEFAULT 0.0,
            created_at        TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS candidate_feedback (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_name TEXT NOT NULL,
            email          TEXT DEFAULT '',
            job_title      TEXT DEFAULT '',
            feedback_text  TEXT NOT NULL,
            status         TEXT DEFAULT 'DRAFT',
            sent_at        TEXT,
            created_at     TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS candidate_offers (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_name TEXT NOT NULL,
            email          TEXT DEFAULT '',
            job_title      TEXT DEFAULT '',
            start_date     TEXT DEFAULT '',
            compensation   TEXT DEFAULT '',
            offer_letter   TEXT NOT NULL,
            status         TEXT DEFAULT 'DRAFT',
            sent_at        TEXT,
            created_at     TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS candidate_notes (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_name TEXT NOT NULL UNIQUE,
            source_file    TEXT DEFAULT '',
            note           TEXT DEFAULT '',
            tags           TEXT DEFAULT '',
            updated_at     TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS hr_notifications (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            type           TEXT NOT NULL,
            title          TEXT NOT NULL,
            message        TEXT NOT NULL,
            candidate_name TEXT DEFAULT '',
            job_title      TEXT DEFAULT '',
            link           TEXT DEFAULT '',
            is_read        INTEGER DEFAULT 0,
            created_at     TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_candidates_run_id ON candidates(run_id);
        CREATE INDEX IF NOT EXISTS idx_schedules_run_id ON schedules(run_id);
        CREATE INDEX IF NOT EXISTS idx_schedules_status ON schedules(status);
        CREATE INDEX IF NOT EXISTS idx_interview_tokens_token ON interview_tokens(token);
        CREATE INDEX IF NOT EXISTS idx_interview_sessions_token ON interview_sessions(token);
        CREATE INDEX IF NOT EXISTS idx_candidate_embeddings_name ON candidate_embeddings(candidate_name);
        CREATE INDEX IF NOT EXISTS idx_ai_telemetry_created ON ai_telemetry(created_at);
        CREATE INDEX IF NOT EXISTS idx_candidate_feedback_name ON candidate_feedback(candidate_name);
        CREATE INDEX IF NOT EXISTS idx_candidate_notes_name ON candidate_notes(candidate_name);
        CREATE INDEX IF NOT EXISTS idx_hr_notifications_read ON hr_notifications(is_read);
    """)
    try:
        from src.security import migrate_database_secrets
        migrate_database_secrets(conn)
    except Exception:
        pass
    conn.commit()
    conn.close()
    print("[DB] Database initialised:", DB_PATH)


# ─── Settings Persistence Helpers ───

def get_setting(key: str, default=None) -> str:
    """Fetch a single setting from the database by key."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT value, is_encrypted FROM app_settings WHERE key=?", (key,)).fetchone()
        if not row:
            return default
        val = row["value"]
        if row["is_encrypted"]:
            from src.security import decrypt_secret
            val = decrypt_secret(val)
        return val
    finally:
        conn.close()


def set_setting(key: str, value: str, is_encrypted: bool = False):
    """Save or update a setting in the database."""
    conn = get_connection()
    try:
        str_val = str(value) if value is not None else ""
        if is_encrypted and str_val and not str_val.startswith("ENC:"):
            from src.security import encrypt_secret
            str_val = encrypt_secret(str_val)

        conn.execute(
            """INSERT INTO app_settings (key, value, is_encrypted, updated_at)
               VALUES (?, ?, ?, datetime('now'))
               ON CONFLICT(key) DO UPDATE SET value=excluded.value, is_encrypted=excluded.is_encrypted, updated_at=datetime('now')""",
            (key, str_val, 1 if is_encrypted else 0)
        )
        conn.commit()
    finally:
        conn.close()


def get_all_settings() -> dict:
    """Return all database settings as a dictionary of key-value pairs (decrypting sensitive keys)."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT key, value, is_encrypted FROM app_settings").fetchall()
        result = {}
        for r in rows:
            val = r["value"]
            if r["is_encrypted"]:
                from src.security import decrypt_secret
                val = decrypt_secret(val)
            result[r["key"]] = val
        return result
    finally:
        conn.close()


def save_settings_dict(settings_dict: dict):
    """Bulk save dictionary of configuration key-values to the database."""
    from src.security import SENSITIVE_KEYS
    conn = get_connection()
    try:
        for k, v in settings_dict.items():
            if k.startswith("_"):
                continue
            is_enc = k in SENSITIVE_KEYS
            str_val = str(v) if v is not None else ""
            if is_enc and str_val and not str_val.startswith("ENC:"):
                from src.security import encrypt_secret
                stored_val = encrypt_secret(str_val)
            else:
                stored_val = str_val

            conn.execute(
                """INSERT INTO app_settings (key, value, is_encrypted, updated_at)
                   VALUES (?, ?, ?, datetime('now'))
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value, is_encrypted=excluded.is_encrypted, updated_at=datetime('now')""",
                (k, stored_val, 1 if is_enc else 0)
            )
        conn.commit()
    finally:
        conn.close()


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
    """Insert or update a candidate within a run. Encrypts email PII at rest. Returns the candidate id."""
    from src.security import encrypt_secret
    stored_email = encrypt_secret(email) if email else ""

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
                (stored_email, source_file, score, skills_json, row["id"]),
            )
            cid = row["id"]
        else:
            cur = conn.execute(
                "INSERT INTO candidates (run_id, name, email, source_file, score, skills) VALUES (?,?,?,?,?,?)",
                (run_id, name, stored_email, source_file, score, skills_json),
            )
            cid = cur.lastrowid
        conn.commit()
        return cid
    finally:
        conn.close()

def get_candidate_by_name(name, run_id=None):
    """Return candidate row or None with transparently decrypted PII. If run_id given, scoped to that run."""
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
        if not row:
            return None
        from src.security import decrypt_secret
        cand_dict = dict(row)
        if cand_dict.get("email"):
            cand_dict["email"] = decrypt_secret(cand_dict["email"])
        return cand_dict
    finally:
        conn.close()

def get_all_candidates(run_id=None):
    """Return candidates as a list of dicts with transparently decrypted PII. If run_id given, scoped to that run."""
    conn = get_connection()
    try:
        if run_id:
            rows = conn.execute(
                "SELECT * FROM candidates WHERE run_id=? ORDER BY score DESC", (run_id,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM candidates ORDER BY score DESC").fetchall()
        from src.security import decrypt_secret
        results = []
        for r in rows:
            d = dict(r)
            if d.get("email"):
                d["email"] = decrypt_secret(d["email"])
            results.append(d)
        return results
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
    """Log an email send attempt. Encrypts recipient email address at rest."""
    from src.security import encrypt_secret
    stored_recipient = encrypt_secret(recipient) if recipient else ""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO email_log (run_id, schedule_id, recipient, subject, status, error) VALUES (?,?,?,?,?,?)",
            (run_id, schedule_id, stored_recipient, subject, status, error),
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

def generate_interview_token() -> str:
    """Generate a high-entropy cryptographically secure interview access token (256 bits)."""
    return f"T_{secrets.token_hex(32)}"

def create_interview_token(token=None, candidate_name="", source_file="", job_title="", rank=0, score=0):
    """Create a unique interview token for a candidate. Returns the token string."""
    if not token:
        token = generate_interview_token()
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


def delete_candidate(candidate_id: int) -> dict | None:
    """Purge a candidate and all related database records (schedules, email_logs, tokens, feedback, offers, notes, embeddings, notifications).
    Returns deleted candidate metadata (name, source_file, email) or None if not found."""
    conn = get_connection()
    try:
        cur = conn.execute("SELECT id, name, email, source_file FROM candidates WHERE id=?", (candidate_id,))
        cand = cur.fetchone()
        if not cand:
            return None
        cand_dict = dict(cand)
        name = cand_dict["name"]
        source_file = cand_dict.get("source_file") or ""
        email = cand_dict.get("email") or ""

        # Resolve effective plaintext email
        effective_email = ""
        if email:
            if email.startswith("ENC:"):
                try:
                    from src.security import decrypt_secret

                    effective_email = decrypt_secret(email)
                except Exception:
                    effective_email = ""
            else:
                effective_email = email

        # Delete from email_log for matching schedules
        conn.execute("""
            DELETE FROM email_log WHERE schedule_id IN (
                SELECT id FROM schedules WHERE candidate_name=?
            )
        """, (name,))

        # Delete from email_log for matching recipient (plaintext or encrypted)
        if effective_email:
            rows = conn.execute("SELECT id, recipient FROM email_log WHERE recipient != ''").fetchall()
            from src.security import decrypt_secret

            ids_to_del = []
            for r in rows:
                recip = r["recipient"]
                if recip == effective_email:
                    ids_to_del.append(r["id"])
                elif recip.startswith("ENC:"):
                    try:
                        if decrypt_secret(recip) == effective_email:
                            ids_to_del.append(r["id"])
                    except Exception:
                        pass
            if ids_to_del:
                placeholders = ",".join("?" for _ in ids_to_del)
                conn.execute(f"DELETE FROM email_log WHERE id IN ({placeholders})", tuple(ids_to_del))

        # Delete from schedules
        conn.execute("DELETE FROM schedules WHERE candidate_name=?", (name,))

        # Delete from interview_tokens
        conn.execute("DELETE FROM interview_tokens WHERE candidate_name=? OR (source_file != '' AND source_file=?)", (name, source_file))

        # Delete from interview_sessions
        conn.execute("DELETE FROM interview_sessions WHERE candidate_name=?", (name,))

        # Delete from candidate_feedback
        if effective_email:
            conn.execute("DELETE FROM candidate_feedback WHERE candidate_name=? OR (email != '' AND email=?)", (name, effective_email))
        else:
            conn.execute("DELETE FROM candidate_feedback WHERE candidate_name=?", (name,))

        # Delete from candidate_offers
        if effective_email:
            conn.execute("DELETE FROM candidate_offers WHERE candidate_name=? OR (email != '' AND email=?)", (name, effective_email))
        else:
            conn.execute("DELETE FROM candidate_offers WHERE candidate_name=?", (name,))

        # Delete from candidate_notes
        conn.execute("DELETE FROM candidate_notes WHERE candidate_name=? OR (source_file != '' AND source_file=?)", (name, source_file))

        # Delete from candidate_embeddings
        conn.execute("DELETE FROM candidate_embeddings WHERE candidate_name=? OR (source_file != '' AND source_file=?)", (name, source_file))

        # Delete from hr_notifications
        conn.execute("DELETE FROM hr_notifications WHERE candidate_name=?", (name,))

        # Delete from candidates
        conn.execute("DELETE FROM candidates WHERE id=?", (candidate_id,))
        conn.commit()
        return cand_dict
    finally:
        conn.close()


def save_interview_session(session_id: str, data: dict):
    """Insert or update an active interview session in SQLite."""
    token = data.get("token", "")
    cand_name = data.get("candidate_name", "")
    job_title = data.get("job_title", "")
    created_at = data.get("started_at") or data.get("created_at") or time.time()
    payload = json.dumps(data)
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO interview_sessions (session_id, token, candidate_name, job_title, session_data, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(session_id) DO UPDATE SET
                token=excluded.token,
                candidate_name=excluded.candidate_name,
                job_title=excluded.job_title,
                session_data=excluded.session_data,
                updated_at=datetime('now')
            """,
            (session_id, token, cand_name, job_title, payload, created_at),
        )


def get_interview_session(session_id: str) -> dict | None:
    """Retrieve an interview session by session_id from SQLite."""
    with db_session() as conn:
        row = conn.execute(
            "SELECT session_data FROM interview_sessions WHERE session_id=?", (session_id,)
        ).fetchone()
        if row and row["session_data"]:
            return json.loads(row["session_data"])
        return None


def get_active_session_by_token(token: str) -> tuple[str | None, dict | None]:
    """Retrieve the most recent session for an interview token."""
    with db_session() as conn:
        row = conn.execute(
            "SELECT session_id, session_data FROM interview_sessions WHERE token=? ORDER BY rowid DESC LIMIT 1",
            (token,),
        ).fetchone()
        if row and row["session_data"]:
            return row["session_id"], json.loads(row["session_data"])
        return None, None


def delete_interview_session(session_id: str) -> bool:
    """Delete an interview session by session_id."""
    with db_session() as conn:
        conn.execute("DELETE FROM interview_sessions WHERE session_id=?", (session_id,))
        return True


def cleanup_expired_interview_sessions(ttl_seconds: int = 7200) -> int:
    """Delete sessions older than ttl_seconds from SQLite."""
    cutoff = time.time() - ttl_seconds
    with db_session() as conn:
        cur = conn.execute("DELETE FROM interview_sessions WHERE created_at < ?", (cutoff,))
        return cur.rowcount


# ─── Talent Intelligence & Analytics Helpers ───

def upsert_candidate_embedding(candidate_name: str, source_file: str, domain: str, skills: list, profile_text: str, vector: list):
    """Store or update candidate vector profile in SQLite."""
    with db_session() as conn:
        conn.execute("""
            INSERT INTO candidate_embeddings (candidate_name, source_file, domain, skills_json, profile_text, vector_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(candidate_name) DO UPDATE SET
                source_file = excluded.source_file,
                domain = excluded.domain,
                skills_json = excluded.skills_json,
                profile_text = excluded.profile_text,
                vector_json = excluded.vector_json,
                updated_at = datetime('now')
        """, (
            candidate_name,
            source_file,
            domain,
            json.dumps(skills or []),
            profile_text,
            json.dumps(vector or [])
        ))


def get_all_candidate_embeddings() -> list:
    """Fetch all candidate vector profiles from SQLite."""
    with db_session() as conn:
        rows = conn.execute("""
            SELECT id, candidate_name, source_file, domain, skills_json, profile_text, vector_json, updated_at
            FROM candidate_embeddings
            ORDER BY candidate_name ASC
        """).fetchall()
        result = []
        for r in rows:
            result.append({
                "id": r["id"],
                "candidate_name": r["candidate_name"],
                "source_file": r["source_file"],
                "domain": r["domain"],
                "skills": json.loads(r["skills_json"]) if r["skills_json"] else [],
                "profile_text": r["profile_text"],
                "vector": json.loads(r["vector_json"]) if r["vector_json"] else [],
                "updated_at": r["updated_at"]
            })
        return result


def log_telemetry(provider: str, model: str, prompt_tokens: int, completion_tokens: int, latency_seconds: float, status: str = "SUCCESS", cost_usd: float = 0.0):
    """Log an AI request event for performance and cost tracking."""
    try:
        with db_session() as conn:
            conn.execute("""
                INSERT INTO ai_telemetry (provider, model, prompt_tokens, completion_tokens, latency_seconds, status, cost_usd, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                provider or "unknown",
                model or "unknown",
                int(prompt_tokens or 0),
                int(completion_tokens or 0),
                float(latency_seconds or 0.0),
                status or "SUCCESS",
                float(cost_usd or 0.0)
            ))
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Failed to log AI telemetry: %s", e)


def get_telemetry_metrics() -> dict:
    """Return aggregated AI telemetry metrics for dashboard visualization."""
    with db_session() as conn:
        total_calls = conn.execute("SELECT COUNT(*) as count FROM ai_telemetry").fetchone()["count"]
        avg_latency = conn.execute("SELECT AVG(latency_seconds) as avg_lat FROM ai_telemetry WHERE latency_seconds > 0").fetchone()["avg_lat"] or 0.0
        total_prompt_tok = conn.execute("SELECT SUM(prompt_tokens) as tok FROM ai_telemetry").fetchone()["tok"] or 0
        total_comp_tok = conn.execute("SELECT SUM(completion_tokens) as tok FROM ai_telemetry").fetchone()["tok"] or 0
        total_cost = conn.execute("SELECT SUM(cost_usd) as cost FROM ai_telemetry").fetchone()["cost"] or 0.0

        provider_breakdown = conn.execute("""
            SELECT provider, COUNT(*) as count, AVG(latency_seconds) as avg_lat,
                   SUM(prompt_tokens + completion_tokens) as total_tokens,
                   SUM(cost_usd) as total_cost
            FROM ai_telemetry
            GROUP BY provider
            ORDER BY count DESC
        """).fetchall()

        # Calculate estimated savings from Ollama (cloud pricing ~$0.003 / 1k tokens = ~₹0.25 / 1k tokens)
        USD_TO_INR = 85.0
        ollama_tokens = conn.execute("""
            SELECT SUM(prompt_tokens + completion_tokens) as tok
            FROM ai_telemetry
            WHERE provider LIKE '%ollama%' OR provider LIKE '%privacy%'
        """).fetchone()["tok"] or 0
        estimated_saved_usd = round((ollama_tokens / 1000.0) * 0.003, 2)
        estimated_saved_inr = round(estimated_saved_usd * USD_TO_INR, 2)
        total_cost_inr = round(total_cost * USD_TO_INR, 2)

        providers = []
        for r in provider_breakdown:
            p_dict = dict(r)
            p_cost_usd = p_dict.get("total_cost") or 0.0
            p_dict["total_cost_usd"] = round(p_cost_usd, 4)
            p_dict["total_cost_inr"] = round(p_cost_usd * USD_TO_INR, 2)
            p_dict["total_cost"] = p_dict["total_cost_inr"]
            providers.append(p_dict)

        return {
            "total_calls": total_calls,
            "avg_latency": round(avg_latency, 2),
            "total_tokens": total_prompt_tok + total_comp_tok,
            "total_cost": total_cost_inr,
            "total_cost_usd": round(total_cost, 4),
            "total_cost_inr": total_cost_inr,
            "estimated_saved_usd": estimated_saved_usd,
            "estimated_saved_inr": estimated_saved_inr,
            "currency": "INR",
            "currency_symbol": "₹",
            "providers": providers
        }


def save_candidate_feedback(candidate_name: str, email: str, job_title: str, feedback_text: str, status: str = "DRAFT") -> int:
    """Save or update tailored candidate feedback."""
    with db_session() as conn:
        cur = conn.execute("""
            INSERT INTO candidate_feedback (candidate_name, email, job_title, feedback_text, status, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        """, (candidate_name, email or "", job_title or "", feedback_text, status))
        return cur.lastrowid


def get_all_candidate_feedback() -> list:
    """Fetch all candidate feedback items."""
    with db_session() as conn:
        rows = conn.execute("""
            SELECT id, candidate_name, email, job_title, feedback_text, status, sent_at, created_at
            FROM candidate_feedback
            ORDER BY id DESC
        """).fetchall()
        return [dict(r) for r in rows]


def mark_feedback_sent(feedback_id: int):
    """Mark a feedback item as SENT with current timestamp."""
    with db_session() as conn:
        conn.execute("""
            UPDATE candidate_feedback
            SET status = 'SENT', sent_at = datetime('now')
            WHERE id = ?
        """, (feedback_id,))


# ─── Candidate Job Offers & Selection Letters ───

def save_candidate_offer(
    candidate_name: str,
    email: str,
    job_title: str,
    offer_letter: str,
    start_date: str = "",
    compensation: str = "",
    status: str = "DRAFT",
) -> int:
    """Save or update a formal candidate offer and selection letter."""
    with db_session() as conn:
        cur = conn.execute("""
            INSERT INTO candidate_offers (candidate_name, email, job_title, start_date, compensation, offer_letter, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (candidate_name.strip(), (email or "").strip(), (job_title or "").strip(), (start_date or "").strip(), (compensation or "").strip(), offer_letter, status))
        return int(cur.lastrowid or 0)


def get_candidate_offers(candidate_name: str = None) -> list[dict]:
    """Fetch candidate offers, optionally filtered by candidate name, ordered newest first."""
    with db_session() as conn:
        if candidate_name:
            rows = conn.execute("""
                SELECT id, candidate_name, email, job_title, start_date, compensation, offer_letter, status, sent_at, created_at
                FROM candidate_offers
                WHERE candidate_name = ?
                ORDER BY id DESC
            """, (candidate_name.strip(),)).fetchall()
        else:
            rows = conn.execute("""
                SELECT id, candidate_name, email, job_title, start_date, compensation, offer_letter, status, sent_at, created_at
                FROM candidate_offers
                ORDER BY id DESC
            """).fetchall()
        return [dict(r) for r in rows]


def get_candidate_offer_by_id(offer_id: int) -> dict | None:
    """Fetch a single candidate offer by its primary key ID."""
    with db_session() as conn:
        row = conn.execute("""
            SELECT id, candidate_name, email, job_title, start_date, compensation, offer_letter, status, sent_at, created_at
            FROM candidate_offers
            WHERE id = ?
        """, (offer_id,)).fetchone()
        return dict(row) if row else None


def mark_offer_sent(offer_id: int):
    """Mark an offer letter as SENT with the current timestamp."""
    with db_session() as conn:
        conn.execute("""
            UPDATE candidate_offers
            SET status = 'SENT', sent_at = datetime('now')
            WHERE id = ?
        """, (offer_id,))



# ─── Recruiter Candidate Notes & Tags ───

def _parse_tags(raw_tags) -> list[str]:
    if not raw_tags:
        return []
    if isinstance(raw_tags, list):
        return [str(t) for t in raw_tags]
    try:
        parsed = json.loads(raw_tags)
        if isinstance(parsed, list):
            return [str(t) for t in parsed]
    except Exception:
        pass
    return [t.strip() for t in str(raw_tags).split(",") if t.strip()]


def save_candidate_note(candidate_name: str, note: str, tags: list[str] | str = "", source_file: str = ""):
    """Save or update recruiter notes and tags for a candidate."""
    if isinstance(tags, (list, tuple, set)):
        tags_str = json.dumps(list(tags))
    else:
        tags_str = str(tags or "").strip()

    with db_session() as conn:
        conn.execute("""
            INSERT INTO candidate_notes (candidate_name, source_file, note, tags, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            ON CONFLICT(candidate_name) DO UPDATE SET
                note = excluded.note,
                tags = excluded.tags,
                source_file = CASE WHEN excluded.source_file != '' THEN excluded.source_file ELSE candidate_notes.source_file END,
                updated_at = datetime('now')
        """, (candidate_name.strip(), (source_file or "").strip(), (note or "").strip(), tags_str))


def get_candidate_note(candidate_name: str) -> dict:
    """Retrieve recruiter notes and tags for a candidate."""
    with db_session() as conn:
        row = conn.execute("SELECT * FROM candidate_notes WHERE candidate_name = ?", (candidate_name.strip(),)).fetchone()
        if row:
            res = dict(row)
            res["tags"] = _parse_tags(res.get("tags"))
            return res
        return {"candidate_name": candidate_name, "note": "", "tags": [], "source_file": ""}


def get_all_candidate_notes() -> dict[str, dict]:
    """Retrieve all candidate notes indexed by candidate name."""
    with db_session() as conn:
        rows = conn.execute("SELECT candidate_name, note, tags, source_file, updated_at FROM candidate_notes").fetchall()
        result = {}
        for r in rows:
            d = dict(r)
            d["tags"] = _parse_tags(d.get("tags"))
            result[d["candidate_name"]] = d
        return result


# ─── HR Notifications ───

def create_hr_notification(
    title: str,
    message: str,
    candidate_name: str = "",
    job_title: str = "",
    notif_type: str = "interview_completed",
    link: str = "/reports",
) -> int:
    """Create a new notification for the HR manager."""
    with db_session() as conn:
        cursor = conn.execute("""
            INSERT INTO hr_notifications (type, title, message, candidate_name, job_title, link, is_read, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 0, datetime('now'))
        """, (notif_type, title, message, candidate_name, job_title, link))
        return int(cursor.lastrowid or 0)


def get_hr_notifications(limit: int = 30, unread_only: bool = False) -> list[dict]:
    """Retrieve recent notifications for HR."""
    with db_session() as conn:
        query = "SELECT * FROM hr_notifications"
        params: list = []
        if unread_only:
            query += " WHERE is_read = 0"
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_unread_notification_count() -> int:
    """Count unread HR notifications."""
    with db_session() as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM hr_notifications WHERE is_read = 0").fetchone()
        return int(row["count"]) if row else 0


def mark_notification_read(notif_id: int):
    """Mark a specific notification as read."""
    with db_session() as conn:
        conn.execute("UPDATE hr_notifications SET is_read = 1 WHERE id = ?", (notif_id,))


def mark_all_notifications_read():
    """Mark all notifications as read."""
    with db_session() as conn:
        conn.execute("UPDATE hr_notifications SET is_read = 1 WHERE is_read = 0")



