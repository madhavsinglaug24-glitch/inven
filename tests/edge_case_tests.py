"""Automated edge-case tests for whatsapp-bot ledger API."""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests

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


def get_txs():
    r = requests.get(f"{BASE}/transactions", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def run_tests():
    results = []

    def record(name, passed, detail=""):
        results.append({"name": name, "passed": passed, "detail": detail})
        mark = "PASS" if passed else "FAIL"
        print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))

    # Math Breaker
    r = post_tx(amount=0, type="expense")
    record("Zero amount blocked", r.status_code == 400 and "greater than 0" in r.json().get("error", "").lower(),
           r.text[:120])

    r = post_tx(amount=-500, type="expense")
    record("Negative amount blocked", r.status_code == 400, r.text[:120])

    r = post_tx(amount=999999999999, type="income", merchant="BigIncome")
    record("Massive value accepted", r.status_code == 200, r.text[:120])

    r = post_tx(amount=10.12345, type="expense", merchant="DecimalTest")
    if r.ok:
        txs = get_txs()
        dec = next((t for t in txs if t["merchant"] == "DecimalTest"), None)
        stored = dec["debit"] if dec else None
        record("Decimal rounded to 2 places", dec is not None and stored == 10.12, f"stored={stored}")
    else:
        record("Decimal stored", False, r.text[:120])

    # Transfer math
    before = requests.get(f"{BASE}/summary", headers=HEADERS).json()
    net_before = before.get("cash_balance", 0) + before.get("bank_balance", 0)
    tr = requests.post(f"{BASE}/transfer", headers=HEADERS, json={
        "amount": 100, "direction": "bank_to_cash", "description": "test transfer"
    })
    after = requests.get(f"{BASE}/summary", headers=HEADERS).json()
    net_after = after.get("cash_balance", 0) + after.get("bank_balance", 0)
    record("Self-transfer preserves net", tr.ok and abs(net_before - net_after) < 0.01,
           f"before={net_before}, after={net_after}")

    # Future date
    future = (datetime.now() + timedelta(days=365 * 10)).strftime("%Y-%m-%d %H:%M:%S")
    r = post_tx(amount=50, type="income", merchant="FutureTxn", date=future)
    if r.ok:
        txs = get_txs()
        top = txs[0] if txs else None
        record("Future date at top of All Time", top and top.get("merchant") == "FutureTxn",
               f"top={top.get('merchant') if top else None}, date={top.get('date') if top else None}")
    else:
        record("Future date at top of All Time", False, r.text[:120])

    # Leap year Feb 29
    r = post_tx(amount=29, type="expense", merchant="LeapDay", date="2024-02-29 12:00:00")
    record("Leap year Feb 29 accepted", r.status_code == 200, r.text[:120])

    # Edit deleted txn
    r = post_tx(amount=77, type="expense", merchant="DeleteMe")
    txs = get_txs()
    tid = next(t["id"] for t in txs if t["merchant"] == "DeleteMe")
    requests.delete(f"{BASE}/transactions/{tid}", headers=HEADERS)
    upd = requests.put(f"{BASE}/transactions/{tid}", headers=HEADERS, json={"amount": 88})
    record("Edit deleted txn fails gracefully", upd.status_code in (404, 400), upd.text[:120])

    # Case search simulation (client-side logic)
    post_tx(amount=909, type="expense", merchant="aMaZoN")
    txs = get_txs()
    q = "amazon"
    found = any(q in str(t["merchant"]).lower() for t in txs)
    record("Case-insensitive merchant search logic", found)
    q2 = "909"
    found_amt = any(q2 in str(t["credit"]) or q2 in str(t["debit"]) for t in txs)
    record("Amount search logic", found_amt)

    # Message parser (if module exists)
    try:
        from message_parser import parse_expense_message
        p1 = parse_expense_message("Spent 500\non \ngroceries")
        record("Multiline parse 500", p1.get("amount") == 500, str(p1))
        p2 = parse_expense_message("₹500 for coffee")
        record("Rupee symbol parse", p2.get("amount") == 500, str(p2))
        p3 = parse_expense_message("$500 for coffee")
        record("Dollar symbol parse", p3.get("amount") == 500, str(p3))
        p4 = parse_expense_message("500rs for coffee")
        record("rs suffix parse", p4.get("amount") == 500, str(p4))
        p5 = parse_expense_message("spent 50O on food")
        record("Letter O typo asks clarification", p5.get("needs_clarification") or p5.get("amount") is None,
               str(p5))
    except ImportError as e:
        record("Message parser module", False, str(e))

    failed = [r for r in results if not r["passed"]]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(run_tests())
