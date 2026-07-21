# -*- coding: utf-8 -*-
"""
ai_notifier.py  |  Corporate Spend Analytics Pipeline
========================================================
Reads ALL flagged anomalies from spend.db, groups them by department manager,
calls the Gemini API to draft a professional email alert for each manager,
and saves the draft as a .txt file in output/alerts/.

*** SIMULATION ONLY — no real emails are sent ***

Requirements:
  - GENAI_API_KEY must be set as a Windows Environment Variable
  - data/spend.db must exist (run generate_data.py first)

Usage:
  python scripts/ai_notifier.py
"""

import sys
import os
import json
import uuid
import sqlite3
import time as _time
from datetime import datetime
from collections import defaultdict

# Force UTF-8 output on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from google import genai
from dotenv import load_dotenv

# Load .env if present (optional — GENAI_API_KEY may already be in system env vars)
load_dotenv()

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT       = os.path.join(os.path.dirname(__file__), "..")
DB_PATH    = os.path.join(ROOT, "data", "spend.db")
VIEWS_PATH   = os.path.join(ROOT, "sql", "views.sql")
OUT_DIR      = os.path.join(ROOT, "output", "alerts")
RUN_LOG_PATH = os.path.join(ROOT, "output", "run_log.json")
CONFIG_PATH  = os.path.join(ROOT, "output", "config.json")

# Model pricing registry (USD per 1M tokens)
MODEL_PRICING = {
    "gemini-2.5-flash-lite":           {"input": 0.075, "output": 0.30},
    "gemini-2.5-flash":                {"input": 0.150, "output": 0.60},
    "gemini-2.5-pro":                  {"input": 1.250, "output": 5.00},
    "gemini-2.0-flash-thinking-exp-01-21": {"input": 0.150, "output": 0.60},
}

DEFAULT_MODEL = "gemini-2.5-flash-lite"

def load_active_model() -> tuple[str, float, float]:
    """Read active model from config.json or fall back to default."""
    model_name = DEFAULT_MODEL
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                model_name = cfg.get("active_model", DEFAULT_MODEL)
        except Exception:
            model_name = DEFAULT_MODEL

    pricing = MODEL_PRICING.get(model_name, MODEL_PRICING[DEFAULT_MODEL])
    return model_name, pricing["input"], pricing["output"]

GEMINI_MODEL, _PRICE_INPUT_PER_1M, _PRICE_OUTPUT_PER_1M = load_active_model()


# ── Gemini Setup ─────────────────────────────────────────────────────────────
def setup_gemini() -> genai.Client:
    api_key = os.environ.get("GENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GENAI_API_KEY is not set.\n"
            "Add it as a Windows Environment Variable or create a .env file."
        )
    return genai.Client(api_key=api_key)


# ── Database Helpers ──────────────────────────────────────────────────────────
def ensure_views(conn: sqlite3.Connection) -> None:
    """Create or refresh analytical views from views.sql."""
    with open(VIEWS_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def fetch_anomalies_by_manager(conn: sqlite3.Connection) -> dict:
    """
    Query vw_anomaly_log and group flagged transactions by manager.
    Returns: { (manager_name, manager_email, department): [list of anomaly dicts] }
    """
    cursor = conn.execute("""
        SELECT
            manager_name,
            manager_email,
            department,
            employee_name,
            merchant,
            amount,
            currency,
            amount_eur,
            timestamp,
            flag_reason
        FROM vw_anomaly_log
        ORDER BY manager_name, flag_reason, timestamp
    """)

    grouped: dict = defaultdict(list)
    for row in cursor.fetchall():
        key = (row[0], row[1], row[2])   # (manager_name, manager_email, department)
        grouped[key].append({
            "employee":    row[3],
            "merchant":    row[4],
            "amount":      row[5],
            "currency":    row[6],
            "amount_eur":  row[7],
            "timestamp":   row[8],
            "flag":        row[9],
        })
    return dict(grouped)


# ── Prompt Engineering ────────────────────────────────────────────────────────
FLAG_EXPLANATIONS = {
    "DOUBLE_SWIPE":       "Possible duplicate charge — the same merchant was charged twice within minutes.",
    "WEEKEND_SPIKE":      "Unusually high-value transaction recorded on a weekend.",
    "OVERSPEND":          "Employee has exceeded their monthly budget allocation.",
    "UNUSUAL_CURRENCY":   "Transaction recorded in RSD (Serbian Dinar) — unexpected for a Berlin-based operation.",
}

def build_prompt(manager_name: str, department: str, anomalies: list) -> str:
    lines = []
    for i, a in enumerate(anomalies, start=1):
        flag_note = FLAG_EXPLANATIONS.get(a["flag"], a["flag"])
        lines.append(
            f"  {i}. [{a['flag']}] {a['employee']}  |  {a['merchant']}  |  "
            f"{a['amount']:,.2f} {a['currency']} ({a['amount_eur']:.2f} EUR)  |  "
            f"{a['timestamp']}  |  Note: {flag_note}"
        )
    transaction_block = "\n".join(lines)

    return f"""You are a corporate finance compliance assistant working for a Berlin-based fintech company.

Your task: Write a professional, concise email alert addressed to a department manager.
The email should inform them about flagged transactions in their team's corporate card activity and request a review.

--- CONTEXT ---
Manager:    {manager_name}
Department: {department}
Report date: {datetime.now().strftime("%d %B %Y")}

Flagged Transactions ({len(anomalies)} total):
{transaction_block}

--- INSTRUCTIONS ---
- Write in English only
- Professional, respectful, but direct tone — this is a compliance alert
- Open with a brief introduction explaining why this email was sent
- Present the flagged items clearly (you may use a short numbered list)
- For each flag type, briefly explain what it means in plain language
- Request the manager to review and confirm or dispute each item within 48 business hours
- Mention that unresolved flags may be escalated to the Finance Director
- Close with sign-off: "Spend Analytics System | Finance Operations | {datetime.now().strftime("%d %B %Y")}"
- Do NOT invent any data not listed above
- Do NOT use markdown formatting — plain text only

Write the complete email now:"""


# ── Run Log ──────────────────────────────────────────────────────────────────
def save_run_log(run_meta: dict) -> str:
    """
    Append this run's metadata to output/run_log.json.
    Creates the file if it doesn't exist; appends to the existing list.
    """
    os.makedirs(os.path.dirname(RUN_LOG_PATH), exist_ok=True)

    # Load existing log or start fresh
    if os.path.exists(RUN_LOG_PATH):
        try:
            with open(RUN_LOG_PATH, "r", encoding="utf-8") as f:
                log_data = json.load(f)
            if not isinstance(log_data, list):
                log_data = [log_data]   # migrate old single-object format
        except (json.JSONDecodeError, ValueError):
            log_data = []
    else:
        log_data = []

    log_data.append(run_meta)

    with open(RUN_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)

    return RUN_LOG_PATH


# ── Output ────────────────────────────────────────────────────────────────────
def save_alert(manager_name: str, manager_email: str, department: str, email_body: str) -> str:
    os.makedirs(OUT_DIR, exist_ok=True)
    date_str   = datetime.now().strftime("%Y-%m-%d")
    safe_dept  = department.replace(" ", "_").lower()
    filename   = f"alert_{safe_dept}_{date_str}.txt"
    filepath   = os.path.join(OUT_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("DRAFT ALERT -- SIMULATION ONLY -- NOT SENT\n")
        f.write("=" * 60 + "\n")
        f.write(f"TO:          {manager_name} <{manager_email}>\n")
        f.write(f"DEPARTMENT:  {department}\n")
        f.write(f"GENERATED:   {datetime.now().isoformat()}\n")
        f.write(f"SUBJECT:     [ACTION REQUIRED] Corporate Card Anomalies Detected -- {department}\n")
        f.write("=" * 60 + "\n\n")
        f.write(email_body.strip())
        f.write("\n")

    return filepath


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    print("\n[START] Corporate Spend Analytics -- AI Alert Notifier")
    print("=" * 50)

    run_start = _time.monotonic()
    run_timestamp = datetime.now().isoformat()
    run_id = str(uuid.uuid4())

    # 1. Connect to database
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] Database not found: {DB_PATH}")
        print("   Run 'python scripts/generate_data.py' first.\n")
        return

    conn = sqlite3.connect(DB_PATH)

    # 2. Refresh views
    print("\n[1/4] Loading analytical views...")
    t0 = _time.monotonic()
    ensure_views(conn)
    db_duration = round(_time.monotonic() - t0, 3)

    # 3. Load anomalies
    print("[2/4] Fetching flagged transactions from vw_anomaly_log...")
    grouped = fetch_anomalies_by_manager(conn)
    conn.close()

    total_flags = sum(len(v) for v in grouped.values())
    if not grouped:
        print("[OK] No flagged transactions found. Nothing to report.\n")
        return
    print(f"   Found {total_flags} flagged transaction(s) across {len(grouped)} manager(s)")

    # 4. Setup Gemini
    print("\n[3/4] Connecting to Gemini API...")
    client = setup_gemini()
    print(f"   Model: {GEMINI_MODEL}")

    # 5. Generate + save one alert per manager
    print(f"\n[4/4] Drafting email alerts...\n")
    saved_files = []
    api_call_logs = []   # token tracking per manager

    for (manager_name, manager_email, department), anomalies in grouped.items():
        print(f"   >> {manager_name}  ({department})  --  {len(anomalies)} flag(s)...")
        prompt = build_prompt(manager_name, department, anomalies)

        call_start = _time.monotonic()
        call_status = "success"
        prompt_tokens = output_tokens = total_tokens = 0

        try:
            last_exc = None
            for attempt in range(1, 4):
                try:
                    response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
                    email_body = response.text

                    # ── Token usage logging ──────────────────────────────────
                    usage = getattr(response, "usage_metadata", None)
                    if usage:
                        prompt_tokens  = getattr(usage, "prompt_token_count", 0) or 0
                        output_tokens  = getattr(usage, "candidates_token_count", 0) or 0
                        total_tokens   = getattr(usage, "total_token_count", 0) or (prompt_tokens + output_tokens)
                    break
                except Exception as exc:
                    last_exc = exc
                    if "503" in str(exc) and attempt < 3:
                        wait = attempt * 5
                        print(f"      [RETRY {attempt}/3] 503 error, waiting {wait}s...")
                        _time.sleep(wait)
                    else:
                        raise

            call_duration = round(_time.monotonic() - call_start, 3)
            filepath = save_alert(manager_name, manager_email, department, email_body)
            saved_files.append(filepath)
            print(f"      [OK] Saved -> {os.path.relpath(filepath, ROOT)}  "
                  f"| tokens: {total_tokens} ({prompt_tokens} in / {output_tokens} out)")

        except Exception as exc:
            call_duration = round(_time.monotonic() - call_start, 3)
            call_status = "error"
            email_body = ""
            print(f"      [ERROR] {manager_name}: {exc}")

        api_call_logs.append({
            "manager":          manager_name,
            "department":       department,
            "flags_count":      len(anomalies),
            "prompt_tokens":    prompt_tokens,
            "output_tokens":    output_tokens,
            "total_tokens":     total_tokens,
            "duration_seconds": call_duration,
            "status":           call_status,
        })

    # 6. Build + save run log
    total_prompt  = sum(c["prompt_tokens"]  for c in api_call_logs)
    total_output  = sum(c["output_tokens"]  for c in api_call_logs)
    total_tok     = sum(c["total_tokens"]   for c in api_call_logs)
    est_cost_usd  = round(
        (total_prompt  / 1_000_000) * _PRICE_INPUT_PER_1M +
        (total_output / 1_000_000) * _PRICE_OUTPUT_PER_1M,
        6
    )
    total_duration = round(_time.monotonic() - run_start, 3)

    run_meta = {
        "run_id":                 run_id,
        "timestamp":              run_timestamp,
        "model":                  GEMINI_MODEL,
        "total_duration_seconds": total_duration,
        "db_query_seconds":       db_duration,
        "total_flags_processed":  total_flags,
        "alerts_saved":           len(saved_files),
        "api_calls":              api_call_logs,
        "totals": {
            "prompt_tokens":       total_prompt,
            "output_tokens":       total_output,
            "total_tokens":        total_tok,
            "estimated_cost_usd":  est_cost_usd,
            "api_calls_count":     len(api_call_logs),
        },
    }
    log_path = save_run_log(run_meta)
    print(f"\n   [LOG] Run log saved -> {os.path.relpath(log_path, ROOT)}")
    print(f"   [LOG] Total tokens: {total_tok}  "
          f"({total_prompt} in / {total_output} out)  "
          f"| Est. cost: ${est_cost_usd:.6f} USD")

    # 7. Summary
    print(f"\n{'=' * 50}")
    print(f"[DONE] {len(saved_files)} alert draft(s) saved to output/alerts/")
    print(f"[DONE] Run completed in {total_duration}s")
    print("   NOTE: SIMULATION ONLY -- no real emails were sent.\n")


if __name__ == "__main__":
    main()
