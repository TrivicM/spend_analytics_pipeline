-- =============================================================
-- views.sql  |  Corporate Spend Analytics Pipeline
-- Analytical views used by Excel Power Query & ai_notifier.py
-- Re-run safely: each view is dropped before re-creation
-- =============================================================

DROP VIEW IF EXISTS vw_anomaly_log;
DROP VIEW IF EXISTS vw_overspend_summary;
DROP VIEW IF EXISTS vw_department_spend;
DROP VIEW IF EXISTS vw_currency_breakdown;

-- ---------------------------------------------------------------
-- vw_anomaly_log
-- All flagged transactions enriched with employee & manager info.
-- Used by: ai_notifier.py, Excel "Anomaly Log" sheet
-- ---------------------------------------------------------------
CREATE VIEW vw_anomaly_log AS
SELECT
    t.id                AS transaction_id,
    e.name              AS employee_name,
    e.department,
    e.manager_name,
    e.manager_email,
    t.merchant,
    t.amount,
    t.currency,
    t.amount_eur,
    t.timestamp,
    t.flag_reason
FROM transactions t
JOIN employees e ON e.id = t.employee_id
WHERE t.is_flagged = 1
ORDER BY t.timestamp DESC;

-- ---------------------------------------------------------------
-- vw_overspend_summary
-- Employees who exceeded their monthly allocated budget.
-- Used by: Excel "Budget vs Actual" sheet
-- ---------------------------------------------------------------
CREATE VIEW vw_overspend_summary AS
SELECT
    e.name              AS employee_name,
    e.department,
    e.manager_name,
    b.month,
    b.allocated_eur,
    ROUND(b.spent_eur, 2)                       AS spent_eur,
    ROUND(b.spent_eur - b.allocated_eur, 2)     AS overspend_eur,
    ROUND((b.spent_eur / b.allocated_eur - 1) * 100, 1) AS overspend_pct
FROM budgets b
JOIN employees e ON e.id = b.employee_id
WHERE b.spent_eur > b.allocated_eur
ORDER BY overspend_eur DESC;

-- ---------------------------------------------------------------
-- vw_department_spend
-- Aggregated spend per department for bar chart in Excel.
-- Used by: Excel "Department Summary" sheet
-- ---------------------------------------------------------------
CREATE VIEW vw_department_spend AS
SELECT
    e.department,
    e.manager_name,
    COUNT(t.id)                     AS total_transactions,
    ROUND(SUM(t.amount_eur), 2)     AS total_spent_eur,
    ROUND(AVG(t.amount_eur), 2)     AS avg_transaction_eur,
    SUM(t.is_flagged)               AS flagged_count
FROM transactions t
JOIN employees e ON e.id = t.employee_id
GROUP BY e.department, e.manager_name
ORDER BY total_spent_eur DESC;

-- ---------------------------------------------------------------
-- vw_currency_breakdown
-- EUR / USD / RSD transaction volumes for pie chart.
-- Used by: Excel "Currency Breakdown" sheet
-- ---------------------------------------------------------------
CREATE VIEW vw_currency_breakdown AS
SELECT
    currency,
    COUNT(*)                        AS transaction_count,
    ROUND(SUM(amount_eur), 2)       AS total_eur_equivalent
FROM transactions
GROUP BY currency
ORDER BY total_eur_equivalent DESC;
