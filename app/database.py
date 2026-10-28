"""
database.py — Per-User Isolated SQLite Architecture for Money Manager Cloud.

Architecture:
- /data/auth.db: Manages user accounts (username, email, salted hashed passwords).
- /data/users/user_{user_id}.db: Dedicated private database for each user.
  - No write collisions between users.
  - Zero lock contention when multiple users sync at the same time.
  - 100% data isolation and privacy.
"""

import sqlite3
import os
import sys
import threading
import hashlib
import secrets
from datetime import datetime

# Fix Windows emoji encoding issue
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

_locks = {}
_lock_for_locks = threading.Lock()

# Base directory for data
DEFAULT_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
DATA_DIR = os.getenv("DATA_DIR", DEFAULT_DATA_DIR)
AUTH_DB_PATH = os.path.join(DATA_DIR, "auth.db")
USERS_DIR = os.path.join(DATA_DIR, "users")


def _get_user_lock(user_id: int) -> threading.Lock:
    """Get or create a dedicated threading lock for a specific user's DB."""
    with _lock_for_locks:
        if user_id not in _locks:
            _locks[user_id] = threading.Lock()
        return _locks[user_id]


def _cleanup_wal_files(db_path: str):
    """Remove any orphaned -shm and -wal files created by earlier WAL runs on GCS FUSE."""
    for ext in ["-shm", "-wal", "-journal"]:
        p = db_path + ext
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass


def get_auth_connection() -> sqlite3.Connection:
    """Return a connection to the central auth.db with GCS FUSE safe in-memory journal mode."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
    except Exception:
        pass
    _cleanup_wal_files(AUTH_DB_PATH)
    conn = sqlite3.connect(AUTH_DB_PATH, timeout=60.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=MEMORY;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA busy_timeout=60000;")
        conn.execute("PRAGMA synchronous=OFF;")
    except Exception:
        pass
    return conn


def get_user_db_path(user_id: int) -> str:
    """Return path to a specific user's database file."""
    try:
        os.makedirs(USERS_DIR, exist_ok=True)
    except Exception:
        pass
    return os.path.join(USERS_DIR, f"user_{user_id}.db")


def get_user_connection(user_id: int) -> sqlite3.Connection:
    """Return a connection to a specific user's private database with GCS FUSE safe in-memory journal mode."""
    db_path = get_user_db_path(user_id)
    _cleanup_wal_files(db_path)
    conn = sqlite3.connect(db_path, timeout=60.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=MEMORY;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA busy_timeout=60000;")
        conn.execute("PRAGMA synchronous=OFF;")
    except Exception:
        pass
    return conn


# ── Password Hashing ──────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Generate salted SHA-256 hash for secure password storage."""
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${hashed}"


def verify_password(stored_password_hash: str, provided_password: str) -> bool:
    """Verify a plain password against the stored salt$hash string."""
    try:
        salt, hashed = stored_password_hash.split("$", 1)
        test_hash = hashlib.sha256((salt + provided_password).encode("utf-8")).hexdigest()
        return secrets.compare_digest(hashed, test_hash)
    except Exception:
        return False


# ── Initialization ────────────────────────────────────────────────────────────

def init_auth_db():
    """Create the users table in auth.db."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = get_auth_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                username        TEXT UNIQUE NOT NULL,
                email           TEXT UNIQUE,
                password_hash   TEXT NOT NULL,
                created_at      TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
    finally:
        conn.close()


def init_user_db(user_id: int):
    """Initialize a user's private database with settings and transaction tables."""
    conn = get_user_connection(user_id)
    try:
        # User settings table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id                      INTEGER PRIMARY KEY DEFAULT 1,
                bank_email_sender       TEXT DEFAULT 'alerts@yourbank.com',
                ai_provider             TEXT DEFAULT 'gemini',
                gemini_api_key          TEXT DEFAULT '',
                groq_api_key            TEXT DEFAULT '',
                groq_model              TEXT DEFAULT 'llama-3.3-70b-versatile',
                cash_savings            REAL DEFAULT 0.0,
                cash_notes              TEXT DEFAULT '',
                pf_amount               REAL DEFAULT 0.0,
                pf_notes                TEXT DEFAULT '',
                gold_amount             REAL DEFAULT 0.0,
                gold_notes              TEXT DEFAULT '',
                mutual_funds            REAL DEFAULT 0.0,
                mutual_funds_notes      TEXT DEFAULT '',
                gmail_auth_method       TEXT DEFAULT 'app_password',
                gmail_address           TEXT DEFAULT '',
                gmail_app_password      TEXT DEFAULT '',
                gmail_token_json        TEXT DEFAULT '',
                updated_at              TEXT DEFAULT (datetime('now'))
            )
        """)
        # Ensure default row exists
        conn.execute("INSERT OR IGNORE INTO settings (id) VALUES (1)")

        # Transactions table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                email_msg_id    TEXT UNIQUE,
                date            TEXT NOT NULL,
                time            TEXT,
                type            TEXT NOT NULL,
                amount          REAL NOT NULL,
                merchant        TEXT,
                category        TEXT,
                balance         REAL,
                description     TEXT,
                raw_email       TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            )
        """)

        # Tombstone table for deleted transactions
        conn.execute("""
            CREATE TABLE IF NOT EXISTS deleted_emails (
                email_msg_id    TEXT PRIMARY KEY,
                deleted_at      TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
    finally:
        conn.close()


# ── Auth Operations ───────────────────────────────────────────────────────────

def register_user(username: str, email: str, password: str) -> tuple[bool, str, int | None]:
    """Register a new user and create their isolated database."""
    init_auth_db()
    username = username.strip().lower()
    email = email.strip().lower() if email else None

    if not username or len(username) < 3:
        return False, "Username must be at least 3 characters.", None
    if not password or len(password) < 4:
        return False, "Password must be at least 4 characters.", None

    pwd_hash = hash_password(password)
    conn = get_auth_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, pwd_hash)
        )
        user_id = cur.lastrowid
        conn.commit()

        # Initialize the user's isolated private database
        init_user_db(user_id)
        return True, "Account created successfully!", user_id
    except sqlite3.IntegrityError as e:
        err = str(e).lower()
        if "username" in err:
            return False, f"Username '{username}' is already taken.", None
        elif "email" in err:
            return False, f"Email '{email}' is already registered.", None
        return False, "User registration failed.", None
    finally:
        conn.close()


def authenticate_user(username: str, password: str) -> dict | None:
    """Validate credentials and return user dict if successful."""
    init_auth_db()
    username = username.strip().lower()
    conn = get_auth_connection()
    try:
        row = conn.execute(
            "SELECT id, username, email, password_hash, created_at FROM users WHERE username = ? OR email = ?",
            (username, username)
        ).fetchone()
        if not row:
            return None
        if verify_password(row["password_hash"], password):
            user_id = row["id"]
            # Ensure their private DB is ready
            init_user_db(user_id)
            return {
                "id": user_id,
                "username": row["username"],
                "email": row["email"],
                "created_at": row["created_at"],
            }
        return None
    finally:
        conn.close()


# ── User Settings Operations ──────────────────────────────────────────────────

def get_user_settings(user_id: int) -> dict:
    """Fetch user-specific settings from their isolated database."""
    init_user_db(user_id)
    conn = get_user_connection(user_id)
    try:
        row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def update_user_settings(user_id: int, **kwargs) -> bool:
    """Update settings in the user's private database."""
    init_user_db(user_id)
    allowed = {
        "bank_email_sender", "ai_provider", "gemini_api_key", "groq_api_key",
        "groq_model", "cash_savings", "cash_notes", "pf_amount", "pf_notes",
        "gold_amount", "gold_notes", "mutual_funds", "mutual_funds_notes",
        "gmail_auth_method", "gmail_address", "gmail_app_password", "gmail_token_json"
    }
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False

    set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
    set_clause += ", updated_at = datetime('now')"
    values = list(updates.values())

    lock = _get_user_lock(user_id)
    with lock:
        conn = get_user_connection(user_id)
        try:
            conn.execute(f"UPDATE settings SET {set_clause} WHERE id = 1", values)
            conn.commit()
            return True
        finally:
            conn.close()


# ── Transaction Operations ────────────────────────────────────────────────────

def insert_transaction(user_id: int, txn: dict) -> bool:
    """Insert a transaction into the user's private database. Returns True if inserted, False if duplicate."""
    init_user_db(user_id)
    lock = _get_user_lock(user_id)
    with lock:
        conn = get_user_connection(user_id)
        try:
            conn.execute("""
                INSERT INTO transactions
                    (email_msg_id, date, time, type, amount, merchant, category,
                     balance, description, raw_email)
                VALUES
                    (:email_msg_id, :date, :time, :type, :amount, :merchant,
                     :category, :balance, :description, :raw_email)
            """, txn)
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()


def insert_transactions_batch(user_id: int, txns: list[dict]) -> int:
    """Insert a batch of transactions in a single SQLite transaction on GCS FUSE."""
    if not txns:
        return 0
    init_user_db(user_id)
    lock = _get_user_lock(user_id)
    inserted_count = 0
    with lock:
        conn = get_user_connection(user_id)
        try:
            for txn in txns:
                try:
                    conn.execute("""
                        INSERT INTO transactions
                            (email_msg_id, date, time, type, amount, merchant, category,
                             balance, description, raw_email)
                        VALUES
                            (:email_msg_id, :date, :time, :type, :amount, :merchant,
                             :category, :balance, :description, :raw_email)
                    """, txn)
                    inserted_count += 1
                except sqlite3.IntegrityError:
                    pass
            conn.commit()
            return inserted_count
        finally:
            conn.close()


def get_all_synced_ids(user_id: int) -> set[str]:
    """Return all email_msg_ids already processed or deleted for this user."""
    init_user_db(user_id)
    conn = get_user_connection(user_id)
    try:
        rows = conn.execute("SELECT email_msg_id FROM transactions WHERE email_msg_id IS NOT NULL").fetchall()
        deleted = conn.execute("SELECT email_msg_id FROM deleted_emails").fetchall()
        return {r["email_msg_id"] for r in rows} | {r["email_msg_id"] for r in deleted}
    finally:
        conn.close()


def mark_emails_as_deleted(user_id: int, email_msg_ids: list[str]):
    """Record email_msg_ids in deleted_emails tombstone table so they never re-sync."""
    if not email_msg_ids:
        return
    init_user_db(user_id)
    lock = _get_user_lock(user_id)
    with lock:
        conn = get_user_connection(user_id)
        try:
            conn.executemany(
                "INSERT OR IGNORE INTO deleted_emails (email_msg_id) VALUES (?)",
                [(mid,) for mid in email_msg_ids if mid]
            )
            conn.commit()
        finally:
            conn.close()


def get_all_transactions(
    user_id: int,
    start_date: str = None,
    end_date: str = None,
    category: str = None,
    txn_type: str = None,
) -> list[dict]:
    """Fetch user's transactions with optional filters."""
    init_user_db(user_id)
    conn = get_user_connection(user_id)
    try:
        query = "SELECT * FROM transactions WHERE 1=1"
        params = []
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        if category and category != "All":
            query += " AND category = ?"
            params.append(category)
        if txn_type and txn_type != "All":
            query += " AND type = ?"
            params.append(txn_type)

        query += " ORDER BY date DESC, time DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_summary_stats(user_id: int, start_date: str = None, end_date: str = None) -> dict:
    """Return aggregate stats for a user: total spent, total income, volume."""
    init_user_db(user_id)
    conn = get_user_connection(user_id)
    try:
        query = """
            SELECT
                SUM(CASE WHEN type='debit'  THEN amount ELSE 0 END) AS total_spent,
                SUM(CASE WHEN type='credit' THEN amount ELSE 0 END) AS total_income,
                COUNT(*) AS total_txns
            FROM transactions
            WHERE 1=1
        """
        params = []
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        row = conn.execute(query, params).fetchone()
        return dict(row) if row else {"total_spent": 0.0, "total_income": 0.0, "total_txns": 0}
    finally:
        conn.close()


def get_category_totals(user_id: int, start_date: str = None, end_date: str = None) -> list[dict]:
    """Return total spend per category (debits only) for a user."""
    init_user_db(user_id)
    conn = get_user_connection(user_id)
    try:
        query = """
            SELECT category, SUM(amount) AS total
            FROM transactions
            WHERE type = 'debit'
        """
        params = []
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        query += " GROUP BY category ORDER BY total DESC"

        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_daily_totals(user_id: int, start_date: str = None, end_date: str = None) -> list[dict]:
    """Return daily debit totals for trend charts for a user."""
    init_user_db(user_id)
    conn = get_user_connection(user_id)
    try:
        query = """
            SELECT date, SUM(amount) AS total
            FROM transactions
            WHERE type = 'debit'
        """
        params = []
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        query += " GROUP BY date ORDER BY date ASC"

        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def delete_transaction(user_id: int, txn_id: int) -> bool:
    """Delete a transaction and add to tombstone so it won't re-sync."""
    init_user_db(user_id)
    lock = _get_user_lock(user_id)
    with lock:
        conn = get_user_connection(user_id)
        try:
            row = conn.execute("SELECT email_msg_id FROM transactions WHERE id = ?", (txn_id,)).fetchone()
            if row and row["email_msg_id"]:
                conn.execute(
                    "INSERT OR IGNORE INTO deleted_emails (email_msg_id) VALUES (?)",
                    (row["email_msg_id"],)
                )
            conn.execute("DELETE FROM transactions WHERE id = ?", (txn_id,))
            conn.commit()
            return True
        finally:
            conn.close()


# ── Database Health & Validation ──────────────────────────────────────────────

def validate_database_integrity(user_id: int = None) -> dict:
    """Run PRAGMA integrity_check on auth.db and user databases."""
    init_auth_db()
    results = {}

    # Check auth.db
    auth_conn = get_auth_connection()
    try:
        row = auth_conn.execute("PRAGMA integrity_check;").fetchone()
        auth_status = row[0] if row else "unknown"
        user_count = auth_conn.execute("SELECT count(*) FROM users;").fetchone()[0]
        results["auth.db"] = {
            "status": auth_status,
            "total_users": user_count,
        }
    finally:
        auth_conn.close()

    # Check user DBs
    if user_id:
        targets = [user_id]
    else:
        # Find all user IDs
        auth_conn = get_auth_connection()
        try:
            rows = auth_conn.execute("SELECT id FROM users;").fetchall()
            targets = [r["id"] for r in rows]
        finally:
            auth_conn.close()

    user_results = {}
    for uid in targets:
        init_user_db(uid)
        u_conn = get_user_connection(uid)
        try:
            u_check = u_conn.execute("PRAGMA integrity_check;").fetchone()[0]
            txn_count = u_conn.execute("SELECT count(*) FROM transactions;").fetchone()[0]
            del_count = u_conn.execute("SELECT count(*) FROM deleted_emails;").fetchone()[0]
            user_results[f"user_{uid}.db"] = {
                "status": u_check,
                "transactions": txn_count,
                "tombstones": del_count,
            }
        finally:
            u_conn.close()

    results["users"] = user_results
    return results


if __name__ == "__main__":
    init_auth_db()
    print("Database system initialized successfully.")
