# -*- coding: utf-8 -*-
"""
generate_data.py  |  Corporate Spend Analytics Pipeline
========================================================
Simulates corporate card transactions for a fictional Berlin fintech company.
Fetches LIVE EUR exchange rates (no API key required).

What this script does:
  1. Fetches live EUR/USD and EUR/RSD exchange rates
  2. Creates (or recreates) data/spend.db with schema from sql/schema.sql
  3. Inserts 15 employees across 5 departments
  4. Generates ~180 normal transactions in EUR and USD
  5. Injects 4 types of controlled anomalies:
       - DOUBLE_SWIPE    : same merchant, same employee, within ~2 minutes
       - WEEKEND_SPIKE   : high-value transaction (>500 EUR) on Sat/Sun
       - UNUSUAL_CURRENCY: transaction in RSD (Serbian Dinar — unexpected in Berlin)
       - OVERSPEND       : employee's monthly spend exceeds allocated budget
  6. Updates the budgets table with actual spend totals

Usage:
  python scripts/generate_data.py
"""

import sys
import sqlite3
import random
import os
import requests
from datetime import datetime, timedelta
from faker import Faker

# Force UTF-8 output so emoji prints work on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ── Config ──────────────────────────────────────────────────────────────────
fake = Faker("de_DE")   # German locale for realistic names / merchants
random.seed(42)          # Fixed seed → reproducible dataset

ROOT = os.path.join(os.path.dirname(__file__), "..")
DB_PATH     = os.path.join(ROOT, "data", "spend.db")
SCHEMA_PATH = os.path.join(ROOT, "sql", "schema.sql")

SIMULATION_MONTH = "2025-06"
BASE_DATE        = datetime(2025, 6, 1)

# 5 departments with their managers (name, email)
DEPARTMENTS: dict[str, tuple[str, str]] = {
    "Marketing":   ("Sarah Mueller",   "sarah.mueller@company.de"),
    "Engineering": ("Thomas Becker",   "thomas.becker@company.de"),
    "Sales":       ("Anna Schmidt",    "anna.schmidt@company.de"),
    "Finance":     ("Klaus Wagner",    "klaus.wagner@company.de"),
    "Operations":  ("Lisa Hoffmann",   "lisa.hoffmann@company.de"),
}

# Realistic merchants per department
MERCHANTS: dict[str, list[str]] = {
    "Marketing":   ["Google Ads", "Meta Ads", "Canva Pro", "Adobe Creative Cloud", "Eventbrite", "LinkedIn Ads"],
    "Engineering": ["AWS", "GitHub Enterprise", "JetBrains", "Datadog", "Notion", "Figma"],
    "Sales":       ["Salesforce", "HubSpot", "Zoom Pro", "Lufthansa Business", "Hotel Adlon Berlin", "Uber Business"],
    "Finance":     ["Bloomberg Terminal", "Expensify", "DocuSign", "PwC Advisory", "Deloitte Germany", "KPMG"],
    "Operations":  ["DHL Express", "IKEA Business", "Staples Office", "Siemens Services", "DB Bahn", "WeWork Berlin"],
}


# ── Exchange Rates ───────────────────────────────────────────────────────────
def fetch_exchange_rates() -> dict[str, float]:
    """Fetch live EUR base rates via free public API (no key required)."""
    url = "https://api.exchangerate-api.com/v4/latest/EUR"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        rates_data = resp.json()["rates"]
        rates = {
            "EUR": 1.0,
            "USD": round(rates_data["USD"], 4),
            "RSD": round(rates_data["RSD"], 4),
        }
        print(f"   Live rates fetched  →  1 EUR = {rates['USD']} USD  |  1 EUR = {rates['RSD']} RSD")
        return rates
    except Exception as exc:
        print(f"   ⚠️  Could not fetch live rates ({exc}). Using fallback values.")
        return {"EUR": 1.0, "USD": 1.08, "RSD": 117.5}


# ── Database Setup ───────────────────────────────────────────────────────────
def create_database() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    return conn


# ── Employee Insertion ───────────────────────────────────────────────────────
def insert_employees(conn: sqlite3.Connection) -> list[tuple]:
    """Insert 3 employees per department (15 total). Returns list of employee tuples."""
    employees = []
    emp_id = 1
    for dept, (manager_name, manager_email) in DEPARTMENTS.items():
        for _ in range(3):
            budget = random.choice([1500.0, 2000.0, 2500.0, 3000.0])
            employees.append((emp_id, fake.name(), dept, manager_name, manager_email, budget))
            emp_id += 1

    conn.executemany(
        "INSERT INTO employees (id, name, department, manager_name, manager_email, monthly_budget_eur) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        employees,
    )
    conn.commit()
    print(f"   Inserted {len(employees)} employees across {len(DEPARTMENTS)} departments")
    return employees


# ── Budget Setup ─────────────────────────────────────────────────────────────
def insert_budgets(conn: sqlite3.Connection, employees: list[tuple]) -> None:
    budgets = [(emp[0], SIMULATION_MONTH, emp[5]) for emp in employees]
    conn.executemany(
        "INSERT INTO budgets (employee_id, month, allocated_eur) VALUES (?, ?, ?)",
        budgets,
    )
    conn.commit()


# ── Transaction Generation ───────────────────────────────────────────────────
def generate_transactions(
    conn: sqlite3.Connection,
    employees: list[tuple],
    rates: dict[str, float],
) -> None:
    transactions: list[tuple] = []
    employee_spend: dict[int, float] = {emp[0]: 0.0 for emp in employees}
    tx_id = 1

    # Weekend days in June 2025 (0-indexed offset from June 1)
    weekend_offsets = [0, 6, 7, 13, 14, 20, 21, 27, 28]  # Sat & Sun

    def make_weekday_dt() -> datetime:
        """Random weekday timestamp in June 2025."""
        offset = random.randint(0, 27)
        while offset in weekend_offsets:
            offset = random.randint(0, 27)
        return BASE_DATE + timedelta(
            days=offset,
            hours=random.randint(8, 18),
            minutes=random.randint(0, 59),
        )

    # ── 1. Normal transactions (EUR + USD mix) ────────────────────────────
    for _ in range(180):
        emp = random.choice(employees)
        emp_id, _, dept, _, _, _ = emp
        currency = random.choices(["EUR", "USD"], weights=[80, 20])[0]
        amount = round(random.uniform(15.0, 480.0), 2)
        amount_eur = round(amount / rates[currency], 2) if currency != "EUR" else amount
        dt = make_weekday_dt()

        employee_spend[emp_id] = round(employee_spend[emp_id] + amount_eur, 2)
        transactions.append((tx_id, emp_id, random.choice(MERCHANTS[dept]),
                              amount, currency, amount_eur, dt.isoformat(), 0, None))
        tx_id += 1

    # ── 2. DOUBLE_SWIPE anomalies (10 pairs = 20 transactions) ───────────
    for _ in range(10):
        emp = random.choice(employees)
        emp_id, _, dept, _, _, _ = emp
        merchant = random.choice(MERCHANTS[dept])
        amount = round(random.uniform(50.0, 350.0), 2)
        dt = make_weekday_dt()
        dt2 = dt + timedelta(minutes=random.randint(1, 3))

        for ts in [dt, dt2]:
            employee_spend[emp_id] = round(employee_spend[emp_id] + amount, 2)
            transactions.append((tx_id, emp_id, merchant, amount, "EUR", amount,
                                  ts.isoformat(), 1, "DOUBLE_SWIPE"))
            tx_id += 1

    # ── 3. WEEKEND_SPIKE anomalies (8 transactions) ───────────────────────
    for _ in range(8):
        emp = random.choice(employees)
        emp_id, _, dept, _, _, _ = emp
        amount = round(random.uniform(520.0, 1400.0), 2)
        offset = random.choice(weekend_offsets)
        dt = BASE_DATE + timedelta(
            days=offset, hours=random.randint(10, 21), minutes=random.randint(0, 59)
        )
        employee_spend[emp_id] = round(employee_spend[emp_id] + amount, 2)
        transactions.append((tx_id, emp_id, random.choice(MERCHANTS[dept]),
                              amount, "EUR", amount, dt.isoformat(), 1, "WEEKEND_SPIKE"))
        tx_id += 1

    # ── 4. UNUSUAL_CURRENCY: RSD transactions (6 transactions) ───────────
    rsd_merchants = ["Merkator d.o.o.", "Idea Market Beograd", "NIS Petrol d.o.o.",
                     "Comtrade Group doo", "MTS Telekom doo", "Delhaize Serbia doo"]
    for i in range(6):
        emp = random.choice(employees)
        emp_id = emp[0]
        amount_rsd = round(random.uniform(4000.0, 55000.0), 2)
        amount_eur = round(amount_rsd / rates["RSD"], 2)
        dt = make_weekday_dt()
        employee_spend[emp_id] = round(employee_spend[emp_id] + amount_eur, 2)
        transactions.append((tx_id, emp_id, rsd_merchants[i],
                              amount_rsd, "RSD", amount_eur, dt.isoformat(), 1, "UNUSUAL_CURRENCY"))
        tx_id += 1

    # ── 5. OVERSPEND: force 4 employees over budget ───────────────────────
    overspend_targets = random.sample(employees, 4)
    for emp in overspend_targets:
        emp_id, _, dept, _, _, budget = emp
        current = employee_spend[emp_id]
        # Amount needed to exceed budget by 150–600 EUR
        overshoot = round(random.uniform(150.0, 600.0), 2)
        excess_amount = max(50.0, round(budget - current + overshoot, 2))
        dt = BASE_DATE + timedelta(days=random.randint(20, 27), hours=random.randint(9, 17))
        employee_spend[emp_id] = round(employee_spend[emp_id] + excess_amount, 2)
        transactions.append((tx_id, emp_id, random.choice(MERCHANTS[dept]),
                              excess_amount, "EUR", excess_amount, dt.isoformat(), 1, "OVERSPEND"))
        tx_id += 1

    # ── Insert all transactions ───────────────────────────────────────────
    conn.executemany(
        "INSERT INTO transactions "
        "(id, employee_id, merchant, amount, currency, amount_eur, timestamp, is_flagged, flag_reason) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        transactions,
    )

    # ── Update budgets.spent_eur ──────────────────────────────────────────
    for emp_id, spent in employee_spend.items():
        conn.execute(
            "UPDATE budgets SET spent_eur = ? WHERE employee_id = ?",
            (round(spent, 2), emp_id),
        )

    conn.commit()

    flagged = sum(1 for t in transactions if t[7] == 1)
    print(f"   Inserted {len(transactions)} transactions  "
          f"({len(transactions) - flagged} normal  |  {flagged} flagged)")


# ── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    print("\n[START] Corporate Spend Analytics -- Data Generator")
    print("=" * 50)

    print("\n[1/5] Fetching live EUR exchange rates...")
    rates = fetch_exchange_rates()

    print("\n[2/5] Creating SQLite database...")
    conn = create_database()

    print("\n[3/5] Inserting employees...")
    employees = insert_employees(conn)

    print("\n[4/5] Setting up monthly budgets...")
    insert_budgets(conn, employees)

    print("\n[5/5] Generating transactions + anomalies...")
    generate_transactions(conn, employees, rates)

    conn.close()
    print(f"\n[DONE] Database created: {DB_PATH}")
    print("   Next step: python scripts/ai_notifier.py\n")


if __name__ == "__main__":
    main()
