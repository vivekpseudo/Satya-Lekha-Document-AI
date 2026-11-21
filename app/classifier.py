from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Classification:
    document_type: str
    confidence: float
    signals: list[str]


# Patterns run against the text with everything except letters and digits removed
# ("squashed"). That makes matching immune to line breaks, punctuation, and the
# stray spaces some PDF fonts produce inside words ("MEMBE RS", "Au dit of t he").
# Each entry is (signal name, squashed regex, weight). Generic words that appear
# in almost every financial document ("assets") get a weight of 1; document
# titles and unmistakable phrases get much more.
_PATTERNS: dict[str, list[tuple[str, str, int]]] = {
    "balance_sheet": [
        ("balance sheet", r"balancesheet", 5),
        ("equity and liabilities", r"equityandliabilities", 3),
        ("shareholders' funds/equity", r"shareholders(funds|equity)", 2),
        ("total assets", r"totalassets", 2),
        ("current liabilities", r"currentliabilities", 1),
        ("property, plant and equipment", r"propertyplantandequipment", 1),
        ("assets", r"assets", 1),
        ("liabilities", r"liabilities", 1),
    ],
    "profit_and_loss": [
        ("statement of profit and loss", r"(statementofprofitand(loss)?|profitandlossstatement)", 6),
        ("profit before tax", r"profitbeforetax", 2),
        ("profit for the year", r"profit(loss)?fortheyear", 2),
        ("revenue from operations", r"revenuefromoperations", 2),
        ("total expenses", r"totalexpenses", 1),
        ("revenue", r"revenue", 1),
    ],
    "cash_flow": [
        ("cash flow statement", r"cashflowstatement", 6),
        ("cash flows from operating activities", r"cashflowsfromoperatingactivities", 3),
        ("operating activities", r"operatingactivities", 2),
        ("cash and cash equivalents", r"cashandcashequivalents", 1),
    ],
    "notes_to_accounts": [
        ("notes to the financial statements", r"notes(to|formingpartof)(the)?financialstatements", 6),
        ("accounting policies", r"(significant)?accountingpolicies", 2),
        ("contingent liabilities", r"contingentliabilities", 1),
        ("commitments", r"commitments", 1),
    ],
    "directors_report": [
        ("directors' report", r"(directorsreport|boardsreport|reportoftheboardofdirectors)", 8),
        ("directors have pleasure", r"yourdirectorshavepleasure", 5),
        ("directors' responsibility statement", r"directorsresponsibilitystatement", 4),
        ("state of the company's affairs", r"stateofthecompanysaffairs", 3),
        ("transfer to reserves", r"transfertoreserves", 2),
        ("material changes", r"materialchangesandcommitments", 2),
    ],
    "auditors_report": [
        ("independent auditor's report", r"independentauditorsreport", 8),
        ("auditor's report", r"auditorsreport", 5),
        ("report on the audit of the financial statements", r"reportontheauditofthefinancialstatements", 6),
        ("basis for opinion", r"basisforopinion", 5),
        ("key audit matters", r"keyauditmatters", 4),
        ("we have audited", r"wehaveaudited", 4),
        ("Standards on Auditing", r"standardsonauditing", 3),
        ("CARO", r"(caro|companiesauditorsreportorder)", 3),
        ("internal financial controls", r"internalfinancialcontrols", 2),
    ],
    "agm_notice": [
        ("notice is hereby given", r"noticeisherebygiven", 8),
        ("annual general meeting", r"annualgeneralmeeting", 4),
        ("ordinary business", r"ordinarybusiness", 3),
        ("special business", r"specialbusiness", 3),
        ("proxy", r"proxy", 1),
        ("explanatory statement", r"explanatorystatement", 2),
    ],
    "invoice": [
        ("tax invoice", r"taxinvoice", 6),
        ("invoice", r"invoice", 4),
        ("invoice no", r"invoice(no|number)", 4),
        ("GSTIN", r"gstin", 3),
        ("HSN/SAC", r"(hsn|sac)(code)?", 2),
        ("bill to / party", r"(billto|party)", 1),
        ("amount chargeable", r"amountchargeable", 3),
    ],
}

# Phrases in the first part of a document count double: a title near the top says
# what the document *is*, while the same phrase later may only be a reference.
_TITLE_ZONE_CHARS = 1200
_MIN_SCORE = 4


def _squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def classify_document(text: str) -> Classification:
    squashed = _squash(text)
    head = squashed[:_TITLE_ZONE_CHARS]

    scores: dict[str, int] = {}
    signals: dict[str, list[str]] = {}
    for doc_type, patterns in _PATTERNS.items():
        score, matched = 0, []
        for name, pattern, weight in patterns:
            if re.search(pattern, squashed):
                score += weight * (2 if re.search(pattern, head) else 1)
                matched.append(name)
        scores[doc_type], signals[doc_type] = score, matched

    ranked = sorted(scores, key=scores.get, reverse=True)
    best = ranked[0]
    best_score = scores[best]
    if best_score < _MIN_SCORE:
        return Classification("other", 0.35, [])

    second_score = scores[ranked[1]]
    strength = min(1.0, best_score / 12)
    margin = (best_score - second_score) / best_score
    confidence = 0.45 + 0.5 * strength * (0.6 + 0.4 * margin)
    return Classification(best, round(min(confidence, 0.97), 3), signals[best])
