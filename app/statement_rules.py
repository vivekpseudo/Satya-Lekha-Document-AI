"""Rules for financial statements: the balance sheet and the statement of profit and loss.

These check that the statements are arithmetically consistent, internally
reconciled across years, notes and statements, and laid out as Schedule III to
the Companies Act, 2013 expects. They work from the extracted rows (``facts``,
each carrying every column: current year first, then prior year) and, for
layout and signature checks, from the document text.

A passing result means the numbers agree with each other. It does not mean the
numbers are right: a statement can reconcile and still be wrong.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from app.rules_engine import ComplianceFinding, ComplianceRule, RegulationEvidence, RuleContext
from app.text_rules import Evaluator, TextIndex, _finding, _no_text, _signature_date

TOLERANCE = Decimal("1.00")  # statements are often rounded to the nearest rupee
ZERO = Decimal(0)

_LEADING_MARKERS = re.compile(
    r"^(?:(?:\(\s*[a-z0-9]{1,4}\s*\)|[ivx]{1,5}\.|\d{1,2}\.|[-–•])\s*)+", re.I
)
_CHILD_MARKER = re.compile(r"^\(\s*(?:[ivx]{1,4}|\d{1,2})\s*\)", re.I)


def _key(label: str) -> str:
    """Comparable form of a row label: no numbering, punctuation, case or spaces."""
    return re.sub(r"[^a-z0-9]", "", _LEADING_MARKERS.sub("", label.strip().lower()))


def _dec(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def _fmt(value: Decimal) -> str:
    return f"{value:,.2f}"


@dataclass
class Row:
    label: str
    key: str
    cur: Decimal | None
    prev: Decimal | None
    page: Any
    fact: dict[str, Any]
    child: bool  # a "(i)" / "(1)" sub-line already counted in its parent

    @property
    def cur0(self) -> Decimal:
        return self.cur if self.cur is not None else ZERO

    @property
    def prev0(self) -> Decimal:
        return self.prev if self.prev is not None else ZERO


def _rows(ctx: RuleContext) -> list[Row]:
    rows = []
    for fact in ctx.facts:
        label = str(fact.get("label", ""))
        values = fact.get("values")
        if not isinstance(values, list):
            values = [fact.get("value")]
        cur = _dec(values[0]) if values else None
        prev = _dec(values[1]) if len(values) > 1 else None
        if cur is None and prev is None:
            continue
        rows.append(Row(label, _key(label), cur, prev, fact.get("source_page"), fact,
                        bool(_CHILD_MARKER.match(label.strip()))))
    return rows


def _years(*candidates: Row | None) -> list[tuple[str, str]]:
    """Which columns exist: [("current year", "cur"), ("prior year", "prev")]."""
    out = [("current year", "cur")]
    rows = [r for r in candidates if r is not None]
    if rows and all(r.prev is not None for r in rows):
        out.append(("prior year", "prev"))
    return out


# ---------------------------------------------------------------- statement regions

@dataclass
class BalanceSheet:
    liabilities: list[Row]
    assets: list[Row]
    le_total: Row
    asset_total: Row


def _balance_sheet(rows: list[Row]) -> BalanceSheet | None:
    """Locate the face of the balance sheet using its two closing totals."""
    le_idx = next((i for i, r in enumerate(rows)
                   if r.key.startswith(("totalequityandliabilities", "totalliabilitiesandequity"))), None)
    asset_idx = next((i for i, r in enumerate(rows) if r.key.startswith("totalassets")), None)
    if le_idx is None or asset_idx is None:
        by_page: dict[Any, list[int]] = {}
        for i, r in enumerate(rows):
            if r.key == "total":
                by_page.setdefault(r.page, []).append(i)
        for page in sorted(by_page, key=lambda p: (p is None, p)):
            if len(by_page[page]) == 2:
                le_idx, asset_idx = by_page[page]
                break
        else:
            return None
    if not le_idx < asset_idx:
        return None
    page = rows[le_idx].page
    start = next(i for i, r in enumerate(rows) if r.page == page)
    return BalanceSheet(rows[start:le_idx], rows[le_idx + 1:asset_idx], rows[le_idx], rows[asset_idx])


@dataclass
class ProfitAndLoss:
    rows: list[Row]
    total_expenses: Row


def _profit_and_loss(rows: list[Row]) -> ProfitAndLoss | None:
    idx = next((i for i, r in enumerate(rows) if r.key.startswith("totalexpenses")), None)
    if idx is None:
        return None
    page = rows[idx].page
    return ProfitAndLoss([r for r in rows if r.page == page], rows[idx])


def _find(rows: list[Row], *keys: str, exact: bool = False) -> Row | None:
    for row in rows:
        if any(row.key == k if exact else row.key.startswith(k) for k in keys):
            return row
    return None


def _items(rows: list[Row], prefixes: tuple[str, ...]) -> list[Row]:
    return [r for r in rows if not r.child and r.key.startswith(prefixes)]


def _sum(rows: list[Row], attr: str) -> Decimal:
    return sum((getattr(r, attr + "0") for r in rows), ZERO)


def _facts(*rows: Row | None) -> list[dict[str, Any]]:
    return [r.fact for r in rows if r is not None]


def _squashed_has(ctx: RuleContext, pattern: str) -> bool:
    return TextIndex(ctx.text).has(pattern) if ctx.text.strip() else False


# Schedule III, Division I (accounting standards) groupings by line-item name.
_SECTIONS: dict[str, tuple[str, tuple[str, ...]]] = {
    "shareholders' funds": ("shareholdersfunds", ("sharecapital", "reservesandsurplus",
                                                   "moneyreceivedagainstsharewarrants")),
    "non-current liabilities": ("noncurrentliabilities", ("longtermborrowings", "deferredtaxliabilit",
                                                           "otherlongtermliabilit", "longtermprovisions")),
    "current liabilities": ("currentliabilities", ("shorttermborrowings", "tradepayables",
                                                    "othercurrentliabilit", "shorttermprovisions")),
    "non-current assets": ("noncurrentassets", ("propertyplantandequipmentandintangible", "fixedassets",
                                                 "noncurrentinvestments", "deferredtaxassets",
                                                 "longtermloansandadvances", "othernoncurrentassets")),
    "current assets": ("currentassets", ("currentinvestments", "inventories", "traderecei",
                                          "cashandcashequivalents", "shorttermloansandadvances",
                                          "othercurrentassets")),
}


def _heading(rows: list[Row], ctx: RuleContext, key: str) -> tuple[Row | None, bool]:
    """(row, exists): nil headings vanish from the facts but remain in the text."""
    row = _find(rows, key, exact=True)
    return row, row is not None or _squashed_has(ctx, key)


# ------------------------------------------------------------------- balance sheet

def rule_bs_both_years(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "FSBS-001", "Balance sheet balances in both years"
    sheet = _balance_sheet(_rows(ctx))
    if not sheet:
        return None
    problems, parts = [], []
    for name, attr in _years(sheet.le_total, sheet.asset_total):
        assets, le = getattr(sheet.asset_total, attr), getattr(sheet.le_total, attr)
        diff = assets - le
        parts.append(f"{name}: assets {_fmt(assets)}, equity and liabilities {_fmt(le)}")
        if abs(diff) > TOLERANCE:
            problems.append(f"{name} differs by {_fmt(diff)}")
    evidence = _facts(sheet.le_total, sheet.asset_total)
    if problems:
        return _finding(rid, title, "FAIL", "HIGH", "Total assets do not equal total equity and liabilities: "
                        + "; ".join(problems) + ".", evidence, regs, 0.95)
    return _finding(rid, title, "PASS", "LOW", "Total assets equal total equity and liabilities (" + "; ".join(parts)
                    + ").", evidence, regs, 0.95)


def rule_bs_subtotals(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "FSBS-002", "Sub-totals add up to the balance sheet totals"
    rows = _rows(ctx)
    sheet = _balance_sheet(rows)
    if not sheet:
        return None
    liab = {name: _heading(sheet.liabilities, ctx, _SECTIONS[name][0])
            for name in ("shareholders' funds", "non-current liabilities", "current liabilities")}
    assets = {name: _heading(sheet.assets, ctx, _SECTIONS[name][0])
              for name in ("non-current assets", "current assets")}
    if not liab["shareholders' funds"][1] or not assets["current assets"][1]:
        return None  # not a Division I layout with these headings
    share_app = _find(sheet.liabilities, "shareapplicationmoney")
    checks = [("equity and liabilities", sheet.le_total, [r for r, _ in liab.values()] + [share_app]),
              ("assets", sheet.asset_total, [r for r, _ in assets.values()])]
    problems, parts = [], []
    evidence = _facts(sheet.le_total, sheet.asset_total)
    for label, total, headings in checks:
        evidence += _facts(*headings)
        for name, attr in _years(total):
            summed = _sum([h for h in headings if h is not None], attr)
            diff = summed - getattr(total, attr)
            parts.append(f"{label} {name}: {_fmt(summed)} vs {_fmt(getattr(total, attr))}")
            if abs(diff) > TOLERANCE:
                problems.append(f"{label} ({name}): sub-totals add up to {_fmt(summed)} but the total is "
                                f"{_fmt(getattr(total, attr))}")
    if problems:
        return _finding(rid, title, "FAIL", "HIGH", "; ".join(problems) + ".", evidence, regs, 0.9)
    return _finding(rid, title, "PASS", "LOW",
                    "Shareholders' funds, non-current and current liabilities add up to the total, and "
                    "non-current plus current assets add up to total assets, in each year.", evidence, regs, 0.9)


def rule_bs_sections_add_up(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "FSBS-003", "Balance sheet line items add up to their sections"
    sheet = _balance_sheet(_rows(ctx))
    if not sheet:
        return None
    problems, evidence, checked = [], [], 0
    for name, (key, prefixes) in _SECTIONS.items():
        side = sheet.liabilities if "liabilit" in name or name == "shareholders' funds" else sheet.assets
        heading, exists = _heading(side, ctx, key)
        if not exists:
            continue
        items = _items(side, prefixes)
        checked += 1
        evidence += _facts(heading, *items)
        for year, attr in _years(*(([heading] if heading else []) + items) or [sheet.le_total]):
            head_val = getattr(heading, attr + "0") if heading else ZERO
            diff = _sum(items, attr) - head_val
            if abs(diff) > TOLERANCE:
                problems.append(f"{name} ({year}): line items add up to {_fmt(_sum(items, attr))} but the "
                                f"heading shows {_fmt(head_val)}")
    if not checked:
        return None
    if problems:
        return _finding(rid, title, "FAIL", "HIGH", "; ".join(problems) + ".", evidence, regs, 0.85)
    return _finding(rid, title, "PASS", "LOW",
                    f"The line items add up to the heading in all {checked} sections, in each year.",
                    evidence, regs, 0.85)


_DIVISION_I = [
    ("Shareholders' funds", r"shareholdersfunds"), ("Share capital", r"sharecapital"),
    ("Reserves and surplus", r"reservesandsurplus"), ("Non-current liabilities", r"noncurrentliabilities"),
    ("Long-term borrowings", r"longtermborrowings"), ("Current liabilities", r"currentliabilities"),
    ("Trade payables", r"tradepayables"), ("Non-current assets", r"noncurrentassets"),
    ("Current assets", r"currentassets"), ("Inventories", r"inventories"),
    ("Trade receivables", r"tradereceivables"), ("Cash and cash equivalents", r"cashandcashequivalents"),
]
_DIVISION_II = [
    ("Equity share capital", r"equitysharecapital"), ("Other equity", r"otherequity"),
    ("Non-current liabilities", r"noncurrentliabilities"), ("Financial liabilities", r"financialliabilities"),
    ("Current liabilities", r"currentliabilities"), ("Total equity and liabilities", r"totalequityandliabilities"),
    ("Non-current assets", r"noncurrentassets"), ("Property, plant and equipment", r"propertyplantandequipment"),
    ("Financial assets", r"financialassets"), ("Current assets", r"currentassets"),
    ("Inventories", r"inventories"), ("Total assets", r"totalassets"),
]


def rule_bs_schedule_iii_headings(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "FSBS-004", "Schedule III headings on the balance sheet"
    if not ctx.text.strip() or not (ctx.document_type == "balance_sheet" or _balance_sheet(_rows(ctx))):
        return None
    index = TextIndex(ctx.text)
    division_ii = index.has(r"(otherequity|financialassets|financialliabilities)")
    division_i = index.has(r"(shareholdersfunds|shareapplicationmoney)")
    division, expected = ("II (Ind AS)", _DIVISION_II) if division_ii and not division_i else ("I", _DIVISION_I)
    found = [(label, index.evidence(pattern, label, 120)) for label, pattern in expected]
    missing = [label for label, ev in found if not ev]
    evidence = [ev for _, ev in found if ev][:6]
    notes = ""
    if division == "I" and ctx.framework == "Ind AS":
        notes = (" The layout is Schedule III Division I (accounting standards), but the framework selected is Ind AS. "
                 "Unlisted companies below the Ind AS net-worth threshold may follow Division I, so confirm which applies.")
    if missing:
        return _finding(rid, title, "REVIEW", "MEDIUM",
                        f"Division {division} headings not found: " + ", ".join(missing) + "." + notes,
                        evidence, regs, 0.75)
    status, sev = ("REVIEW", "LOW") if notes else ("PASS", "LOW")
    return _finding(rid, title, status, sev,
                    f"All expected Schedule III Division {division} headings are present." + notes,
                    evidence, regs, 0.8)


def rule_bs_comparatives_and_units(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "FSBS-005", "Comparative figures and units stated"
    sheet = _balance_sheet(_rows(ctx))
    if not sheet:
        return None
    face = [r for r in sheet.liabilities + sheet.assets + [sheet.le_total, sheet.asset_total]]
    both = sum(1 for r in face if r.cur is not None and r.prev is not None)
    share = both / len(face) if face else 0
    problems = []
    if share < 0.8:
        problems.append(f"only {both} of {len(face)} lines show a prior-year figure (Schedule III requires "
                        "comparatives)")
    if ctx.text.strip() and not TextIndex(ctx.text).has(r"(amounts?in|inrs|rupees|inlakhs|incrores|rsinlakhs)"):
        problems.append("the units of presentation (for example 'Amount in Rs.') are not stated")
    evidence = _facts(sheet.le_total, sheet.asset_total)
    if problems:
        return _finding(rid, title, "REVIEW", "MEDIUM", "Review: " + "; ".join(problems) + ".", evidence, regs, 0.8)
    return _finding(rid, title, "PASS", "LOW",
                    "Prior-year comparatives are shown and the units of presentation are stated.",
                    evidence, regs, 0.8)


def _notes_page(ctx: RuleContext) -> int | None:
    if "\f" not in ctx.text:
        return None
    for number, page in enumerate(ctx.text.split("\f"), start=1):
        if TextIndex(page).has(r"notesformingpartofthefinancialstatements|notestothefinancialstatements"):
            return number
    return None


def rule_notes_tie_to_statements(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "FSBS-006", "Note totals agree with the statements"
    rows = _rows(ctx)
    notes_from = _notes_page(ctx)
    if notes_from is None:
        return None
    statements = [r for r in rows if isinstance(r.page, int) and r.page < notes_from]
    if not statements:
        return None
    totals = [r for r in rows if isinstance(r.page, int) and r.page >= notes_from and r.key == "total"]
    if not totals:
        return None
    unmatched, evidence = [], []
    seen: set[tuple[Decimal | None, Decimal | None]] = set()
    for total in totals:
        if (total.cur, total.prev) in seen:
            continue  # a repeated grand total
        seen.add((total.cur, total.prev))
        for _, attr in _years(total):
            value = getattr(total, attr)
            if not any(abs(getattr(s, attr) - value) <= TOLERANCE for s in statements
                       if getattr(s, attr) is not None):
                unmatched.append((total, attr, value))
        evidence.append(total.fact)
    if unmatched:
        desc = "; ".join(f"page {t.page}: a note total of {_fmt(v)} ({'current' if a == 'cur' else 'prior'} year)"
                         for t, a, v in unmatched[:5])
        return _finding(rid, title, "REVIEW", "MEDIUM",
                        "These note totals do not match any line on the balance sheet or statement of profit and "
                        f"loss (within ₹1): {desc}.", [t.fact for t, _, _ in unmatched[:5]], regs, 0.75)
    return _finding(rid, title, "PASS", "LOW",
                    f"All {len(seen)} note totals agree with a line on the balance sheet or statement of profit "
                    "and loss in both years.", evidence[:8], regs, 0.8)


def rule_statement_signatures(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "FSBS-007", "Statements signed by directors and auditor, with UDIN"
    if not ctx.text.strip():
        return None
    pages = ctx.text.split("\f")
    problems, evidence, signed_pages = [], [], 0
    for number, text in enumerate(pages, start=1):
        index = TextIndex(text)
        if not index.has(r"(frn\d|foronbehalfof|forbehalfof)"):
            continue
        signed_pages += 1
        missing = []
        if len(set(re.findall(r"(?<!u)din(?:no)?(\d{8})", index.squashed))) < 2:
            missing.append("two directors with DIN")
        if not index.has(r"frn\d{5,6}[a-z]?"):
            missing.append("auditor FRN")
        if not index.has(r"(mno|membershipno?)\d{6}"):
            missing.append("membership number")
        if not index.has(r"udin(no)?\d{8}[a-z0-9]{10}"):
            missing.append("UDIN")
        if _signature_date(index) is None:
            missing.append("date")
        ev = index.evidence(r"frn\d|foronbehalfof|forbehalfof", f"Signature block (page {number})", 200)
        if ev:
            ev["source_page"] = number if len(pages) > 1 else None
            evidence.append(ev)
        if missing:
            problems.append(f"page {number}: " + ", ".join(missing))
    if not signed_pages:
        return _finding(rid, title, "REVIEW", "MEDIUM",
                        "No signature block (directors and auditor) was found on the statements.", [], regs, 0.7)
    if problems:
        only_udin = all(p.endswith("UDIN") for p in problems)
        return _finding(rid, title, "FAIL", "MEDIUM" if only_udin else "HIGH",
                        "Incomplete signature blocks: " + "; ".join(problems) + ". A UDIN is mandatory on "
                        "documents certified by a chartered accountant.", evidence, regs, 0.85)
    return _finding(rid, title, "PASS", "LOW",
                    f"{signed_pages} signature block(s) carry two directors' DINs, the auditor's FRN, membership "
                    "number, UDIN and a date.", evidence, regs, 0.85)


BALANCE_SHEET_RULES: list[tuple[str, str, Evaluator]] = [
    ("FSBS-001", "Balance sheet balances in both years", rule_bs_both_years),
    ("FSBS-002", "Sub-totals add up to the balance sheet totals", rule_bs_subtotals),
    ("FSBS-003", "Balance sheet line items add up to their sections", rule_bs_sections_add_up),
    ("FSBS-004", "Schedule III headings on the balance sheet", rule_bs_schedule_iii_headings),
    ("FSBS-005", "Comparative figures and units stated", rule_bs_comparatives_and_units),
    ("FSBS-006", "Note totals agree with the statements", rule_notes_tie_to_statements),
    ("FSBS-007", "Statements signed by directors and auditor, with UDIN", rule_statement_signatures),
]


# --------------------------------------------------------------- profit and loss

_EXPENSE_PREFIXES = (
    "costofmaterials", "purchaseofstockintrade", "purchasesofstockintrade", "purchases", "changesininventor",
    "increasedecreaseinstock", "employeebenefit", "financecost", "depreciation", "otherexpenses",
    "manufacturingexpenses", "operatingexpenses",
)
_TAX_PREFIXES = ("currenttax", "deferredtax", "incometaxofpreviousyear", "taxexpense")
_PL_HEADINGS = [
    ("Revenue from operations", r"revenuefromoperations"), ("Other income", r"otherincome"),
    ("Total income / revenue", r"total(income|revenue)"), ("Employee benefit expense", r"employeebenefit"),
    ("Finance costs", r"financecost"), ("Depreciation", r"depreciation"), ("Other expenses", r"otherexpenses"),
    ("Total expenses", r"totalexpenses"), ("Profit before tax", r"profitbefore.{0,40}tax"),
    ("Tax expense", r"taxexpense"), ("Profit/(loss) for the year", r"profit(loss)?fortheyear"),
    ("Earnings per equity share", r"(earning|earnings)perequityshare|basic"),
]


def _pl(ctx: RuleContext) -> tuple[list[Row], ProfitAndLoss | None]:
    rows = _rows(ctx)
    return rows, _profit_and_loss(rows)


def rule_pl_headings(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "FSPL-001", "Schedule III headings on the statement of profit and loss"
    rows, pl = _pl(ctx)
    if not pl or not ctx.text.strip():
        return None
    index = TextIndex(ctx.text)
    found = [(label, index.evidence(pattern, label, 120)) for label, pattern in _PL_HEADINGS]
    missing = [label for label, ev in found if not ev]
    evidence = [ev for _, ev in found if ev][:6]
    if missing:
        return _finding(rid, title, "REVIEW", "MEDIUM",
                        "Headings not found: " + ", ".join(missing) + ".", evidence, regs, 0.75)
    return _finding(rid, title, "PASS", "LOW",
                    "Income, expense, profit, tax and earnings-per-share headings are all present.",
                    evidence, regs, 0.8)


def rule_pl_total_expenses(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "FSPL-002", "Expense lines add up to total expenses"
    _, pl = _pl(ctx)
    if not pl:
        return None
    items = [r for r in pl.rows if r is not pl.total_expenses and not r.child and r.key.startswith(_EXPENSE_PREFIXES)]
    problems = []
    for year, attr in _years(pl.total_expenses):
        diff = _sum(items, attr) - getattr(pl.total_expenses, attr)
        if abs(diff) > TOLERANCE:
            problems.append(f"{year}: expense lines add up to {_fmt(_sum(items, attr))} but total expenses are "
                            f"{_fmt(getattr(pl.total_expenses, attr))}")
    evidence = _facts(*items, pl.total_expenses)
    if problems:
        return _finding(rid, title, "FAIL", "HIGH", "; ".join(problems) + ".", evidence, regs, 0.85)
    return _finding(rid, title, "PASS", "LOW",
                    f"{len(items)} expense line(s) add up to total expenses in each year.", evidence, regs, 0.85)


def _total_income(pl: ProfitAndLoss, ctx: RuleContext) -> tuple[Row | None, list[Row]]:
    total = _find(pl.rows, "totalincome", "totalrevenue")
    if total:
        return total, [total]
    parts = [r for r in pl.rows if r.key.startswith(("revenuefromoperations", "otherincome"))]
    return None, parts


def rule_pl_profit_before_tax(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "FSPL-003", "Total income less total expenses equals profit before tax"
    _, pl = _pl(ctx)
    if not pl:
        return None
    pbt = _find(pl.rows, "profitbeforetax", exact=True)
    if not pbt:
        return None
    total_income, income_rows = _total_income(pl, ctx)
    if not income_rows and not _squashed_has(ctx, "totalincome") and not _squashed_has(ctx, "revenuefromoperations"):
        return None
    problems = []
    for year, attr in _years(pbt, pl.total_expenses):
        income = _sum(income_rows, attr)
        expected = income - getattr(pl.total_expenses, attr)
        diff = expected - getattr(pbt, attr)
        if abs(diff) > TOLERANCE:
            problems.append(f"{year}: income {_fmt(income)} less expenses {_fmt(getattr(pl.total_expenses, attr))} "
                            f"is {_fmt(expected)} but profit before tax shows {_fmt(getattr(pbt, attr))}")
    evidence = _facts(*income_rows, pl.total_expenses, pbt)
    if problems:
        return _finding(rid, title, "FAIL", "HIGH", "; ".join(problems) + ".", evidence, regs, 0.85)
    return _finding(rid, title, "PASS", "LOW",
                    "Total income less total expenses equals profit before tax in each year "
                    "(a nil total income is read from the statement text).", evidence, regs, 0.85)


def _profit_row(pl: ProfitAndLoss) -> Row | None:
    return _find(pl.rows, "profitlossfortheyear", "profitfortheyear", "profitfortheperiod", "profitaftertax",
                 "lossfortheyear")


def rule_pl_profit_after_tax(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "FSPL-004", "Profit before tax less tax equals profit for the year"
    _, pl = _pl(ctx)
    if not pl:
        return None
    pbt, profit = _find(pl.rows, "profitbeforetax", exact=True), _profit_row(pl)
    if not pbt or not profit:
        return None
    taxes = [r for r in pl.rows if not r.child and r.key.startswith(_TAX_PREFIXES)]
    problems = []
    for year, attr in _years(pbt, profit):
        expected = getattr(pbt, attr) - _sum(taxes, attr)
        diff = expected - getattr(profit, attr)
        if abs(diff) > TOLERANCE:
            problems.append(f"{year}: profit before tax {_fmt(getattr(pbt, attr))} less tax "
                            f"{_fmt(_sum(taxes, attr))} is {_fmt(expected)} but the profit for the year shows "
                            f"{_fmt(getattr(profit, attr))}")
    evidence = _facts(pbt, *taxes, profit)
    if problems:
        return _finding(rid, title, "FAIL", "HIGH", "; ".join(problems) + ".", evidence, regs, 0.85)
    return _finding(rid, title, "PASS", "LOW",
                    "Profit before tax less tax equals the profit (or loss) for the year in each year.",
                    evidence, regs, 0.85)


def rule_pl_eps(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "FSPL-005", "Earnings per share consistent with profit and share capital"
    rows, pl = _pl(ctx)
    if not pl:
        return None
    eps = next((r for r in pl.rows if "basic" in r.key or r.key.startswith(("earning", "eps"))), None)
    profit = _profit_row(pl)
    capital = _find(rows, "sharecapital")
    face = re.search(r"sharesofrs(\d{1,3})each", TextIndex(ctx.text).squashed) if ctx.text.strip() else None
    if not (eps and profit and capital and face and capital.cur):
        return None
    shares = capital.cur / Decimal(face.group(1))
    problems, notes = [], []
    for year, attr in _years(eps, profit):
        e, p = getattr(eps, attr), getattr(profit, attr)
        if e == 0 or p == 0:
            continue
        if (e > 0) != (p > 0):
            problems.append(f"{year}: EPS ({e}) and profit ({_fmt(p)}) have opposite signs")
            continue
        implied = abs(p / e)
        if attr == "cur" and abs(implied - shares) / shares > Decimal("0.02"):
            problems.append(f"{year}: the profit and EPS imply {implied:,.0f} shares but the share capital "
                            f"is {shares:,.0f} shares")
        elif attr == "prev" and abs(implied - shares) / shares > Decimal("0.02"):
            notes.append(f"the prior-year EPS implies about {implied:,.0f} shares against {shares:,.0f} in issue "
                         "(acceptable only if the shares were issued part-way through that year)")
    evidence = _facts(eps, profit, capital)
    if problems:
        return _finding(rid, title, "FAIL", "HIGH", "; ".join(problems) + ".", evidence, regs, 0.8)
    if notes:
        return _finding(rid, title, "REVIEW", "MEDIUM", "Review: " + "; ".join(notes) + ".", evidence, regs, 0.75)
    return _finding(rid, title, "PASS", "LOW",
                    f"EPS is consistent with the profit and the {shares:,.0f} shares in issue.", evidence, regs, 0.85)


PROFIT_AND_LOSS_RULES: list[tuple[str, str, Evaluator]] = [
    ("FSPL-001", "Schedule III headings on the statement of profit and loss", rule_pl_headings),
    ("FSPL-002", "Expense lines add up to total expenses", rule_pl_total_expenses),
    ("FSPL-003", "Total income less total expenses equals profit before tax", rule_pl_profit_before_tax),
    ("FSPL-004", "Profit before tax less tax equals profit for the year", rule_pl_profit_after_tax),
    ("FSPL-005", "Earnings per share consistent with profit and share capital", rule_pl_eps),
]


# ------------------------------------------------------------- across statements

def rule_reserves_rollforward(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "FSX-001", "Reserves move by the profit or loss for the year"
    rows, pl = _pl(ctx)
    sheet = _balance_sheet(rows)
    if not pl or not sheet:
        return None
    reserves = _find(sheet.liabilities, "reservesandsurplus")
    profit = _profit_row(pl)
    if not reserves or not profit or reserves.cur is None or reserves.prev is None or profit.cur is None:
        return None
    movement = reserves.cur - reserves.prev
    diff = movement - profit.cur
    evidence = _facts(reserves, profit)
    if abs(diff) <= TOLERANCE:
        return _finding(rid, title, "PASS", "LOW",
                        f"Reserves and surplus moved by {_fmt(movement)}, equal to the profit/(loss) for the year "
                        f"({_fmt(profit.cur)}), so the balance sheet and statement of profit and loss articulate.",
                        evidence, regs, 0.85)
    return _finding(rid, title, "REVIEW", "MEDIUM",
                    f"Reserves and surplus moved by {_fmt(movement)} but the profit/(loss) for the year is "
                    f"{_fmt(profit.cur)}, a difference of {_fmt(diff)}. Dividends, transfers, other comprehensive "
                    "income or an error could explain this.", evidence, regs, 0.8)


CROSS_RULES: list[tuple[str, str, Evaluator]] = [
    ("FSX-001", "Reserves move by the profit or loss for the year", rule_reserves_rollforward),
]


def _build() -> list[ComplianceRule]:
    rules = []
    for group in (BALANCE_SHEET_RULES, PROFIT_AND_LOSS_RULES, CROSS_RULES):
        for rule_id, title, evaluator in group:
            rules.append(ComplianceRule(rule_id=rule_id, title=title,
                                        statement_types={"balance_sheet", "profit_and_loss"},
                                        evaluator=evaluator))
    return rules


STATEMENT_RULES: list[ComplianceRule] = _build()
