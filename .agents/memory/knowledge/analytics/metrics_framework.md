# Analytics Metrics Framework

Reference document for all metrics, thresholds, flag definitions, KPI calculations, and token cost data used in this project.

---

## 1. Anomaly Flag Types

| Flag | Trigger Condition | Business Meaning | Dashboard Color |
|---|---|---|---|
| `DOUBLE_SWIPE` | Same merchant + same employee, within ~2 minutes | Possible duplicate charge / system error | 🟡 Amber |
| `WEEKEND_SPIKE` | Amount > 500 EUR on Saturday or Sunday | Unauthorized or unusual spend outside work hours | 🔴 Red |
| `OVERSPEND` | Employee total monthly spend > allocated budget | Budget compliance failure | 🟠 Orange |
| `UNUSUAL_CURRENCY` | Transaction in RSD (Serbian Dinar) | Unexpected geography for a Berlin-based company | 🟣 Purple |

---

## 2. KPI Definitions (Dashboard Tab 1)

### Total Spend (EUR)
- **Formula**: `SUM(amount_eur)` across all transactions in the simulation month
- **Threshold**: Informational — no alert; context only
- **Source**: `transactions` table

### Flagged Transaction Rate
- **Formula**: `COUNT(is_flagged=1) / COUNT(*) × 100`
- **Threshold**: 
  - > 5% → Yellow warning
  - > 15% → Red alert
- **Source**: `transactions` table

### Employees Over Budget
- **Formula**: `COUNT(*)` from `vw_overspend_summary`
- **Threshold**: 
  - 0 → Green
  - 1–2 → Yellow
  - 3+ → Red
- **Source**: `vw_overspend_summary`

### Currency Exposure Count
- **Formula**: `COUNT(DISTINCT currency)` in transactions
- **Context**: EUR = expected, USD = acceptable, RSD = flag for review
- **Source**: `vw_currency_breakdown`

### Overspend Amount (per employee)
- **Formula**: `spent_eur - allocated_eur`
- **Threshold**: any positive value triggers red progress bar in dashboard
- **Source**: `vw_overspend_summary`

---

## 3. Department Spend Metrics

From `vw_department_spend`:

| Column | Description |
|---|---|
| `total_transactions` | Count of all transactions in the department |
| `total_spent_eur` | Sum of amount_eur for the department |
| `avg_transaction_eur` | Average transaction size |
| `flagged_count` | Number of flagged transactions in the department |

---

## 4. Token Cost Reference (Gemini Pricing — as of Q3 2025)

> **Note**: These are used for cost estimation in Dashboard Tab 2. Always verify against current [Google AI pricing](https://ai.google.dev/pricing).

### Gemini 2.5 Flash Lite (production model)
| Metric | Rate |
|---|---|
| Input tokens | $0.00 / 1M tokens (free tier up to limits) |
| Output tokens | $0.00 / 1M tokens (free tier) |
| Paid input | ~$0.075 / 1M tokens |
| Paid output | ~$0.30 / 1M tokens |

### Gemini 2.5 Flash
| Metric | Rate |
|---|---|
| Input | ~$0.30 / 1M tokens |
| Output | ~$1.00 / 1M tokens |

### Gemini 2.5 Pro
| Metric | Rate |
|---|---|
| Input | ~$1.25 / 1M tokens (≤200K ctx) |
| Output | ~$10.00 / 1M tokens |

---

## 5. Cost Optimization Recommendations (Dashboard Tab 2)

Ordered by estimated impact:

| Priority | Recommendation | Estimated Impact |
|---|---|---|
| 🥇 1 | **Batch all anomalies into ONE API call** instead of N calls per manager | Reduces API calls from 5 to 1 (80% reduction in API overhead) |
| 🥈 2 | **Remove redundant prompt instructions** — FLAG_EXPLANATIONS repeat per transaction | ~20-30% input token reduction |
| 🥉 3 | **Use structured output** (JSON mode) instead of free-text emails | Faster, cheaper, more consistent results |
| 4 | **Cache view results** in JSON snapshot — skip DB query on re-runs with unchanged data | Eliminates all DB queries on repeat runs |
| 5 | **Shorten merchant/timestamp format** in prompt — full ISO timestamp is verbose | ~5-10% input token reduction |
| 6 | **Flash Lite is already optimal** for this use case — do not upgrade to Flash/Pro | Current model is the right choice |

---

## 6. Token Usage Schema (`output/run_log.json`)

```json
{
  "run_id": "uuid4",
  "timestamp": "ISO 8601",
  "model": "gemini-2.5-flash-lite",
  "total_duration_seconds": 12.4,
  "total_flags_processed": 38,
  "api_calls": [
    {
      "manager": "Sarah Mueller",
      "department": "Marketing",
      "flags_count": 8,
      "prompt_tokens": 1240,
      "output_tokens": 420,
      "total_tokens": 1660,
      "duration_seconds": 2.3,
      "status": "success"
    }
  ],
  "totals": {
    "prompt_tokens": 6100,
    "output_tokens": 2100,
    "total_tokens": 8200,
    "estimated_cost_usd": 0.0,
    "api_calls_count": 5
  }
}
```
