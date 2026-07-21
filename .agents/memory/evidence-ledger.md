# Evidence Ledger

A running log of confirmed facts, resolved decisions, and observed behaviors in this project.
Use this to avoid re-investigating already-settled questions.

---

## Architecture Decisions (Confirmed)

| Date | Decision | Evidence / Rationale |
|---|---|---|
| 2026-07-21 | Dashboard: one `index.html`, two tabs | User confirmed — unified UX, single server endpoint |
| 2026-07-21 | Data source: Python server `/api/data` | User confirmed — clean separation, avoids CORS/file:// issues |
| 2026-07-21 | Token tracking: extend `ai_notifier.py` | User confirmed — minimal footprint, logs to `output/run_log.json` |
| 2026-07-21 | Dashboard 2 data: dynamic numbers + fixed recommendations | User confirmed — actionable insights without over-engineering |
| 2026-07-21 | Gemini model: `gemini-2.5-flash-lite` | Already in use — optimal cost/quality for structured compliance emails |

## Known Behaviors

- `generate_data.py` uses `random.seed(42)` — dataset is reproducible but exchange rates are live.
- `ai_notifier.py` retries up to 3x on 503 errors with exponential backoff (5s, 10s).
- Excel `analysis.xlsx` requires SQLite ODBC driver (64-bit) and manual path update in Power Query.
- `vw_anomaly_log` sorts by `timestamp DESC` — newest anomalies appear first.

## Verified File Paths

- DB: `data/spend.db`
- Schema: `sql/schema.sql`
- Views: `sql/views.sql`
- Alerts output: `output/alerts/`
- Run log: `output/run_log.json` (created after first `ai_notifier.py` run)
- Web dashboard: `dashboard/index.html`
- Server: `scripts/dashboard_server.py`
