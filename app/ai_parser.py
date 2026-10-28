"""
ai_parser.py — AI-powered bank alert email parser for Money Manager Cloud.
Supports Google Gemini and Groq, configurable per user or via cloud environment.
"""

import json
import os
import sys
import re
import time

# Fix Windows emoji encoding issue
if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure') and sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(__file__))
from categories import CATEGORIES, classify_merchant, validate_category


SYSTEM_PROMPT = f"""You are a precise bank transaction email parser for Indian banks.

Extract the following details from the bank alert email and respond ONLY with valid JSON.
Do not include any explanation or markdown — just the raw JSON object.

JSON schema:
{{
  "is_transaction": true/false,        // false if this email is NOT a transaction alert
  "type": "debit" or "credit",
  "amount": <number in INR, no currency symbol>,
  "date": "YYYY-MM-DD",
  "time": "HH:MM" or null,
  "merchant": "<merchant/payee name, clean title case>",
  "category": "<one of the valid categories below>",
  "balance": <available balance as number, or null if not mentioned>,
  "description": "<brief 1-line description of the transaction>"
}}

Valid categories: {", ".join(CATEGORIES)}

Rules:
- If the email is a promotional mail, OTP, login alert, or not a transaction, set is_transaction=false and return only that field.
- Amount must be a plain number (e.g. 1250.50), never a string.
- For merchant, extract the business name cleanly (e.g. "Swiggy", "Amazon", "HDFC ATM").
- For UPI transfers, merchant = recipient name or UPI ID (shortened).
- Date format must be YYYY-MM-DD.
- Choose the most fitting category from the list above.
"""


def _get_client_for_user(user_settings: dict = None):
    """
    Determine AI provider and client for a specific user.
    Falls back to cloud environment variables if user has not specified their own key.
    """
    user_settings = user_settings or {}

    provider = (user_settings.get("ai_provider") or os.getenv("AI_PROVIDER", "")).strip().lower()
    gemini_key = (user_settings.get("gemini_api_key") or os.getenv("GEMINI_API_KEY", "")).strip()
    groq_key = (user_settings.get("groq_api_key") or os.getenv("GROQ_API_KEY", "")).strip()

    if not provider:
        if gemini_key:
            provider = "gemini"
        elif groq_key:
            provider = "groq"
        else:
            provider = "gemini"

    if provider == "groq":
        if not groq_key or groq_key.startswith("your_"):
            raise ValueError("Groq API key not provided in User Settings or Cloud Environment.")
        from groq import Groq
        model = user_settings.get("groq_model") or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        return "groq", Groq(api_key=groq_key), model
    else:
        if not gemini_key or gemini_key.startswith("your_"):
            raise ValueError("Gemini API key not configured. Please enter your free key in Settings.")
        from google import genai
        model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        return "gemini", genai.Client(api_key=gemini_key), model


def _parse_with_groq(client, model: str, email_body: str) -> str:
    """Call Groq API using Llama model."""
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Parse this bank email:\n\n{email_body}"},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    return completion.choices[0].message.content.strip()


def _parse_with_gemini(client, model: str, email_body: str) -> str:
    """Call Gemini API using Google GenAI SDK (Interactions API with auto-retry)."""
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            interaction = client.interactions.create(
                model=model,
                system_instruction=SYSTEM_PROMPT,
                input=f"Parse this bank email:\n\n{email_body}",
                store=False,
            )
            return interaction.output_text.strip()
        except Exception as e:
            err_str = str(e)
            # If rate limited (429), back off and retry
            if ("429" in err_str or "RESOURCE_EXHAUSTED" in err_str) and attempt < max_retries:
                time.sleep(2.0 * attempt)
                continue
            # If interactions API is not supported on this endpoint, fallback to generate_content
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=f"{SYSTEM_PROMPT}\n\nParse this bank email:\n\n{email_body}",
                )
                return response.text.strip()
            except Exception as e2:
                if ("429" in str(e2) or "RESOURCE_EXHAUSTED" in str(e2)) and attempt < max_retries:
                    time.sleep(2.0 * attempt)
                    continue
                raise e


def parse_email_with_ai(email_body: str, user_settings: dict = None) -> dict | None:
    """
    Parse a bank alert email using Gemini or Groq.
    Respects individual user configuration.
    Returns a dict with transaction details, or None if not a transaction.
    """
    try:
        provider, client, model = _get_client_for_user(user_settings)
    except Exception as e:
        print(f"⚠️ AI Client Init error: {e}")
        return None

    raw = ""
    try:
        if provider == "groq":
            raw = _parse_with_groq(client, model, email_body)
        else:
            raw = _parse_with_gemini(client, model, email_body)

        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        data = json.loads(raw)

        if not data.get("is_transaction", True):
            return None

        category = validate_category(data.get("category", ""))
        if category == "Other":
            category = classify_merchant(
                data.get("merchant", ""),
                data.get("description", ""),
            )
        data["category"] = category
        data["amount"] = float(data.get("amount", 0))

        return data

    except json.JSONDecodeError as e:
        print(f"⚠️ AI returned invalid JSON: {e}\nRaw output: {raw[:300]}")
        return None
    except Exception as e:
        print(f"⚠️ AI parsing error ({provider}): {e}")
        return None
