# Persistent Memory

Action-oriented working rules, preferences, recurring workflows, and links to relevant Knowledge live here.

---

## Project Context & Reference Guides

- **Pipeline & System Architecture**: Refer to [Pipeline Architecture](knowledge/architecture/pipeline.md) for the full data flow, SQL views, and Python script roles.
- **Analytics Metrics & Thresholds**: Refer to [Metrics Framework](knowledge/analytics/metrics_framework.md) for flag type definitions, KPI calculations, and alert thresholds.

---

## Core Rules & Preferences

1. **Environment Variables**:
   - The application strictly uses `GENAI_API_KEY`. Ensure it is defined in the active `.env` file or Windows Environment Variables.
   - Do NOT use or fall back to `GEMINI_API_KEY`.

2. **Git Commit Standards**:
   - All commit messages must follow [Conventional Commits v1.0.0](https://www.conventionalcommits.org/en/v1.0.0/) (`<type>(<scope>): <description>`).
   - Scopes used: `pipeline`, `dashboard`, `notifier`, `server`, `sql`, `agents`, `docs`.

3. **Running the Pipeline**:
   - Generate data: `python scripts/generate_data.py`
   - Run AI notifier (also writes `output/run_log.json`): `python scripts/ai_notifier.py`
   - Start web server: `python scripts/dashboard_server.py` → `http://localhost:8001` (port 8001 avoids conflict with StockMonitor on 8000)

4. **Dashboard Architecture**:
   - Single `dashboard/index.html` with two tabs: Analytics (Tab 1) and Agent Observability (Tab 2).
   - Server exposes `/api/data` (spend DB data) and `/api/run-log` (token/timing data).

5. **Token Tracking**:
   - `ai_notifier.py` logs `usage_metadata` (prompt_token_count, candidates_token_count, total_token_count) per Gemini API call.
   - Aggregated results written to `output/run_log.json` after each run.

6. **Gemini Model**:
   - Production model: `gemini-2.5-flash-lite` — do not upgrade without documenting cost impact.

7. **Generated Artifact Exclusions**:
   - `data/spend.db`, `output/alerts/`, `output/run_log.json`, `venv/`, `__pycache__/`, `.env` are in `.gitignore` and excluded from source control.
