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
import sqlite3
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
VIEWS_PATH = os.path.join(ROOT, "sql", "views.sql")
OUT_DIR    = os.path.join(ROOT, "output", "alerts")

GEMINI_MODEL = "gemini-2.5-flash-lite"


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

    # 1. Connect to database
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] Database not found: {DB_PATH}")
        print("   Run 'python scripts/generate_data.py' first.\n")
        return

    conn = sqlite3.connect(DB_PATH)

    # 2. Refresh views
    print("\n[1/4] Loading analytical views...")
    ensure_views(conn)

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

    for (manager_name, manager_email, department), anomalies in grouped.items():
        print(f"   >> {manager_name}  ({department})  --  {len(anomalies)} flag(s)...")
        prompt = build_prompt(manager_name, department, anomalies)

        try:
            # Retry up to 3 times for transient 503 errors
            import time
            last_exc = None
            for attempt in range(1, 4):
                try:
                    response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
                    email_body = response.text
                    break
                except Exception as exc:
                    last_exc = exc
                    if "503" in str(exc) and attempt < 3:
                        wait = attempt * 5
                        print(f"      [RETRY {attempt}/3] 503 error, waiting {wait}s...")
                        time.sleep(wait)
                    else:
                        raise
            filepath = save_alert(manager_name, manager_email, department, email_body)
            saved_files.append(filepath)
            print(f"      [OK] Saved -> {os.path.relpath(filepath, ROOT)}")
        except Exception as exc:
            print(f"      [ERROR] {manager_name}: {exc}")

    # 6. Summary
    print(f"\n{'=' * 50}")
    print(f"[DONE] {len(saved_files)} alert draft(s) saved to output/alerts/")
    print("   NOTE: SIMULATION ONLY -- no real emails were sent.\n")


if __name__ == "__main__":
    main()
