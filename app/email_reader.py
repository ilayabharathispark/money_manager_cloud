"""
email_reader.py — Bank alert email fetcher for Money Manager Cloud.
Supports dual sync methods:
1. Gmail IMAP with App Password (zero GCP setup needed for end users)
2. Gmail API with OAuth 2.0
"""

import os
import sys
import re
import base64
import email
from email import policy
import imaplib
import threading
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# Fix Windows emoji encoding issue
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')


def _extract_body_text(payload: dict) -> str:
    """Recursively search for plain text or HTML body across all MIME parts."""
    if not payload:
        return ""
    data = payload.get("body", {}).get("data")
    mime = payload.get("mimeType", "")
    if data and mime.startswith("text/plain"):
        try:
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        except Exception:
            pass

    parts = payload.get("parts", [])
    # 1. Search text/plain parts recursively
    for part in parts:
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            try:
                return base64.urlsafe_b64decode(part["body"]["data"] + "==").decode("utf-8", errors="replace")
            except Exception:
                pass
        if part.get("parts"):
            nested = _extract_body_text(part)
            if nested:
                return nested

    # 2. HTML fallback stripped of tags
    for part in parts:
        if part.get("mimeType") == "text/html" and part.get("body", {}).get("data"):
            try:
                html = base64.urlsafe_b64decode(part["body"]["data"] + "==").decode("utf-8", errors="replace")
                return re.sub(r'<[^>]+>', ' ', html)
            except Exception:
                pass

    if data:
        try:
            raw = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
            return re.sub(r'<[^>]+>', ' ', raw)
        except Exception:
            pass

    return payload.get("snippet", "")


# ── Method 1: IMAP with Gmail App Password (Zero GCP friction) ─────────────────

def _fetch_via_imap(settings: dict, start_date: str = None, end_date: str = None, already_synced_ids: set = None, max_workers: int = 3) -> list[dict]:
    """
    Fetch bank alert emails using IMAP over SSL (imap.gmail.com).
    User configures their Gmail address and a 16-character Google App Password.
    """
    gmail_user = (settings.get("gmail_address") or "").strip()
    gmail_pwd = (settings.get("gmail_app_password") or "").strip().replace(" ", "")
    bank_sender = (settings.get("bank_email_sender") or "").strip()

    if not gmail_user or not gmail_pwd:
        raise ValueError("Please provide your Gmail Address and App Password in Settings.")
    if not bank_sender:
        raise ValueError("Please specify your Bank Alert Sender Email in Settings.")

    already_synced_ids = already_synced_ids or set()

    mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    try:
        mail.login(gmail_user, gmail_pwd)
        mail.select('"[Gmail]/All Mail"', readonly=True)

        # Build IMAP search criteria
        criteria = [f'(FROM "{bank_sender}")']
        if start_date:
            try:
                d_obj = datetime.strptime(start_date, "%Y-%m-%d")
                criteria.append(f'(SINCE "{d_obj.strftime("%d-%b-%Y")}")')
            except Exception:
                pass
        if end_date:
            try:
                # Add 1 day so end_date is inclusive (IMAP BEFORE is strictly exclusive)
                d_end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
                criteria.append(f'(BEFORE "{d_end.strftime("%d-%b-%Y")}")')
            except Exception:
                pass

        search_query = " ".join(criteria)
        status, data = mail.search(None, search_query)
        if status != "OK" or not data[0]:
            return []

        msg_nums = data[0].split()
        emails = []

        for num in reversed(msg_nums):
            # Fetch headers first to check Message-ID without downloading full payload
            _, header_data = mail.fetch(num, "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID SUBJECT DATE)])")
            if not header_data or not header_data[0]:
                continue

            raw_header = header_data[0][1]
            header_msg = email.message_from_bytes(raw_header, policy=policy.default)
            msg_id = header_msg.get("Message-ID", "").strip("<> \n\r\t")

            # Fallback if no Message-ID header
            if not msg_id:
                msg_id = f"imap_{num.decode('utf-8', errors='ignore')}"

            if msg_id in already_synced_ids:
                continue

            # Fetch full message
            _, full_data = mail.fetch(num, "(RFC822)")
            if not full_data or not full_data[0]:
                continue

            msg_bytes = full_data[0][1]
            parsed_msg = email.message_from_bytes(msg_bytes, policy=policy.default)

            body = ""
            if parsed_msg.is_multipart():
                for part in parsed_msg.walk():
                    if part.get_content_type() == "text/plain":
                        try:
                            body = part.get_content()
                            break
                        except Exception:
                            pass
            else:
                try:
                    body = parsed_msg.get_content()
                except Exception:
                    pass

            if not body:
                body = parsed_msg.get_payload()
                if isinstance(body, list):
                    body = "\n".join(str(p) for p in body)

            emails.append({
                "msg_id": msg_id,
                "subject": parsed_msg.get("Subject", ""),
                "date": parsed_msg.get("Date", ""),
                "body": str(body).strip(),
            })

        return emails
    finally:
        try:
            mail.logout()
        except Exception:
            pass


# ── Method 2: Gmail API with OAuth 2.0 ─────────────────────────────────────────

def _fetch_via_oauth(settings: dict, start_date: str = None, end_date: str = None, already_synced_ids: set = None, max_workers: int = 3) -> list[dict]:
    """Fetch bank emails using Google Gmail API with OAuth token."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    import json

    token_str = settings.get("gmail_token_json", "").strip()
    if not token_str:
        # Check environment or local file
        token_file = os.path.join(os.path.dirname(__file__), "..", "data", "gmail_token.json")
        if os.path.exists(token_file):
            with open(token_file, "r", encoding="utf-8") as f:
                token_str = f.read()

    if not token_str:
        raise ValueError("OAuth Token not found. Please connect your Gmail in Settings or use App Password method.")

    token_info = json.loads(token_str)
    creds = Credentials.from_authorized_user_info(token_info)

    _oauth_local = threading.local()

    def _get_service():
        if not hasattr(_oauth_local, "service") or _oauth_local.service is None:
            _oauth_local.service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return _oauth_local.service

    service = _get_service()
    sender = settings.get("bank_email_sender") or os.getenv("BANK_EMAIL_SENDER", "alerts@yourbank.com")
    already_synced_ids = already_synced_ids or set()

    query = f"from:{sender}"
    if start_date:
        query += f" after:{start_date.replace('-', '/')}"
    if end_date:
        try:
            # Add 1 day so end_date is inclusive (Gmail 'before' is strictly exclusive)
            d_next = (datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y/%m/%d")
            query += f" before:{d_next}"
        except Exception:
            query += f" before:{end_date.replace('-', '/')}"

    results = service.users().messages().list(userId="me", q=query, maxResults=500).execute()
    messages = results.get("messages", [])
    if not messages:
        return []

    all_ids = [m["id"] for m in messages]
    new_ids = [mid for mid in all_ids if mid not in already_synced_ids]
    if not new_ids:
        return []

    emails = []

    def _download_single(msg_id):
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                svc = _get_service()
                msg = svc.users().messages().get(userId="me", id=msg_id, format="full").execute()
                headers = msg.get("payload", {}).get("headers", [])
                subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), "")
                date_val = next((h["value"] for h in headers if h["name"].lower() == "date"), "")

                # Extract body with full nested MIME and HTML support
                body = _extract_body_text(msg.get("payload", {}))

                return {
                    "msg_id": msg_id,
                    "subject": subject,
                    "date": date_val,
                    "body": body,
                }
            except Exception as e:
                if attempt < max_retries:
                    time.sleep(1.0 * attempt)
                    continue
                print(f"⚠️ Error fetching message {msg_id}: {e}")
                return None

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_download_single, mid): mid for mid in new_ids}
        for future in as_completed(futures):
            res = future.result()
            if res:
                emails.append(res)

    return emails


# ── Unified Fetcher Function ───────────────────────────────────────────────────

def fetch_bank_emails_for_user(user_settings: dict, start_date: str = None, end_date: str = None, already_synced_ids: set = None, max_workers: int = 3) -> list[dict]:
    """
    Fetch emails using the user's selected authentication method:
    - 'app_password' (default, seamless IMAP)
    - 'oauth' (Google OAuth 2.0)
    """
    method = (user_settings.get("gmail_auth_method") or "app_password").strip().lower()

    if method == "oauth":
        return _fetch_via_oauth(user_settings, start_date, end_date, already_synced_ids, max_workers)
    else:
        return _fetch_via_imap(user_settings, start_date, end_date, already_synced_ids, max_workers)
