# -*- coding: utf-8 -*-
"""
dashboard_server.py  |  Corporate Spend Analytics Pipeline
===========================================================
Zero-dependency HTTP server that serves the web dashboard and
exposes JSON API endpoints for live data.

Endpoints:
  GET /              → dashboard/index.html
  GET /api/data      → all spend metrics from spend.db (JSON)
  GET /api/run-log   → token usage + run history from output/run_log.json (JSON)
  GET /api/config    → active model config
  POST /api/config   → update active model config

Auto-init:
  If data/spend.db is missing at startup, the server automatically loads
  sql/demo_seed.sql to provide a working demo dataset without any manual steps.

Usage:
  python scripts/dashboard_server.py
  → http://localhost:8001
"""

import sys
import os
import json
import sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# Force UTF-8 output on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PORT = 8001
ROOT = os.path.join(os.path.dirname(__file__), "..")
DB_PATH      = os.path.join(ROOT, "data", "spend.db")
SEED_PATH    = os.path.join(ROOT, "sql", "demo_seed.sql")
SCHEMA_PATH  = os.path.join(ROOT, "sql", "schema.sql")
VIEWS_PATH   = os.path.join(ROOT, "sql", "views.sql")
DASHBOARD    = os.path.join(ROOT, "dashboard", "index.html")
RUN_LOG_PATH = os.path.join(ROOT, "output", "run_log.json")


# ── Demo-Ready Auto-Init ──────────────────────────────────────────────────────

def init_demo_db() -> bool:
    """Load demo_seed.sql + schema + views into a fresh spend.db.

    Called automatically at server startup when data/spend.db is missing.
    Returns True if the database was initialised successfully.
    """
    if not os.path.exists(SEED_PATH):
        print("   ⚠️  sql/demo_seed.sql not found — cannot auto-init.")
        print("   Run: python scripts/generate_data.py")
        return False

    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)

        # 1. Apply schema (creates tables)
        if os.path.exists(SCHEMA_PATH):
            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                conn.executescript(f.read())

        # 2. Load seed data
        with open(SEED_PATH, "r", encoding="utf-8") as f:
            conn.executescript(f.read())

        # 3. Apply views
        if os.path.exists(VIEWS_PATH):
            with open(VIEWS_PATH, "r", encoding="utf-8") as f:
                conn.executescript(f.read())

        conn.commit()
        conn.close()

        row_count = sqlite3.connect(DB_PATH).execute(
            "SELECT COUNT(*) FROM transactions"
        ).fetchone()[0]
        print(f"   ✅ Demo database ready: {row_count} transactions loaded from demo_seed.sql")
        return True

    except Exception as exc:
        print(f"   ❌ Auto-init failed: {exc}")
        return False


# ── Database Queries ──────────────────────────────────────────────────────────

def query_spend_data() -> dict:
    """Query spend.db and return all dashboard metrics as a dict."""
    if not os.path.exists(DB_PATH):
        return {"error": "Database not found. Run generate_data.py first."}

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # allows dict-like access

    def rows_to_list(cursor_result) -> list:
        return [dict(row) for row in cursor_result.fetchall()]

    # ── Rebuild views to ensure they exist ───────────────────────────────────
    if os.path.exists(VIEWS_PATH):
        with open(VIEWS_PATH, "r", encoding="utf-8") as f:
            conn.executescript(f.read())

    # ── Anomaly Log ───────────────────────────────────────────────────────────
    anomalies = rows_to_list(conn.execute("""
        SELECT transaction_id, employee_name, department, manager_name,
               merchant, amount, currency, amount_eur, timestamp, flag_reason
        FROM vw_anomaly_log
        ORDER BY timestamp DESC
    """))

    # ── Department Spend ──────────────────────────────────────────────────────
    dept_spend = rows_to_list(conn.execute("""
        SELECT department, manager_name, total_transactions,
               total_spent_eur, avg_transaction_eur, flagged_count
        FROM vw_department_spend
        ORDER BY total_spent_eur DESC
    """))

    # ── Budget vs. Actual (all employees) ────────────────────────────────────
    budget_all = rows_to_list(conn.execute("""
        SELECT e.name AS employee_name,
               e.department,
               e.manager_name,
               b.month,
               b.allocated_eur,
               ROUND(b.spent_eur, 2) AS spent_eur,
               ROUND(b.spent_eur - b.allocated_eur, 2) AS delta_eur,
               ROUND((b.spent_eur / b.allocated_eur) * 100, 1) AS pct_used
        FROM budgets b
        JOIN employees e ON e.id = b.employee_id
        ORDER BY pct_used DESC
    """))

    # ── Currency Breakdown ────────────────────────────────────────────────────
    currencies = rows_to_list(conn.execute("""
        SELECT currency, transaction_count, total_eur_equivalent
        FROM vw_currency_breakdown
        ORDER BY total_eur_equivalent DESC
    """))

    # ── Summary KPIs ─────────────────────────────────────────────────────────
    kpi = dict(conn.execute("""
        SELECT
            COUNT(*)                             AS total_transactions,
            ROUND(SUM(amount_eur), 2)            AS total_spend_eur,
            SUM(is_flagged)                      AS total_flagged,
            ROUND(SUM(is_flagged) * 100.0 / COUNT(*), 1) AS flagged_pct
        FROM transactions
    """).fetchone())

    overspend_count = conn.execute("""
        SELECT COUNT(*) FROM vw_overspend_summary
    """).fetchone()[0]

    currency_count = conn.execute("""
        SELECT COUNT(DISTINCT currency) FROM transactions
    """).fetchone()[0]

    kpi["overspend_employee_count"] = overspend_count
    kpi["currency_count"] = currency_count

    # ── Top Merchants ─────────────────────────────────────────────────────────
    top_merchants = rows_to_list(conn.execute("""
        SELECT merchant,
               COUNT(*) AS transaction_count,
               ROUND(SUM(amount_eur), 2) AS total_eur
        FROM transactions
        GROUP BY merchant
        ORDER BY total_eur DESC
        LIMIT 8
    """))

    conn.close()

    return {
        "kpi":          kpi,
        "anomalies":    anomalies,
        "dept_spend":   dept_spend,
        "budget_all":   budget_all,
        "currencies":   currencies,
        "top_merchants": top_merchants,
    }


def load_run_log() -> list:
    """Load run_log.json or return empty list if not yet generated."""
    if not os.path.exists(RUN_LOG_PATH):
        return []
    try:
        with open(RUN_LOG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else [data]
    except (json.JSONDecodeError, ValueError):
        return []


CONFIG_PATH = os.path.join(ROOT, "output", "config.json")

def load_config() -> dict:
    """Load config.json or return default active_model."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"active_model": "gemini-2.5-flash-lite"}

def save_config(cfg: dict) -> bool:
    """Save config dict to config.json."""
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


# ── HTTP Handler ──────────────────────────────────────────────────────────────

class SpendDashboardHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        """Override to produce cleaner console output."""
        print(f"  [{self.command}] {self.path}  →  {args[1] if len(args) > 1 else ''}")

    def send_json(self, data: dict | list, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, filepath: str) -> None:
        with open(filepath, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path

        if path in ("/", "/index.html"):
            if os.path.exists(DASHBOARD):
                self.send_html(DASHBOARD)
            else:
                self.send_json({"error": "dashboard/index.html not found"}, 404)

        elif path == "/api/data":
            data = query_spend_data()
            self.send_json(data)

        elif path == "/api/run-log":
            data = load_run_log()
            self.send_json(data)

        elif path == "/api/config":
            cfg = load_config()
            self.send_json(cfg)

        else:
            self.send_json({"error": f"Unknown endpoint: {path}"}, 404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path

        if path == "/api/config":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                payload = json.loads(body.decode("utf-8"))
                if "active_model" in payload:
                    current = load_config()
                    current["active_model"] = payload["active_model"]
                    if save_config(current):
                        self.send_json({"status": "success", "config": current})
                        return
                self.send_json({"error": "Invalid payload"}, 400)
            except Exception as e:
                self.send_json({"error": str(e)}, 500)
        else:
            self.send_json({"error": f"Unknown endpoint: {path}"}, 404)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n[START] Corporate Spend Analytics — Dashboard Server")
    print("=" * 50)

    if not os.path.exists(DB_PATH):
        print("\n🔄 No database found — auto-loading demo seed data...")
        init_demo_db()

    server = HTTPServer(("localhost", PORT), SpendDashboardHandler)
    print(f"\n  Dashboard:  http://localhost:{PORT}/")
    print(f"  API Data:   http://localhost:{PORT}/api/data")
    print(f"  Run Log:    http://localhost:{PORT}/api/run-log")
    print("\n  Press Ctrl+C to stop.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[STOP] Server stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
