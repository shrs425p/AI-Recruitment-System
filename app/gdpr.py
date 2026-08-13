"""
app/gdpr.py -- GDPR / CCPA Data Retention, Deletion & Consent Helpers
=======================================================================

Provides:
  delete_candidate_data(candidate_id)  -- hard-delete all PII for one candidate
  purge_old_data(days)                 -- bulk-delete candidates older than N days
  record_consent(token, ip)            -- stamp consent on an interview token
  check_consent(token) -> bool         -- True if candidate has consented

All destructive operations write an audit entry to the `data_deletion_log`
table so HR can demonstrate GDPR compliance on request.
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.database import db_session, get_connection

logger = logging.getLogger(__name__)


# -- Schema migration helper (called from init_db) ----------------------------

GDPR_MIGRATION_SQL = """
    -- Consent tracking on interview invites
    CREATE TABLE IF NOT EXISTS data_deletion_log (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        action       TEXT NOT NULL,
        target_id    TEXT,
        reason       TEXT DEFAULT '',
        deleted_at   TEXT DEFAULT (datetime('now')),
        deleted_by   TEXT DEFAULT 'system'
    );
"""


def ensure_gdpr_schema() -> None:
    """Create GDPR tables and add consent columns if missing. Safe to call on every boot."""
    conn = get_connection()
    try:
        conn.executescript(GDPR_MIGRATION_SQL)
        conn.commit()

        # Add consent columns to interview_tokens if not present
        cols = {row[1] for row in conn.execute("PRAGMA table_info(interview_tokens)").fetchall()}
        if "consent_given" not in cols:
            conn.execute("ALTER TABLE interview_tokens ADD COLUMN consent_given INTEGER DEFAULT 0")
        if "consent_at" not in cols:
            conn.execute("ALTER TABLE interview_tokens ADD COLUMN consent_at TEXT DEFAULT NULL")
        if "consent_ip" not in cols:
            conn.execute("ALTER TABLE interview_tokens ADD COLUMN consent_ip TEXT DEFAULT NULL")
        conn.commit()
        logger.debug("[GDPR] Schema ensured.")
    finally:
        conn.close()


# -- Consent ------------------------------------------------------------------

def record_consent(token: str, ip: str = "") -> bool:
    """
    Stamp consent on an interview_tokens row.

    Called when the candidate ticks the consent checkbox and clicks
    'Start Interview'. Returns False if the token does not exist.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM interview_tokens WHERE token=?", (token,)
        ).fetchone()
        if not row:
            return False
        conn.execute(
            """UPDATE interview_tokens
               SET consent_given=1, consent_at=datetime('now'), consent_ip=?
               WHERE token=?""",
            (ip[:45] if ip else "", token),
        )
        conn.commit()
        logger.info("[GDPR] Consent recorded for token=%s ip=%s", token[:8], ip)
        return True
    finally:
        conn.close()


def check_consent(token: str) -> bool:
    """Return True if the candidate has given consent for this interview session."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT consent_given FROM interview_tokens WHERE token=?", (token,)
        ).fetchone()
        return bool(row and row["consent_given"])
    finally:
        conn.close()


# -- Deletion -----------------------------------------------------------------

def delete_candidate_data(candidate_id: int, reason: str = "HR request", deleted_by: str = "admin") -> dict:
    """
    Hard-delete all data for a candidate across all tables and disk files.

    Removes:
      - candidates row
      - schedules rows (by candidate_name match)
      - interview_tokens rows (by candidate_name match)
      - email_log rows (linked via schedule_ids)
      - Resume file, NLP JSON, ranking JSON, interview transcript, report files
        (matched by source_file stem)

    Args:
        candidate_id: Primary key in the `candidates` table.
        reason:       Reason string for the audit log.
        deleted_by:   Username of the HR user triggering deletion.

    Returns:
        dict with keys: success (bool), rows_deleted (int), files_deleted (int), error (str|None)
    """
    rows_deleted = 0
    files_deleted = 0
    error = None

    try:
        conn = get_connection()
        try:
            # 1. Fetch candidate details before deleting
            row = conn.execute(
                "SELECT * FROM candidates WHERE id=?", (candidate_id,)
            ).fetchone()
            if not row:
                return {"success": False, "error": f"Candidate {candidate_id} not found.", "rows_deleted": 0, "files_deleted": 0}

            name = row["name"]
            source_file = row["source_file"]

            # 2. Collect linked schedule ids
            sched_ids = [
                r["id"] for r in conn.execute(
                    "SELECT id FROM schedules WHERE candidate_name=?", (name,)
                ).fetchall()
            ]

            # 3. Delete email_log entries for those schedules
            if sched_ids:
                placeholders = ",".join("?" * len(sched_ids))
                cur = conn.execute(f"DELETE FROM email_log WHERE schedule_id IN ({placeholders})", sched_ids)
                rows_deleted += cur.rowcount

            # 4. Delete schedules
            cur = conn.execute("DELETE FROM schedules WHERE candidate_name=?", (name,))
            rows_deleted += cur.rowcount

            # 5. Delete interview tokens
            cur = conn.execute("DELETE FROM interview_tokens WHERE candidate_name=?", (name,))
            rows_deleted += cur.rowcount

            # 6. Delete candidate row
            cur = conn.execute("DELETE FROM candidates WHERE id=?", (candidate_id,))
            rows_deleted += cur.rowcount

            conn.commit()

        finally:
            conn.close()

        # 7. Delete associated disk files
        files_deleted = _delete_candidate_files(source_file, name)

        # 8. Write audit log
        _log_deletion("CANDIDATE_DELETE", str(candidate_id), reason, deleted_by)
        logger.info(
            "[GDPR] Candidate %d (%s) deleted -- rows=%d files=%d by=%s",
            candidate_id, name, rows_deleted, files_deleted, deleted_by,
        )
        return {"success": True, "rows_deleted": rows_deleted, "files_deleted": files_deleted, "error": None}

    except Exception as exc:
        logger.error("[GDPR] delete_candidate_data failed: %s", exc, exc_info=True)
        return {"success": False, "error": str(exc), "rows_deleted": rows_deleted, "files_deleted": files_deleted}


def purge_old_data(days: int = 90, deleted_by: str = "system") -> dict:
    """
    Delete all candidate records created more than `days` days ago.

    Args:
        days:       Retention window in days (default 90).
        deleted_by: Username of the triggering user / 'system' for scheduled runs.

    Returns:
        dict with keys: success (bool), candidates_deleted (int), error (str|None)
    """
    try:
        conn = get_connection()
        try:
            old_ids = [
                row["id"] for row in conn.execute(
                    "SELECT id FROM candidates WHERE created_at < datetime('now', ?)",
                    (f"-{days} days",),
                ).fetchall()
            ]
        finally:
            conn.close()

        total_deleted = 0
        for cid in old_ids:
            result = delete_candidate_data(cid, reason=f"Retention purge >{days}d", deleted_by=deleted_by)
            if result["success"]:
                total_deleted += 1

        _log_deletion("RETENTION_PURGE", f"{days}d", f"Auto-purge >{days} days", deleted_by)
        logger.info("[GDPR] Retention purge complete -- %d candidates deleted (>%dd).", total_deleted, days)
        return {"success": True, "candidates_deleted": total_deleted, "error": None}

    except Exception as exc:
        logger.error("[GDPR] purge_old_data failed: %s", exc, exc_info=True)
        return {"success": False, "candidates_deleted": 0, "error": str(exc)}


# -- Audit log ----------------------------------------------------------------

def _log_deletion(action: str, target_id: str, reason: str, deleted_by: str) -> None:
    """Write an immutable deletion record to data_deletion_log."""
    try:
        with db_session() as conn:
            conn.execute(
                "INSERT INTO data_deletion_log (action, target_id, reason, deleted_by) VALUES (?,?,?,?)",
                (action, target_id, reason, deleted_by),
            )
    except Exception as exc:
        logger.error("[GDPR] Audit log write failed: %s", exc)


# -- File cleanup -------------------------------------------------------------

def _delete_candidate_files(source_file: str, name: str) -> int:
    """Delete all disk artifacts associated with this candidate. Returns count of deleted files."""
    from src.common import data_dir
    deleted = 0

    if not source_file:
        return deleted

    stem = Path(source_file).stem

    # Directories to scan for files matching the candidate's source stem
    search_dirs = [
        ("resumes", True),
        ("output/txt", False),
        ("output/nlp", False),
        ("output/ranking", False),
        ("output/scheduling", False),
        ("output/interviews", False),
        ("output/reports", False),
    ]

    for subdir, exact_match in search_dirs:
        try:
            base = data_dir(subdir)
            for f in base.iterdir():
                if f.is_file() and (stem in f.name or (not exact_match and name.replace(" ", "_") in f.name)):
                    f.unlink(missing_ok=True)
                    deleted += 1
                    logger.debug("[GDPR] Deleted file: %s", f)
        except Exception as exc:
            logger.warning("[GDPR] File cleanup error in %s: %s", subdir, exc)

    return deleted
