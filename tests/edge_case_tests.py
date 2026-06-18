"""Automated tests for the SDE ledger web dashboard API."""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests

from ledger_calculations import balances_match_summary, count_ledger_rows, fetch_summary

BASE = "http://127.0.0.1:5000/api"
TOKEN = "admin"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


def post_tx(**kwargs):
    payload = {
        "amount": kwargs.get("amount", 100),
        "merchant": kwargs.get("merchant", "Test Merchant"),
        "description": kwargs.get("description", "test"),
        "type": kwargs.get("type", "expense"),
        "date": kwargs.get("date", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        "account": kwargs.get("account", "Cash"),
    }
    return requests.post(f"{BASE}/transactions", headers=HEADERS, json=payload)


def ledger_count():
    import sqlite3
    conn = sqlite3.connect(Path(__file__).resolve().parents[1] / "inventory.db")
    n = count_ledger_rows(conn)
    conn.close()
    return n


def run_tests():
    results = []

    def record(name, passed, detail=""):
        results.append({"name": name, "passed": passed, "detail": detail})
        mark = "PASS" if passed else "FAIL"
        print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))

    # Amount validation
    r = post_tx(amount=0, type="expense")
    record("Zero amount blocked", r.status_code == 400 and "greater than 0" in r.json().get("error", "").lower())

    r = post_tx(amount=-500, type="expense")
    record("Negative amount blocked", r.status_code == 400)

    r = post_tx(amount=10.12345, type="expense", merchant="DecimalTest")
    if r.ok:
        txs = requests.get(f"{BASE}/transactions", headers=HEADERS).json()
        dec = next((t for t in txs if t["merchant"] == "DecimalTest"), None)
        record("Decimal rounded to 2 places", dec and dec["debit"] == 10.12, f"stored={dec['debit'] if dec else None}")
    else:
        record("Decimal rounded to 2 places", False, r.text[:120])

    # Calculation integrity
    r = requests.get(f"{BASE}/ledger/integrity", headers=HEADERS)
    if r.ok:
        data = r.json()
        record("Summary matches running balances", data.get("ok") is True, str(data.get("latest_balances")))
    else:
        record("Summary matches running balances", False, r.text[:120])

    import sqlite3
    db_path = Path(__file__).resolve().parents[1] / "inventory.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    record("Local balance integrity check", balances_match_summary(conn))
    summary = fetch_summary(conn)
    conn.close()
    record("Net balance equals cash + bank", abs(summary["balance"] - (summary["cash_balance"] + summary["bank_balance"])) < 0.01)

    # Self-transfer preserves net
    before = requests.get(f"{BASE}/summary", headers=HEADERS).json()
    net_before = before["cash_balance"] + before["bank_balance"]
    requests.post(f"{BASE}/transfer", headers=HEADERS, json={
        "amount": 50, "direction": "bank_to_cash", "description": "integrity test"
    })
    after = requests.get(f"{BASE}/summary", headers=HEADERS).json()
    net_after = after["cash_balance"] + after["bank_balance"]
    record("Self-transfer preserves net total", abs(net_before - net_after) < 0.01, f"{net_before} -> {net_after}")

    # Transactions are never deleted unless explicitly confirmed
    count_before = ledger_count()
    post_tx(amount=25, merchant="PersistTest")
    count_after_add = ledger_count()
    record("Adding transaction increases ledger count", count_after_add == count_before + 1)

    # Unconfirmed delete is rejected
    txs = requests.get(f"{BASE}/transactions", headers=HEADERS).json()
    tid = next(t["id"] for t in txs if t["merchant"] == "PersistTest")
    bad_delete = requests.delete(f"{BASE}/transactions/{tid}", headers=HEADERS)
    record("Delete without confirmation blocked", bad_delete.status_code == 400)
    record("Count unchanged after blocked delete", ledger_count() == count_after_add)

    # Confirmed delete works (only explicit user action)
    good_delete = requests.delete(
        f"{BASE}/transactions/{tid}",
        headers=HEADERS,
        json={"confirmed": True},
    )
    record("Confirmed delete succeeds", good_delete.ok)
    record("Count decreases only after confirmed delete", ledger_count() == count_after_add - 1)

    # Edit deleted transaction fails gracefully
    r = post_tx(amount=77, type="expense", merchant="DeleteMe")
    txs = requests.get(f"{BASE}/transactions", headers=HEADERS).json()
    del_id = next(t["id"] for t in txs if t["merchant"] == "DeleteMe")
    requests.delete(f"{BASE}/transactions/{del_id}", headers=HEADERS, json={"confirmed": True})
    upd = requests.put(f"{BASE}/transactions/{del_id}", headers=HEADERS, json={"amount": 88})
    record("Edit deleted txn returns not found", upd.status_code == 404)

    # Future date + leap year
    future = (datetime.now() + timedelta(days=365 * 10)).strftime("%Y-%m-%d %H:%M:%S")
    r = post_tx(amount=50, type="income", merchant="FutureTxn", date=future)
    if r.ok:
        txs = requests.get(f"{BASE}/transactions", headers=HEADERS).json()
        record("Future date accepted", txs[0]["merchant"] == "FutureTxn")
    else:
        record("Future date accepted", False)

    r = post_tx(amount=29, type="expense", merchant="LeapDay", date="2024-02-29 12:00:00")
    record("Leap year Feb 29 accepted", r.status_code == 200)

    failed = [r for r in results if not r["passed"]]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(run_tests())
