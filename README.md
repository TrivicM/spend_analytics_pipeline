# Corporate Spend Analytics & Automated Alert Pipeline

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat&logo=sqlite&logoColor=white)
![Excel](https://img.shields.io/badge/Excel-Power_Query-217346?style=flat&logo=microsoft-excel&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini_API-AI_Notifier-4285F4?style=flat&logo=google&logoColor=white)

A **portfolio project** demonstrating a complete corporate data automation loop:
simulated card transactions → relational database → Excel analytics dashboard → AI-drafted manager alerts.

> Built as a mini-version of an expense management system (directly relevant to fintech roles involving corporate card spend, e.g. Moss, Pleo, Spendesk).

---

## Architecture

```
Python: generate_data.py
        │  Simulates 200+ card transactions
        │  Injects 4 anomaly types (double swipes, weekend spikes, overspends, unusual currency)
        │  Fetches LIVE EUR/USD and EUR/RSD exchange rates
        ▼
SQLite: data/spend.db
        │  3 relational tables: employees · budgets · transactions
        │  4 analytical views: vw_anomaly_log · vw_overspend_summary · vw_department_spend · vw_currency_breakdown
        ├──────────────────────────────────────────────────────┐
        ▼                                                      ▼
Excel: dashboard/analysis.xlsx               Python: ai_notifier.py
       5 sheets with Power Query                     │  Reads vw_anomaly_log
       connections, pivot tables,                   │  Groups flags by manager
       and charts                                   │  Calls Gemini 1.5 Flash API
                                                    ▼
                                            output/alerts/*.txt
                                            Draft email alerts per department
                                            (simulation only — not sent)
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Data simulation | Python + Faker | Generates realistic employees, merchants, transactions |
| Currency conversion | [exchangerate-api.com](https://exchangerate-api.com) | Live EUR/USD/RSD rates (no API key needed) |
| Database | SQLite | Relational storage + SQL analytical views |
| Analytics | Excel 365 + Power Query | Dashboard with pivot tables and charts |
| AI automation | Gemini 1.5 Flash API | Drafts professional email alerts from anomaly data |

---

## Anomaly Types Simulated

| Flag | Description |
|------|-------------|
| `DOUBLE_SWIPE` | Same merchant charged twice within ~2 minutes (possible duplicate) |
| `WEEKEND_SPIKE` | High-value transaction (>500 EUR) recorded on Saturday or Sunday |
| `OVERSPEND` | Employee's total monthly spend exceeds their allocated budget |
| `UNUSUAL_CURRENCY` | Transaction in RSD (Serbian Dinar) — unexpected for a Berlin-based company |

---

## Setup & Usage

### 1. Clone the repository

```bash
git clone https://github.com/TrivicM/spend_analytics_pipeline.git
cd spend_analytics_pipeline
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
venv\Scripts\activate        # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set your Gemini API key

Add `GENAI_API_KEY` as a **Windows Environment Variable**
(Control Panel → System → Advanced → Environment Variables → New User Variable).

Or create a local `.env` file (never committed to Git):
```
GENAI_API_KEY=your_key_here
```

Get a free Gemini API key at: https://aistudio.google.com/app/apikey

### 5. Generate the database

```bash
python scripts/generate_data.py
```

Output: `data/spend.db` with 200+ transactions and injected anomalies.

### 6. Run the AI notifier

```bash
python scripts/ai_notifier.py
```

Output: one `.txt` alert draft per department manager in `output/alerts/`.

---

## Excel Dashboard Setup (Power Query)

> Requires: Excel 365 or Excel 2019+ on Windows + free [SQLite ODBC Driver](http://www.ch-werner.de/sqliteodbc/)

1. Install the 64-bit SQLite ODBC driver from the link above
2. Open `dashboard/analysis.xlsx`
3. Go to **Data → Queries & Connections**
4. For each query, right-click → **Edit** → update the file path to point to `data/spend.db`
5. Click **Close & Load** → **Refresh All**

### Dashboard sheets:

| Sheet | Data source | Visualization |
|-------|------------|---------------|
| Raw Transactions | `transactions` table | Full data table with filters |
| Department Summary | `vw_department_spend` | Bar chart: spend by department |
| Anomaly Log | `vw_anomaly_log` | Flagged transactions with manager info |
| Budget vs Actual | `vw_overspend_summary` | Column chart: allocated vs spent per employee |
| Currency Breakdown | `vw_currency_breakdown` | Pie chart: EUR / USD / RSD volumes |

---

## Project Structure

```
spend_analytics_pipeline/
├── scripts/
│   ├── generate_data.py      # Data simulation + DB population
│   └── ai_notifier.py        # Gemini API alert drafter
├── sql/
│   ├── schema.sql             # Table definitions
│   └── views.sql              # Analytical views
├── data/
│   └── spend.db               # Generated SQLite database
├── dashboard/
│   └── analysis.xlsx          # Excel Power Query dashboard
├── output/
│   └── alerts/                # Generated email draft .txt files
├── .env.example               # API key template
├── requirements.txt
└── README.md
```

---

## About This Project

This project was built as a **portfolio piece** to demonstrate the ability to:
- Design and implement a **relational database schema** with SQL views
- Orchestrate a **multi-step Python automation pipeline**
- Apply **AI API integration** (Gemini) for workflow automation
- Build **Excel analytics** with Power Query on a live SQLite source
- Work with **multi-currency financial data** and anomaly detection logic

> Skill narrative: *Orchestrating custom data automation pipelines by designing workflow logic and utilizing AI coding agents* — an approach that accurately reflects how modern operations and finance professionals leverage AI tools without overclaiming software engineering expertise.

---

## License

MIT — free to use and adapt.
