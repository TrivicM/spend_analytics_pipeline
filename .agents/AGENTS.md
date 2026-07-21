# AGENTS.md — Spend Analytics Pipeline

Project-level rules, workflow instructions, and conventions for any AI agent working on this codebase.

---

## 1. Project Overview

A **corporate spend analytics automation pipeline** for a fictional Berlin-based fintech company.
The pipeline simulates card transactions, detects anomalies, and drafts AI-powered email alerts.
It also ships a **web dashboard** with two layers:
- **Tab 1 — Analytics Dashboard**: KPIs, anomaly log, budget vs. actual, department spend
- **Tab 2 — Agent Observability**: token usage, run cost, optimization recommendations

See [Pipeline Architecture](memory/knowledge/architecture/pipeline.md) for full system design.

---

## 2. Environment Variables

- `GENAI_API_KEY` — required for Gemini API calls in `ai_notifier.py`
- Set as a Windows Environment Variable OR in a local `.env` file (never committed)
- Do NOT use `GEMINI_API_KEY` — the codebase strictly uses `GENAI_API_KEY`

---

## 3. How to Run the Pipeline

```bash
# Step 1: Generate the database (creates data/spend.db)
python scripts/generate_data.py

# Step 2: Run AI notifier (reads spend.db, calls Gemini, writes output/alerts/ and output/run_log.json)
python scripts/ai_notifier.py

# Step 3: Start the web dashboard server
python scripts/dashboard_server.py
# Opens: http://localhost:8001
```

---

## 4. Git Commit Standards

All commit messages must follow [Conventional Commits v1.0.0](https://www.conventionalcommits.org/en/v1.0.0/):

```
<type>(<scope>): <description>

<body>
```

**Types used in this project:**
- `feat` — new feature (MINOR)
- `fix` — bug fix (PATCH)
- `docs` — documentation only
- `refactor` — code restructure, no functional change
- `chore` — tooling, .gitignore, dependencies

**Scopes:** `pipeline`, `dashboard`, `notifier`, `server`, `sql`, `agents`, `docs`

---

## 5. Project Structure

```
spend_analytics_pipeline/
├── scripts/
│   ├── generate_data.py      # Data simulation + DB population (uses urllib, no requests dep)
│   ├── ai_notifier.py        # Gemini API alert drafter + token logger
│   └── dashboard_server.py   # Python stdlib HTTP server (:8001)
├── sql/
│   ├── schema.sql            # Table definitions
│   └── views.sql             # Analytical views (4 views)
├── data/
│   └── spend.db              # Generated SQLite database
├── dashboard/
│   └── index.html            # Web dashboard: Tab 1 (Analytics) + Tab 2 (Observability)
├── output/
│   ├── alerts/               # Generated email draft .txt files
│   └── run_log.json          # Token usage + timing log per run
├── docs/
│   └── assets/               # Dashboard screenshots and animated demo WEBP
├── .agents/
│   ├── AGENTS.md             # This file
│   ├── memory/
│   │   ├── MEMORY.md
│   │   └── knowledge/
│   └── skills/
├── .env.example
├── requirements.txt
└── README.md
```

---

## 6. Key Design Decisions (locked)

| Decision | Choice | Rationale |
|---|---|---|
| Dashboard format | One `index.html`, two tabs | Unified UX, single server endpoint |
| Data source for web dashboard | Python server `/api/data` endpoint | Clean separation, no CORS/file:// issues |
| Token tracking | Extended in `ai_notifier.py` | Minimal footprint, logs to `output/run_log.json` |
| Dashboard 2 data | Dynamic numbers + fixed recommendations | Actionable insights without over-engineering |
| Gemini model | `gemini-2.5-flash-lite` | Optimal cost/quality for structured compliance emails |
| HTTP client in generate_data.py | `urllib.request` + `ssl` (stdlib) | Eliminates `requests` dep; works in all envs without pip |
| GDPR Privacy Mode | CSS `blur(5px)` via `.privacy-mode-active` on `body` | Tab 1: names blurred in table, budget list & modal; persists in `localStorage` |
| Model Switcher | Tab 2 benchmark table with `ⓘ` popovers | Select active model at runtime; saves to `output/config.json` |
| Dashboard port | `8001` | Avoids conflicts with common dev servers on `8000` |

---

## 7. Generated Artifact Exclusions (gitignore)

- `data/spend.db` — regenerated on each run
- `output/alerts/` — generated email drafts
- `output/run_log.json` — generated run metadata
- `venv/`, `.venv/`, `__pycache__/`, `.env`
- `.agents/memory/` — agent working memory, not source code

---

## 8. Known Environment Notes

- Two virtual environments exist locally: `venv/` (main, all deps installed) and `.venv/` (uv-managed, also fully installed as of 2026-07-21).
- Always run scripts from the **project root**, not from inside `scripts/` subfolder (avoids duplicate path issues).
- `generate_data.py` uses `ssl._create_unverified_context()` for Windows SSL certificate compatibility.
- `pyproject.toml`, `.python-version`, `uv.lock` are present locally but **not tracked in git** (no decision yet on whether to include).

---

## 9. Git Branch Strategy

- Active development: `feature/web-dashboard-and-agent-infra`
- Stable / demo-ready: `master`
- Workflow: commit + push to feature branch → merge to master → push master
- Both branches are always kept in sync after each feature session.
