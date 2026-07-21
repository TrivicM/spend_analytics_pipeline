# Pipeline & System Architecture

## Overview

The Spend Analytics Pipeline is a **corporate expense automation system** that simulates corporate card transactions, detects anomalies, drafts AI-powered email alerts, and presents all results in a web-based dashboard.

**"Project within a project"**: The pipeline itself is the core product. The Meta/Observability dashboard layer documents *how to use the AI tooling cheaply and correctly* — making cost governance a first-class deliverable alongside the analytics.

---

## System Architecture

```
[generate_data.py]
      │  • Fetches live EUR/USD/RSD exchange rates
      │  • Creates data/spend.db (schema.sql)
      │  • Inserts 15 employees, 200+ transactions, 4 anomaly types
      ▼
[data/spend.db]  ──────────────────────────────────────────────┐
      │                                                         │
      │  SQL Views (views.sql):                                 │
      │    vw_anomaly_log       → flagged txns + manager info  │
      │    vw_overspend_summary → employees over budget         │
      │    vw_department_spend  → aggregated by dept            │
      │    vw_currency_breakdown→ EUR/USD/RSD volumes           │
      │                                                         │
      ├──────────────────────────────────┐                      │
      ▼                                  ▼                      │
[ai_notifier.py]                  [dashboard_server.py]  ◄─────┘
      │  • Reads vw_anomaly_log          │  • Serves /api/data
      │  • Groups by manager             │  • Serves /api/run-log
      │  • Calls Gemini API (per dept)   │  • Serves dashboard/index.html
      │  • Logs token usage              │  • Runs on http://localhost:8000
      │                                  ▼
      ├── output/alerts/*.txt     [dashboard/index.html]
      └── output/run_log.json         Tab 1: Analytics Dashboard
                                      Tab 2: Agent Observability
```

---

## Script Roles

### `scripts/generate_data.py`
- **Run**: `python scripts/generate_data.py`
- **Output**: `data/spend.db`
- **Seed**: `random.seed(42)` — reproducible dataset, live exchange rates
- **Anomalies injected**:
  - `DOUBLE_SWIPE` — 10 pairs (20 transactions)
  - `WEEKEND_SPIKE` — 8 transactions (>500 EUR on Sat/Sun)
  - `UNUSUAL_CURRENCY` — 6 RSD transactions
  - `OVERSPEND` — 4 employees forced over budget

### `scripts/ai_notifier.py`
- **Run**: `python scripts/ai_notifier.py`
- **Requires**: `GENAI_API_KEY`, `data/spend.db`
- **Model**: `gemini-2.5-flash-lite`
- **Output**: `output/alerts/<dept>_<date>.txt` (one per manager), `output/run_log.json`
- **Token logging**: `response.usage_metadata.prompt_token_count`, `candidates_token_count`, `total_token_count`
- **Retry logic**: Up to 3 attempts on 503 errors (backoff: 5s, 10s)

### `scripts/dashboard_server.py`
- **Run**: `python scripts/dashboard_server.py`
- **Port**: 8000
- **Endpoints**:
  - `GET /` → serves `dashboard/index.html`
  - `GET /api/data` → JSON: all spend DB metrics (anomalies, dept spend, budgets, currencies)
  - `GET /api/run-log` → JSON: contents of `output/run_log.json`

---

## SQL Views

| View | Source tables | Purpose | Used by |
|---|---|---|---|
| `vw_anomaly_log` | transactions + employees | Flagged txns enriched with manager info | ai_notifier.py, Dashboard Tab 1 |
| `vw_overspend_summary` | budgets + employees | Employees exceeding monthly budget | Dashboard Tab 1 |
| `vw_department_spend` | transactions + employees | Aggregated spend per department | Dashboard Tab 1 |
| `vw_currency_breakdown` | transactions | EUR/USD/RSD volume breakdown | Dashboard Tab 1 |

---

## Dashboard Architecture

### Tab 1 — Analytics Dashboard
**Audience**: Finance analysts, compliance officers, department managers
**Data source**: `/api/data` (Python server queries `spend.db` live)

Sections:
1. **KPI Cards** — Total Spend, Flagged Count, Employees Over Budget, Currency Count
2. **Anomaly Log** — Filterable/sortable table (by department, flag type)
3. **Department Spend** — Horizontal bar chart
4. **Budget vs. Actual** — Progress bars per employee (red if overspent)
5. **Currency Breakdown** — Donut chart + volume table

### Tab 2 — Agent Observability
**Audience**: Pipeline operator, manager reviewing AI tooling costs
**Data source**: `/api/run-log` (serves `output/run_log.json`)

Sections:
1. **Run History** — Table of all runs: timestamp, total time, status
2. **Token Usage** — Stacked bar (input vs output tokens) per department per run
3. **Cost Estimation** — Calculated from token counts × Gemini pricing
4. **Optimization Recommendations** — Fixed, prioritized list (see Metrics Framework)
5. **Model Benchmark** — Simulated comparison table (Flash Lite vs Flash vs Pro)

---

## "Project Within a Project" Narrative

```
CORE:   Automated spend analytics pipeline using Gemini AI
           ↓
META:   Transparent AI cost governance layer
           • How much does each run cost?
           • Which prompts consume the most tokens?
           • What are the top 5 ways to reduce cost?
           • When is Flash Lite sufficient vs. Flash/Pro?
```

This dual-layer design demonstrates that the builder understands not just *how to use AI APIs*, but *how to govern, measure, and optimize AI tooling costs* — a critical operations competency.
