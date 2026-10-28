"""
sync.py — Multi-tenant Sync Orchestrator for Money Manager Cloud.
Coordinates email fetching, AI parsing, and insertion for a specific user.
"""

import sys
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Fix Windows emoji encoding issue
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(__file__))

from email_reader import fetch_bank_emails_for_user
from ai_parser import parse_email_with_ai
from database import (
    get_user_settings,
    get_all_synced_ids,
    insert_transaction,
)


def sync_emails_for_user(
    user_id: int,
    start_date: str = None,
    end_date: str = None,
    progress_callback=None,
    max_workers: int = 3,
) -> dict:
    """
    Fetch new bank emails for user_id, parse them with AI concurrently, and save to their private database.
    """
    settings = get_user_settings(user_id)
    if not settings:
        raise ValueError(f"User {user_id} settings not found.")

    if progress_callback:
        progress_callback(0.05, "Connecting to Gmail and searching for bank alerts...")

    synced_ids = get_all_synced_ids(user_id)

    emails = fetch_bank_emails_for_user(
        user_settings=settings,
        start_date=start_date,
        end_date=end_date,
        already_synced_ids=synced_ids,
        max_workers=max_workers,
    )

    if not emails:
        if progress_callback:
            progress_callback(1.0, "All emails are already up to date!")
        return {"inserted": 0, "skipped": 0, "total": 0}

    total_emails = len(emails)
    if progress_callback:
        progress_callback(0.15, f"Parsing {total_emails} emails with AI...")

    inserted = 0
    skipped_not_txn = 0
    completed_count = 0

    def _parse_and_insert(em):
        msg_id = em["msg_id"]
        # Mild spacing to prevent bursting AI rate limits
        time.sleep(0.2)
        parsed = parse_email_with_ai(em["body"], user_settings=settings)
        if parsed is None:
            return "not_txn", em

        txn = {
            "email_msg_id": msg_id,
            "date":         parsed.get("date", ""),
            "time":         parsed.get("time"),
            "type":         parsed.get("type", "debit"),
            "amount":       parsed.get("amount", 0.0),
            "merchant":     parsed.get("merchant", "Unknown"),
            "category":     parsed.get("category", "Other"),
            "balance":      parsed.get("balance"),
            "description":  parsed.get("description", ""),
            "raw_email":    em["body"],
        }
        success = insert_transaction(user_id, txn)
        return ("inserted" if success else "duplicate"), txn

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_parse_and_insert, em): em for em in emails}
        for future in as_completed(futures):
            completed_count += 1
            status, data = future.result()
            if status == "inserted":
                inserted += 1
            elif status == "not_txn":
                skipped_not_txn += 1

            if progress_callback:
                fraction = 0.15 + 0.85 * (completed_count / total_emails)
                progress_callback(fraction, f"Parsed {completed_count}/{total_emails} bank emails...")

    if progress_callback:
        progress_callback(1.0, f"Sync complete! Added {inserted} new transactions.")

    return {"inserted": inserted, "skipped": skipped_not_txn, "total": total_emails}
