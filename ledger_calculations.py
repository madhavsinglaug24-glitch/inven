"""Shared ledger balance and summary calculations for the web dashboard."""


def fetch_summary(conn) -> dict:
    """Compute income, expense, and per-account balances from the ledger."""
    income = float(conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM ledger WHERE type = 'Cash IN'"
    ).fetchone()[0])
    expense = float(conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM ledger WHERE type = 'Cash OUT'"
    ).fetchone()[0])

    cash_in = float(conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM ledger WHERE type = 'Cash IN' AND COALESCE(account, 'Cash') = 'Cash'"
    ).fetchone()[0])
    cash_out = float(conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM ledger WHERE type = 'Cash OUT' AND COALESCE(account, 'Cash') = 'Cash'"
    ).fetchone()[0])
    bank_in = float(conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM ledger WHERE type = 'Cash IN' AND account = 'Bank'"
    ).fetchone()[0])
    bank_out = float(conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM ledger WHERE type = 'Cash OUT' AND account = 'Bank'"
    ).fetchone()[0])

    cash_balance = cash_in - cash_out
    bank_balance = bank_in - bank_out

    return {
        "income": round(income, 2),
        "expense": round(expense, 2),
        "balance": round(income - expense, 2),
        "cash_balance": round(cash_balance, 2),
        "bank_balance": round(bank_balance, 2),
    }


def fetch_month_stats(conn, month_str: str) -> tuple[float, float]:
    """Return (cash_in, cash_out) totals for a YYYY-MM month prefix."""
    month_in = float(conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM ledger WHERE timestamp LIKE ? AND type = 'Cash IN'",
        (f"{month_str}%",),
    ).fetchone()[0])
    month_out = float(conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM ledger WHERE timestamp LIKE ? AND type = 'Cash OUT'",
        (f"{month_str}%",),
    ).fetchone()[0])
    return month_in, month_out


TRANSACTIONS_WITH_BALANCE_SQL = """
SELECT id, txn_id, timestamp, name, amount, type, account, balance FROM (
    SELECT id, txn_id, timestamp, name, amount, type, account,
        SUM(CASE WHEN type LIKE '%IN%' THEN amount ELSE -amount END)
            OVER (PARTITION BY COALESCE(account, 'Cash') ORDER BY timestamp ASC, id ASC) AS balance
    FROM ledger
)
ORDER BY timestamp DESC, id DESC
LIMIT ?
"""


def count_ledger_rows(conn) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM ledger").fetchone()[0])


def latest_balances_by_account(conn) -> dict[str, float]:
    """Last running balance per account from the ledger."""
    rows = conn.execute("""
        SELECT COALESCE(account, 'Cash') AS account, balance FROM (
            SELECT account, balance,
                ROW_NUMBER() OVER (
                    PARTITION BY COALESCE(account, 'Cash')
                    ORDER BY timestamp DESC, id DESC
                ) AS rn
            FROM (
                SELECT account, timestamp, id,
                    SUM(CASE WHEN type LIKE '%IN%' THEN amount ELSE -amount END)
                        OVER (PARTITION BY COALESCE(account, 'Cash') ORDER BY timestamp ASC, id ASC) AS balance
                FROM ledger
            )
        )
        WHERE rn = 1
    """).fetchall()
    return {row["account"]: round(float(row["balance"]), 2) for row in rows}


def balances_match_summary(conn) -> bool:
    """True when summary API numbers match running-balance totals."""
    summary = fetch_summary(conn)
    latest = latest_balances_by_account(conn)
    cash = latest.get("Cash", 0.0)
    bank = latest.get("Bank", 0.0)
    return (
        abs(summary["cash_balance"] - cash) < 0.01
        and abs(summary["bank_balance"] - bank) < 0.01
        and abs(summary["balance"] - (summary["cash_balance"] + summary["bank_balance"])) < 0.01
    )
