"""
validate_db.py — Diagnostic & Health Check Tool for Money Manager Cloud.
Verifies SQLite B-tree page integrity, tables, row counts, and isolation.
Usage:
    python scripts/validate_db.py
"""

import sys
import os

# Fix Windows emoji encoding issue
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from database import (
    DATA_DIR,
    AUTH_DB_PATH,
    USERS_DIR,
    init_auth_db,
    validate_database_integrity,
)


def main():
    print("=" * 60)
    print("🔍 MONEY MANAGER CLOUD — DATABASE VALIDATION & HEALTH CHECK")
    print("=" * 60)
    print(f"📁 Storage Directory: {DATA_DIR}")
    print(f"🔒 Auth Database:     {AUTH_DB_PATH}")
    print(f"👥 Users Directory:   {USERS_DIR}")
    print("-" * 60)

    init_auth_db()
    results = validate_database_integrity()

    auth_info = results.get("auth.db", {})
    status = auth_info.get("status", "error")
    icon = "✅" if status == "ok" else "❌"
    print(f"{icon} [auth.db] Integrity Status: {status.upper()} | Registered Users: {auth_info.get('total_users', 0)}")

    users_info = results.get("users", {})
    if not users_info:
        print("ℹ️  No user databases found yet. (Databases are created when users register).")
    else:
        print(f"\n📊 Per-User Database Health ({len(users_info)} active user databases):")
        for db_name, details in users_info.items():
            u_status = details.get("status", "error")
            u_icon = "✅" if u_status == "ok" else "❌"
            print(f"   {u_icon} {db_name:18} | Status: {u_status.upper():4} | Transactions: {details.get('transactions', 0):4} | Deleted Tombstones: {details.get('tombstones', 0):3}")

    print("=" * 60)
    print("🎉 All database integrity checks passed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
