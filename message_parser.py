"""Parse natural-language expense/income messages from WhatsApp."""
import re
from typing import Any

# Normalize whitespace (handles multi-line messages)
def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())

# Match amounts with optional currency markers; reject letter O used as zero
_AMOUNT_PATTERNS = [
    re.compile(r"(?:spent|paid|pay|bought|buy|expense|income|received|got)\s+([₹$]?\s*[\d,]+(?:\.\d{1,2})?)\s*(?:rs|inr|rupees?)?", re.I),
    re.compile(r"([₹$]\s*[\d,]+(?:\.\d{1,2})?)", re.I),
    re.compile(r"([\d,]+(?:\.\d{1,2})?)\s*(?:rs|inr|rupees?)\b", re.I),
    re.compile(r"\b([\d,]+(?:\.\d{1,2})?)\b"),
]

_AMBIGUOUS_O = re.compile(r"(?<![a-zA-Z])[0-9]*[oO](?![a-zA-Z0-9])|[0-9]+[oO](?![a-zA-Z0-9])")


def _parse_amount_token(raw: str) -> tuple[float | None, bool]:
    """Return (amount, needs_clarification)."""
    token = raw.strip()
    if _AMBIGUOUS_O.search(token):
        return None, True
    cleaned = re.sub(r"[₹$,]", "", token).strip()
    cleaned = re.sub(r"\s+", "", cleaned)
    if not cleaned or not re.fullmatch(r"\d+(?:\.\d{1,2})?", cleaned):
        return None, True
    return round(float(cleaned), 2), False


def _extract_merchant(text: str, amount_str: str | None) -> str:
    lowered = text.lower()
    for prefix in (" on ", " at ", " from ", " for "):
        idx = lowered.find(prefix)
        if idx >= 0:
            merchant = text[idx + len(prefix):].strip()
            if merchant:
                return merchant[:120]
    if amount_str:
        remainder = text.replace(amount_str, "", 1).strip()
        remainder = re.sub(r"(?i)^(spent|paid|pay|bought|buy|expense|income|received|got)\s+", "", remainder)
        remainder = re.sub(r"(?i)\s*(rs|inr|rupees?|for|on|at)\s*", " ", remainder).strip()
        if remainder:
            return remainder[:120]
    return "Unknown"


def parse_expense_message(text: str) -> dict[str, Any]:
    """
    Parse a WhatsApp-style message into amount + merchant.
    Returns needs_clarification=True when the amount cannot be trusted (e.g. 50O).
    """
    normalized = _normalize(text)
    if not normalized:
        return {"amount": None, "merchant": None, "needs_clarification": True, "error": "Empty message"}

    if re.search(r"\d+[oO](?=\s|$|[^0-9.])", normalized):
        return {
            "amount": None,
            "merchant": None,
            "needs_clarification": True,
            "error": "Could not read the amount — did you mean a number like 500?",
        }

    for pattern in _AMOUNT_PATTERNS:
        match = pattern.search(normalized)
        if not match:
            continue
        amount, ambiguous = _parse_amount_token(match.group(1))
        if ambiguous:
            return {
                "amount": None,
                "merchant": None,
                "needs_clarification": True,
                "error": "Could not read the amount — did you mean a number like 500?",
            }
        if amount and amount > 0:
            return {
                "amount": amount,
                "merchant": _extract_merchant(normalized, match.group(1)),
                "needs_clarification": False,
            }

    return {
        "amount": None,
        "merchant": None,
        "needs_clarification": True,
        "error": "No valid amount found in message",
    }
