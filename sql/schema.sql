-- =============================================================
-- schema.sql  |  Corporate Spend Analytics Pipeline
-- Creates 3 relational tables: employees, budgets, transactions
-- Run automatically by generate_data.py on first execution
-- =============================================================

DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS budgets;
DROP TABLE IF EXISTS employees;

-- ---------------------------------------------------------------
-- employees: one row per corporate card holder
-- ---------------------------------------------------------------
CREATE TABLE employees (
    id                  INTEGER PRIMARY KEY,
    name                TEXT    NOT NULL,
    department          TEXT    NOT NULL,
    manager_name        TEXT    NOT NULL,
    manager_email       TEXT    NOT NULL,
    monthly_budget_eur  REAL    NOT NULL
);

-- ---------------------------------------------------------------
-- budgets: monthly budget allocation and actual spend per employee
-- ---------------------------------------------------------------
CREATE TABLE budgets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id     INTEGER NOT NULL REFERENCES employees(id),
    month           TEXT    NOT NULL,   -- format: YYYY-MM
    allocated_eur   REAL    NOT NULL,
    spent_eur       REAL    DEFAULT 0.0
);

-- ---------------------------------------------------------------
-- transactions: every card transaction (normal + anomalies)
-- ---------------------------------------------------------------
CREATE TABLE transactions (
    id           INTEGER PRIMARY KEY,
    employee_id  INTEGER NOT NULL REFERENCES employees(id),
    merchant     TEXT    NOT NULL,
    amount       REAL    NOT NULL,
    currency     TEXT    NOT NULL CHECK(currency IN ('EUR', 'USD', 'RSD')),
    amount_eur   REAL    NOT NULL,          -- converted to EUR using live rates
    timestamp    TEXT    NOT NULL,          -- ISO 8601: YYYY-MM-DDTHH:MM:SS
    is_flagged   INTEGER NOT NULL DEFAULT 0,
    flag_reason  TEXT                       -- NULL | DOUBLE_SWIPE | WEEKEND_SPIKE | OVERSPEND | UNUSUAL_CURRENCY
);
