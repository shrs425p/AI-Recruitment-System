"""
Password Reset Utility — AI Recruitment System
Allows administrators to reset the HR password or disable login if locked out.
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path
from werkzeug.security import check_password_hash, generate_password_hash


def get_db_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        p = Path(local_app_data) / "AI Recruitment System" / "data" / "ars.db"
        if p.exists():
            return p
    # Fallback to local data dir
    local_p = Path(__file__).resolve().parent.parent / "data" / "ars.db"
    return local_p


def verify_credentials(password: str) -> bool:
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT value FROM app_settings WHERE key = 'HR_PASSWORD_HASH'")
    row = cur.fetchone()
    conn.close()
    if not row or not row[0]:
        return False
    return check_password_hash(row[0], password)


def reset_password(new_password: str | None = None, disable_login: bool = False) -> None:
    db_path = get_db_path()
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT value FROM app_settings WHERE key = 'HR_USERNAME'")
    row = cur.fetchone()
    username = row[0] if row else "hr"

    if disable_login:
        cur.execute(
            """INSERT INTO app_settings (key, value, is_encrypted, updated_at)
               VALUES ('LOGIN_ENABLED', 'False', 0, datetime('now'))
               ON CONFLICT(key) DO UPDATE SET value='False', updated_at=datetime('now')"""
        )
        conn.commit()
        print("Login has been disabled (LOGIN_ENABLED = False).")
        print("You can now access the dashboard directly without entering credentials.")
        conn.close()
        return

    if not new_password:
        new_password = "admin"

    new_hash = generate_password_hash(new_password)
    cur.execute(
        """INSERT INTO app_settings (key, value, is_encrypted, updated_at)
           VALUES ('HR_PASSWORD_HASH', ?, 0, datetime('now'))
           ON CONFLICT(key) DO UPDATE SET value=?, updated_at=datetime('now')""",
        (new_hash, new_hash),
    )
    cur.execute(
        """INSERT INTO app_settings (key, value, is_encrypted, updated_at)
           VALUES ('HR_PASSWORD', '', 0, datetime('now'))
           ON CONFLICT(key) DO UPDATE SET value='', updated_at=datetime('now')"""
    )
    cur.execute(
        """INSERT INTO app_settings (key, value, is_encrypted, updated_at)
           VALUES ('LOGIN_ENABLED', 'True', 0, datetime('now'))
           ON CONFLICT(key) DO UPDATE SET value='True', updated_at=datetime('now')"""
    )
    conn.commit()
    conn.close()

    print("Password reset successful.")
    print(f"Username: {username}")
    print(f"Password: {new_password}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset HR credentials for AI Recruitment System")
    parser.add_argument("--password", "-p", help="New HR password (defaults to 'admin')", default=None)
    parser.add_argument("--disable-login", "-d", action="store_true", help="Temporarily disable login prompt")
    parser.add_argument("--verify", "-v", help="Verify given password against stored hash", default=None)
    args = parser.parse_args()

    if args.verify:
        ok = verify_credentials(args.verify)
        print(f"Credential verification result: {'SUCCESS' if ok else 'FAILED'}")
    else:
        reset_password(new_password=args.password, disable_login=args.disable_login)
