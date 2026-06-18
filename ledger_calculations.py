"""Shared ledger balance and summary calculations for the web dashboard."""


def _ts_start(date_str: str) -> str:
    return date_str if " " in date_str else f"{date_str} 00:00:00"


def _ts_end(date_str: str) -> str:
    return date_str if " " in date_str else f"{date_str} 23:59:59"


def fetch_summary(conn, start: str | None = None, end: str | None = None) -> dict:
    """Compute income, expense, and balances. Optional start/end filter period totals; balances are as-of end (or latest)."""
    in_where = "type = 'Cash IN'"
    out_where = "type = 'Cash OUT'"
    params_in: list = []
    params_out: list = []

    if start:
        in_where += " AND timestamp >= ?"
        out_where += " AND timestamp >= ?"
        params_in.append(_ts_start(start))
        params_out.append(_ts_start(start))
    if end:
        in_where += " AND timestamp <= ?"
        out_where += " AND timestamp <= ?"
        params_in.append(_ts_end(end))
        params_out.append(_ts_end(end))

    income = float(conn.execute(
        f"SELECT COALESCE(SUM(amount), 0) FROM ledger WHERE {in_where}", params_in
    ).fetchone()[0])
    expense = float(conn.execute(
        f"SELECT COALESCE(SUM(amount), 0) FROM ledger WHERE {out_where}", params_out
    ).fetchone()[0])

    cash_balance, bank_balance = balances_at_cutoff(conn, end)

    return {
        "income": round(income, 2),
        "expense": round(expense, 2),
        "balance": round(cash_balance + bank_balance, 2),
        "cash_balance": round(cash_balance, 2),
        "bank_balance": round(bank_balance, 2),
    }


def balances_at_cutoff(conn, cutoff: str | None = None) -> tuple[float, float]:
    """Per-account balances including only rows on or before cutoff (latest row if cutoff omitted)."""
    if cutoff is None:
        latest = latest_balances_by_account(conn)
        return latest.get("Cash", 0.0), latest.get("Bank", 0.0)

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
                WHERE timestamp <= ?
            )
        )
        WHERE rn = 1
    """, (_ts_end(cutoff),)).fetchall()
    latest = {row["account"]: float(row["balance"]) for row in rows}
    return latest.get("Cash", 0.0), latest.get("Bank", 0.0)


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
SELECT id, txn_id, timestamp, name, amount, type, account, acct_balance, net_balance FROM (
    SELECT id, txn_id, timestamp, name, amount, type, account,
        SUM(CASE WHEN type LIKE '%IN%' THEN amount ELSE -amount END)
            OVER (PARTITION BY COALESCE(account, 'Cash') ORDER BY timestamp ASC, id ASC) AS acct_balance,
        SUM(CASE WHEN type LIKE '%IN%' THEN amount ELSE -amount END)
            OVER (ORDER BY timestamp ASC, id ASC) AS net_balance
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
