from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Classification:
    document_type: str
    confidence: float
    signals: list[str]


_PATTERNS = {
    "balance_sheet": [
        r"balance sheet",
        r"assets",
        r"liabilities",
        r"shareholders.? equity",
        r"property,? plant and equipment",
    ],
    "profit_and_loss": [
        r"profit and loss",
        r"statement of profit",
        r"revenue",
        r"profit before tax",
        r"profit for the year",
    ],
    "cash_flow": [
        r"cash flow statement",
        r"cash flows from operating activities",
        r"cash and cash equivalents",
    ],
    "notes_to_accounts": [
        r"notes to (the )?financial statements",
        r"accounting policies",
        r"contingent liabilities",
        r"commitments",
    ],
}


def classify_document(text: str) -> Classification:
    normalized = text.lower()
    scores = {}
    signals = {}

    for doc_type, patterns in _PATTERNS.items():
        matched = [pattern for pattern in patterns if re.search(pattern, normalized)]
        scores[doc_type] = len(matched)
        signals[doc_type] = matched

    if not any(scores.values()):
        return Classification("other", 0.35, [])

    best = max(scores, key=scores.get)
    score = scores[best]
    confidence = min(0.95, 0.45 + (score / len(_PATTERNS[best])) * 0.5)
    return Classification(best, round(confidence, 3), signals[best])
