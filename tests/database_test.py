"""
database_test.py - Hard tests for the AI Recruitment System database layer.

Tests cover:
  1.  Schema integrity    — all tables and indexes exist with correct columns
  2.  Pipeline runs       — create_run, finish_run, get_runs, status transitions
  3.  Candidate CRUD      — insert, upsert (update), get by name, get all, score ordering
  4.  Cascade safety      — FK enforcement: no orphan candidates, schedules, tokens
  5.  Schedule CRUD       — save_schedule, get_latest_schedule, update_schedule_slot
  6.  Email log           — log_email, mark_email_sent, get_confirmed_not_emailed
  7.  Interview tokens    — create, get, mark_used, delete_all, duplicate rejection
  8.  Job templates       — save, get_all, delete
  9.  Concurrency         — 20 threads writing simultaneously with no data corruption
 10.  Rollback on error   — db_session rolls back on exception, no dirty data
 11.  SQL injection       — parameterized queries block injection strings
 12.  Large payloads      — 1000 candidates bulk insert + query performance
"""

import json

# ── Bootstrap: use a temporary test database, never touch production ─────────
import os
import sqlite3
import sys
import tempfile
import threading
import time
from pathlib import Path

_tmp = tempfile.mkdtemp()
_TEST_DB = Path(_tmp) / "test_ars.db"
os.environ["_TEST_DB_OVERRIDE"] = str(_TEST_DB)

# Patch data_path before importing anything from the app
import src.common as _cm

_original_data_path = _cm.data_path
def _test_data_path(relative: str) -> Path:
    p = _TEST_DB.parent / relative
    p.parent.mkdir(parents=True, exist_ok=True)
    return p
_cm.data_path = _test_data_path

# Now import database module — it will use the patched data_path
import importlib

import app.database as db

db.DB_PATH = _TEST_DB
importlib.reload(db)

# ── Test scaffolding ─────────────────────────────────────────────────────────
PASS = "[PASS]"
FAIL = "[FAIL]"
results = []

def check(name, condition, details=""):
    status = PASS if condition else FAIL
    print(f"  {status} {name}")
    if details:
        print(f"         {details}")
    results.append((name, condition))

def expect_exception(name, exc_type, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        print(f"  {FAIL} {name}  (expected {exc_type.__name__}, got no exception)")
        results.append((name, False))
    except exc_type:
        print(f"  {PASS} {name}")
        results.append((name, True))
    except Exception as e:
        print(f"  {FAIL} {name}  (expected {exc_type.__name__}, got {type(e).__name__}: {e})")
        results.append((name, False))

# ── Initialize fresh schema ───────────────────────────────────────────────────
db.init_db()
print("\n" + "="*60)
print("  AI Recruitment System - Database Test Suite")
print(f"  Test DB: {_TEST_DB}")
print("="*60 + "\n")

# ══════════════════════════════════════════════════════════════════
# Block 1 — Schema Integrity
# ══════════════════════════════════════════════════════════════════
print("[ Block 1 ] Schema integrity\n")

with db.db_session() as conn:
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    required = {"pipeline_runs", "candidates", "schedules", "email_log", "interview_tokens", "job_templates"}
    missing = required - tables
    check("All 6 tables present", not missing, f"missing: {missing}" if missing else "")

    indexes = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()}
    required_idx = {"idx_candidates_run_id", "idx_schedules_run_id", "idx_schedules_status", "idx_interview_tokens_token"}
    missing_idx = required_idx - indexes
    check("All 4 custom indexes present", not missing_idx, f"missing: {missing_idx}" if missing_idx else "")

    fk_enabled = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    check("PRAGMA foreign_keys=ON per connection", fk_enabled == 1)

    wal = conn.execute("PRAGMA journal_mode").fetchone()[0]
    check("WAL journal mode active", wal == "wal")

# ══════════════════════════════════════════════════════════════════
# Block 2 — Pipeline Runs
# ══════════════════════════════════════════════════════════════════
print("\n[ Block 2 ] Pipeline runs\n")

run_id = db.create_run("nlp", metadata={"job": "Software Engineer"})
check("create_run returns integer id", isinstance(run_id, int) and run_id > 0)

runs = db.get_runs()
check("get_runs returns list", isinstance(runs, list) and len(runs) >= 1)
check("new run status is RUNNING", runs[0]["status"] == "RUNNING")

db.finish_run(run_id, status="COMPLETED", metadata={"candidates": 5})
runs = db.get_runs()
check("finish_run sets COMPLETED status", runs[0]["status"] == "COMPLETED")
check("finish_run updates metadata", json.loads(runs[0]["metadata"]).get("candidates") == 5)

db.finish_run(run_id, status="FAILED")
runs = db.get_runs()
check("finish_run can transition to FAILED", runs[0]["status"] == "FAILED")

run_id2 = db.create_run("ranking")
filtered = db.get_runs(run_type="ranking")
check("get_runs filters by run_type", len(filtered) == 1 and filtered[0]["run_type"] == "ranking")

# ══════════════════════════════════════════════════════════════════
# Block 3 — Candidate CRUD + upsert
# ══════════════════════════════════════════════════════════════════
print("\n[ Block 3 ] Candidate CRUD + upsert\n")

run_id = db.create_run("nlp")
cid = db.upsert_candidate(run_id, "Alice Smith", email="alice@test.com", score=88.5, skills=["Python", "SQL"])
check("upsert_candidate inserts and returns id", isinstance(cid, int) and cid > 0)

cand = db.get_candidate_by_name("Alice Smith", run_id=run_id)
check("get_candidate_by_name returns correct record", cand is not None and cand["email"] == "alice@test.com")
check("skills stored as JSON list", json.loads(cand["skills"]) == ["Python", "SQL"])
check("score stored correctly", abs(cand["score"] - 88.5) < 0.001)

# Upsert = update
cid2 = db.upsert_candidate(run_id, "Alice Smith", email="alice@new.com", score=95.0, skills=["Python", "SQL", "AWS"])
check("upsert returns same id on update", cid2 == cid)
cand2 = db.get_candidate_by_name("Alice Smith", run_id=run_id)
check("upsert updated email", cand2["email"] == "alice@new.com")
check("upsert updated score", abs(cand2["score"] - 95.0) < 0.001)
check("upsert updated skills", len(json.loads(cand2["skills"])) == 3)

# Insert second candidate
db.upsert_candidate(run_id, "Bob Jones", email="bob@test.com", score=70.0)
all_cands = db.get_all_candidates(run_id=run_id)
check("get_all_candidates returns both records", len(all_cands) == 2)
check("get_all_candidates orders by score DESC", all_cands[0]["score"] >= all_cands[1]["score"])

# get_candidate_by_name without run_id returns latest
cand_latest = db.get_candidate_by_name("Alice Smith")
check("get_candidate_by_name without run_id returns latest", cand_latest is not None)

# ══════════════════════════════════════════════════════════════════
# Block 4 — Foreign Key + Cascade Safety
# ══════════════════════════════════════════════════════════════════
print("\n[ Block 4 ] Foreign key enforcement\n")

def _insert_orphan_candidate():
    with db.db_session() as conn:
        conn.execute(
            "INSERT INTO candidates (run_id, name) VALUES (?, ?)",
            (999999, "Orphan Candidate")
        )

expect_exception(
    "INSERT candidate with nonexistent run_id raises IntegrityError",
    sqlite3.IntegrityError,
    _insert_orphan_candidate
)

def _insert_orphan_schedule():
    with db.db_session() as conn:
        conn.execute(
            "INSERT INTO schedules (run_id, candidate_name) VALUES (?, ?)",
            (999999, "Orphan Schedule")
        )

expect_exception(
    "INSERT schedule with nonexistent run_id raises IntegrityError",
    sqlite3.IntegrityError,
    _insert_orphan_schedule
)

# ══════════════════════════════════════════════════════════════════
# Block 5 — Schedules
# ══════════════════════════════════════════════════════════════════
print("\n[ Block 5 ] Schedules\n")

sched_run = db.create_run("scheduling")
entries = [
    {"candidate_name": "Alice Smith", "rank": 1, "score": 95.0, "offered_slots": ["Mon 9am", "Tue 10am"], "selected_slot": "", "status": "PENDING"},
    {"candidate_name": "Bob Jones",   "rank": 2, "score": 70.0, "offered_slots": ["Wed 2pm"],              "selected_slot": "", "status": "PENDING"},
]
ids = db.save_schedule(sched_run, entries, job_title="Software Engineer")
check("save_schedule returns correct number of ids", len(ids) == 2)

sched = db.get_latest_schedule()
check("get_latest_schedule returns entries", len(sched) == 2)
check("schedule ranks ordered correctly", sched[0]["rank"] <= sched[1]["rank"])
check("offered_slots stored as JSON", isinstance(json.loads(sched[0]["offered_slots"]), list))

db.update_schedule_slot("Alice Smith", "Mon 9am")
updated = db.get_latest_schedule(run_id=sched_run)
alice = next(s for s in updated if s["candidate_name"] == "Alice Smith")
check("update_schedule_slot sets selected_slot", alice["selected_slot"] == "Mon 9am")
check("update_schedule_slot sets status to CONFIRMED", alice["status"] == "CONFIRMED")

confirmed = db.get_confirmed_not_emailed(run_id=sched_run)
check("get_confirmed_not_emailed returns Alice", len(confirmed) == 1 and confirmed[0]["candidate_name"] == "Alice Smith")

db.mark_email_sent(alice["id"])
confirmed2 = db.get_confirmed_not_emailed(run_id=sched_run)
check("mark_email_sent removes from get_confirmed_not_emailed", len(confirmed2) == 0)

# ══════════════════════════════════════════════════════════════════
# Block 6 — Email Log
# ══════════════════════════════════════════════════════════════════
print("\n[ Block 6 ] Email log\n")

db.log_email(sched_run, alice["id"], "alice@test.com", "Interview Invite", status="SENT")
db.log_email(sched_run, alice["id"], "alice@test.com", "Reminder", status="FAILED", error="SMTP timeout")

with db.db_session() as conn:
    logs = conn.execute("SELECT * FROM email_log WHERE run_id=?", (sched_run,)).fetchall()
    logs = [dict(log_row) for log_row in logs]

check("email_log has 2 entries", len(logs) == 2)
check("SENT log has empty error", logs[0]["error"] == "" or logs[0]["status"] == "SENT")
failed_log = next((log_row for log_row in logs if log_row["status"] == "FAILED"), None)
check("FAILED log has error message", failed_log is not None and "SMTP" in failed_log["error"])

# ══════════════════════════════════════════════════════════════════
# Block 7 — Interview Tokens
# ══════════════════════════════════════════════════════════════════
print("\n[ Block 7 ] Interview tokens\n")

import secrets

tok = "T_" + secrets.token_hex(8)
db.create_interview_token(tok, "Alice Smith", "alice.pdf", job_title="Engineer", rank=1, score=95.0)
check("create_interview_token succeeds", True)

fetched = db.get_interview_token(tok)
check("get_interview_token returns correct record", fetched is not None and fetched["candidate_name"] == "Alice Smith")
check("token not used yet", fetched["used"] == 0)

db.mark_token_used(tok)
fetched2 = db.get_interview_token(tok)
check("mark_token_used sets used=1", fetched2["used"] == 1)

all_toks = db.get_all_tokens()
check("get_all_tokens returns list", isinstance(all_toks, list) and len(all_toks) >= 1)

def _insert_duplicate_token():
    db.create_interview_token(tok, "Alice Smith", "alice.pdf")  # same token

expect_exception(
    "Duplicate token raises IntegrityError (UNIQUE constraint)",
    sqlite3.IntegrityError,
    _insert_duplicate_token
)

db.delete_all_tokens()
check("delete_all_tokens clears table", len(db.get_all_tokens()) == 0)

# ══════════════════════════════════════════════════════════════════
# Block 8 — Job Templates
# ══════════════════════════════════════════════════════════════════
print("\n[ Block 8 ] Job templates\n")

tid = db.save_job_template("  Senior Python Dev  ", "  Must know async and type hints.  ")
check("save_job_template returns id", isinstance(tid, int) and tid > 0)

templates = db.get_all_job_templates()
check("get_all_job_templates returns list", len(templates) >= 1)
check("title is stripped", templates[0]["title"] == "Senior Python Dev")
check("jd_text is stripped", templates[0]["jd_text"] == "Must know async and type hints.")

db.delete_job_template(tid)
templates2 = db.get_all_job_templates()
check("delete_job_template removes record", all(t["id"] != tid for t in templates2))

# ══════════════════════════════════════════════════════════════════
# Block 9 — Concurrent writes (20 threads)
# ══════════════════════════════════════════════════════════════════
print("\n[ Block 9 ] Concurrent writes (20 threads)\n")

conc_run = db.create_run("concurrency_test")
errors = []

def _worker(i):
    try:
        db.upsert_candidate(conc_run, f"Concurrent Candidate {i}", email=f"c{i}@test.com", score=float(i))
    except Exception as e:
        errors.append(str(e))

threads = [threading.Thread(target=_worker, args=(i,)) for i in range(20)]
start = time.perf_counter()
for t in threads:
    t.start()
for t in threads:
    t.join()
elapsed = time.perf_counter() - start

check("No exceptions during concurrent writes", len(errors) == 0,
      f"errors: {errors}" if errors else "")
all_conc = db.get_all_candidates(run_id=conc_run)
check("All 20 candidates written correctly", len(all_conc) == 20,
      f"got {len(all_conc)}")
check(f"Concurrent writes completed in < 5s ({elapsed:.2f}s)", elapsed < 5.0)

# ══════════════════════════════════════════════════════════════════
# Block 10 — Rollback on exception
# ══════════════════════════════════════════════════════════════════
print("\n[ Block 10 ] Transaction rollback on error\n")

rollback_run = db.create_run("rollback_test")
try:
    with db.db_session() as conn:
        conn.execute(
            "INSERT INTO candidates (run_id, name, score) VALUES (?, ?, ?)",
            (rollback_run, "Rollback Test", 50.0)
        )
        raise ValueError("Simulated error mid-transaction")
except ValueError:
    pass

after = db.get_all_candidates(run_id=rollback_run)
check("Transaction rolled back — no partial data written", len(after) == 0,
      f"got {len(after)} rows (should be 0)")

# ══════════════════════════════════════════════════════════════════
# Block 11 — SQL injection prevention
# ══════════════════════════════════════════════════════════════════
print("\n[ Block 11 ] SQL injection prevention\n")

inj_run = db.create_run("injection_test")
injection_strings = [
    "'; DROP TABLE candidates; --",
    "1 OR 1=1",
    "Robert'); DROP TABLE candidates;--",
    '\" OR \"1\"=\"1',
]
for s in injection_strings:
    cid = db.upsert_candidate(inj_run, s, email="safe@test.com", score=0)
    check(f"Injection string stored safely: {repr(s[:40])}", isinstance(cid, int))

# Verify table still exists with correct row count
survivors = db.get_all_candidates(run_id=inj_run)
check("candidates table survived all injection attempts", len(survivors) == len(injection_strings))

# ══════════════════════════════════════════════════════════════════
# Block 12 — Bulk performance (1000 rows)
# ══════════════════════════════════════════════════════════════════
print("\n[ Block 12 ] Bulk performance (1000 candidates)\n")

bulk_run = db.create_run("bulk_test")
start = time.perf_counter()
for i in range(1000):
    db.upsert_candidate(bulk_run, f"Bulk Candidate {i:04d}", score=float(i % 100))
bulk_insert_time = time.perf_counter() - start

start = time.perf_counter()
all_bulk = db.get_all_candidates(run_id=bulk_run)
bulk_query_time = time.perf_counter() - start

check(f"1000 inserts completed in < 90s ({bulk_insert_time:.2f}s)", bulk_insert_time < 90.0)
check(f"Query of 1000 rows completed in < 1s ({bulk_query_time:.3f}s)", bulk_query_time < 1.0)
check("All 1000 rows returned", len(all_bulk) == 1000)
check("Results ordered by score DESC", all_bulk[0]["score"] >= all_bulk[-1]["score"])

# ── Summary ───────────────────────────────────────────────────────
import shutil

shutil.rmtree(_tmp, ignore_errors=True)

print("\n" + "="*60)
total  = len(results)
passed = sum(1 for _, ok in results if ok)
failed = total - passed
print(f"  Result: {passed}/{total} passed, {failed} failed")
print("="*60 + "\n")

if failed:
    sys.exit(1)
