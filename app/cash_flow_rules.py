"""Rules for the cash flow statement (AS 3 / Ind AS 7).

Indian cash flow statements follow one shape: operating activities (usually the
indirect method: profit before tax, adjustments, working-capital changes, cash
generated, tax paid), then investing, then financing, then the net change and
the opening and closing cash. The rules check that the arithmetic holds in both
years, that years join up, and that the statement agrees with the balance sheet
and the statement of profit and loss.

They use the extracted rows (``facts``, each with every column, current year
first). A passing result means the statement is internally consistent and ties
to the other statements; it does not prove the cash flows are right.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

from app.rules_engine import ComplianceFinding, ComplianceRule, RegulationEvidence, RuleContext
from app.statement_rules import (
    TOLERANCE,
    ZERO,
    Row,
    _balance_sheet,
    _find,
    _facts,
    _fmt,
    _profit_and_loss,
    _rows,
)
from app.text_rules import Evaluator, TextIndex, _finding

_PBT = ("netprofitbeforetax", "profitbeforetax", "profitlossbeforetax", "netprofitlossbeforetax",
        "netprofitbeforeextraordinary")
_OP_PROFIT = ("operatingprofitbefore", "operatingprofitlossbefore", "operatingcashflowbefore")
_CASH_GEN = ("cashgeneratedfromoperations", "cashgeneratedfromusedinoperations", "cashfromoperations",
             "cashflowfromoperations")
_ACTIVITY = {"operating": "operatingactivit", "investing": "investingactivit", "financing": "financingactivit"}
_LABELS = {"operating": "operating activities", "investing": "investing activities",
           "financing": "financing activities"}


@dataclass
class CashFlow:
    rows: list[Row]
    start: int  # first row of the statement
    idx: dict[str, int]  # named anchors -> index into rows


def _first(rows: list[Row], pred: Callable[[Row], bool], start: int = 0, stop: int | None = None) -> int | None:
    for i in range(start, len(rows) if stop is None else stop):
        if pred(rows[i]):
            return i
    return None


def _net_of(rows: list[Row], word: str, start: int = 0) -> int | None:
    return _first(rows, lambda r: word in r.key and r.key.startswith(("net", "cash")), start)


def _cash_flow(rows: list[Row]) -> CashFlow | None:
    idx: dict[str, int] = {}
    op = _net_of(rows, _ACTIVITY["operating"])
    inv = _net_of(rows, _ACTIVITY["investing"], op or 0)
    fin = _net_of(rows, _ACTIVITY["financing"], inv if inv is not None else (op or 0))
    for name, i in (("operating", op), ("investing", inv), ("financing", fin)):
        if i is not None:
            idx[name] = i
    anchors = [i for i in (op, inv, fin) if i is not None]
    if not anchors:
        return None
    page = rows[anchors[0]].page
    start = next(i for i, r in enumerate(rows) if r.page == page)
    stop = anchors[0]
    pbt = _first(rows, lambda r: r.key.startswith(_PBT) and r.page == page, start, stop)
    if pbt is not None:
        idx["pbt"] = pbt
    if op is not None:
        for name, prefixes in (("opprofit", _OP_PROFIT), ("cashgen", _CASH_GEN)):
            i = _first(rows, lambda r: r.key.startswith(prefixes), start, op)
            if i is not None:
                idx[name] = i
    after = max(anchors)
    net = _first(rows, lambda r: r.key.startswith(("netincrease", "netdecrease", "netchange", "increasedecrease"))
                 and "cash" in r.key, start)
    if net is not None:
        idx["net"] = net
        after = max(after, net)
    opening = _first(rows, lambda r: "cash" in r.key and ("beginning" in r.key or "opening" in r.key), start)
    closing = _first(rows, lambda r: "cash" in r.key and ("endof" in r.key or "closing" in r.key), start)
    for name, i in (("opening", opening), ("closing", closing)):
        if i is not None:
            idx[name] = i
            after = max(after, i)
    return CashFlow(rows[:after + 1], start, idx)


def _row(cf: CashFlow, name: str) -> Row | None:
    return cf.rows[cf.idx[name]] if name in cf.idx else None


def _between(cf: CashFlow, a: int, b: int) -> list[Row]:
    return [r for r in cf.rows[a + 1:b] if not r.child]


def _all_years(*rows: Row | None) -> list[tuple[str, str]]:
    present = [r for r in rows if r is not None]
    years = [("current year", "cur")]
    if present and all(r.prev is not None for r in present):
        years.append(("prior year", "prev"))
    return years


def _mentioned(ctx: RuleContext, pattern: str) -> bool:
    return bool(ctx.text.strip()) and TextIndex(ctx.text).has(pattern)


def _cf(ctx: RuleContext) -> tuple[list[Row], CashFlow | None]:
    rows = _rows(ctx)
    return rows, _cash_flow(rows)


def _section_total(cf: CashFlow, ctx: RuleContext, name: str) -> tuple[Row | None, bool]:
    """(row, exists): a nil total is all dashes, so it never reaches the facts."""
    row = _row(cf, name)
    return row, row is not None or _mentioned(ctx, _ACTIVITY[name])


# --------------------------------------------------------------------------- rules

def rule_cf_structure(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "CFS-001", "Cash flow statement has all required parts (AS 3 / Ind AS 7)"
    rows, cf = _cf(ctx)
    if cf is None:
        if ctx.document_type != "cash_flow":
            return None
        return _finding(rid, title, "FAIL", "HIGH",
                        "No net cash flow totals for operating, investing or financing activities were found.",
                        [], regs, 0.8)
    missing = []
    for name in ("operating", "investing", "financing"):
        _, exists = _section_total(cf, ctx, name)
        if not exists:
            missing.append(f"net cash from {_LABELS[name]}")
    for name, label in (("net", "net increase/(decrease) in cash"), ("opening", "opening cash and cash equivalents"),
                        ("closing", "closing cash and cash equivalents")):
        if name not in cf.idx:
            missing.append(label)
    evidence = _facts(*(cf.rows[i] for i in cf.idx.values()))
    if missing:
        return _finding(rid, title, "FAIL" if len(missing) > 2 else "REVIEW", "HIGH",
                        "Not found: " + "; ".join(missing) + ".", evidence, regs, 0.8)
    return _finding(rid, title, "PASS", "LOW",
                    "Operating, investing and financing activities, the net change and the opening and closing "
                    "cash are all present.", evidence, regs, 0.85)


def rule_cf_operating(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "CFS-002", "Operating activities add up"
    _, cf = _cf(ctx)
    op = _row(cf, "operating") if cf else None
    if not cf or op is None:
        return None
    op_i = cf.idx["operating"]
    anchors = sorted(cf.idx[n] for n in ("pbt", "opprofit", "cashgen") if n in cf.idx and cf.idx[n] < op_i)
    chain = anchors + [op_i]
    # Each step runs from one recognised subtotal to the next; with none, sum every line.
    segments = [(chain[k], chain[k + 1]) for k in range(len(chain) - 1)] if anchors else [(None, op_i)]
    sloppy = not anchors
    problems, evidence, checked = [], [op.fact], 0
    for a, b in segments:
        start_row, end = (cf.rows[a] if a is not None else None), cf.rows[b]
        lines = _between(cf, a, b) if a is not None else [r for r in cf.rows[cf.start:b] if not r.child]
        if not lines and start_row is None:
            continue
        evidence += _facts(start_row, *lines, end)
        for year, attr in _all_years(end, start_row):
            base = getattr(start_row, attr) if start_row is not None else ZERO
            movement = sum((getattr(r, attr + "0") for r in lines), ZERO)
            expected = base + movement
            actual = getattr(end, attr)
            ok = abs(expected - actual) <= TOLERANCE
            if not ok and b == op_i and lines and all("tax" in r.key for r in lines):
                ok = abs(base - movement - actual) <= TOLERANCE  # tax shown as a positive deduction
            checked += 1
            if not ok:
                problems.append(f"{year}: {start_row.label if start_row else 'the lines'} "
                                f"{'plus' if start_row else 'total'} {_fmt(movement)} gives {_fmt(expected)} but "
                                f"'{end.label}' shows {_fmt(actual)}")
    if not checked:
        return None
    if problems:
        status, sev = ("REVIEW", "MEDIUM") if sloppy else ("FAIL", "HIGH")
        extra = " Subtotal rows may not have been recognised." if sloppy else ""
        return _finding(rid, title, status, sev, "; ".join(problems) + "." + extra, evidence, regs, 0.8)
    return _finding(rid, title, "PASS", "LOW",
                    f"The operating section adds up through each recognised step ({checked} check(s)).",
                    evidence, regs, 0.85)


def rule_cf_investing_financing(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "CFS-003", "Investing and financing totals add up"
    _, cf = _cf(ctx)
    if not cf:
        return None
    sections = []
    order = [n for n in ("operating", "investing", "financing") if n in cf.idx]
    for name in ("investing", "financing"):
        if name not in cf.idx:
            continue
        position = order.index(name)
        lines = (_between(cf, cf.idx[order[position - 1]], cf.idx[name]) if position
                 else [r for r in cf.rows[cf.start:cf.idx[name]] if not r.child])
        sections.append((name, lines, cf.rows[cf.idx[name]]))
    problems, evidence, checked = [], [], 0
    for name, lines, total in sections:
        if not lines:
            continue
        evidence += _facts(*lines, total)
        for year, attr in _all_years(total):
            summed = sum((getattr(r, attr + "0") for r in lines), ZERO)
            checked += 1
            if abs(summed - getattr(total, attr)) > TOLERANCE:
                problems.append(f"{_LABELS[name]} ({year}): the lines add up to {_fmt(summed)} but the total is "
                                f"{_fmt(getattr(total, attr))}")
    if not checked:
        return None
    if problems:
        return _finding(rid, title, "FAIL", "HIGH", "; ".join(problems) + ".", evidence, regs, 0.85)
    return _finding(rid, title, "PASS", "LOW",
                    "The lines add up to the investing and financing totals in each year.", evidence, regs, 0.85)


def _sections(cf: CashFlow, ctx: RuleContext) -> list[tuple[str, Row | None]]:
    return [(n, _section_total(cf, ctx, n)[0]) for n in ("operating", "investing", "financing")]


def rule_cf_net_change(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "CFS-004", "Net change in cash equals A + B + C"
    _, cf = _cf(ctx)
    net = _row(cf, "net") if cf else None
    if not cf or net is None:
        return None
    totals = _sections(cf, ctx)
    if not any(row for _, row in totals):
        return None
    problems = []
    for year, attr in _all_years(net):
        total = sum((getattr(r, attr + "0") for _, r in totals if r is not None), ZERO)
        if abs(total - getattr(net, attr)) > TOLERANCE:
            problems.append(f"{year}: operating + investing + financing is {_fmt(total)} but the net change is "
                            f"{_fmt(getattr(net, attr))}")
    evidence = _facts(*(r for _, r in totals), net)
    if problems:
        return _finding(rid, title, "FAIL", "HIGH", "; ".join(problems) + ".", evidence, regs, 0.9)
    return _finding(rid, title, "PASS", "LOW",
                    "Operating, investing and financing cash flows add up to the net change in each year.",
                    evidence, regs, 0.9)


def rule_cf_closing(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "CFS-005", "Opening cash plus net change equals closing cash"
    _, cf = _cf(ctx)
    if not cf or not all(n in cf.idx for n in ("net", "opening", "closing")):
        return None
    net, opening, closing = _row(cf, "net"), _row(cf, "opening"), _row(cf, "closing")
    problems = []
    for year, attr in _all_years(net, opening, closing):
        expected = getattr(opening, attr) + getattr(net, attr)
        if abs(expected - getattr(closing, attr)) > TOLERANCE:
            problems.append(f"{year}: opening {_fmt(getattr(opening, attr))} plus net change "
                            f"{_fmt(getattr(net, attr))} is {_fmt(expected)} but closing cash is "
                            f"{_fmt(getattr(closing, attr))}")
        elif getattr(closing, attr) < 0:
            problems.append(f"{year}: closing cash is negative ({_fmt(getattr(closing, attr))}); an overdraft "
                            "may be included in cash and cash equivalents")
    evidence = _facts(opening, net, closing)
    if problems:
        return _finding(rid, title, "FAIL", "HIGH", "; ".join(problems) + ".", evidence, regs, 0.9)
    return _finding(rid, title, "PASS", "LOW",
                    "Opening cash plus the net change equals closing cash in each year.", evidence, regs, 0.9)


def rule_cf_continuity(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "CFS-006", "Opening cash equals the prior year's closing cash"
    _, cf = _cf(ctx)
    opening, closing = (_row(cf, "opening"), _row(cf, "closing")) if cf else (None, None)
    if not opening or not closing or opening.cur is None or closing.prev is None:
        return None
    diff = opening.cur - closing.prev
    evidence = _facts(opening, closing)
    if abs(diff) <= TOLERANCE:
        return _finding(rid, title, "PASS", "LOW",
                        f"The current-year opening cash ({_fmt(opening.cur)}) equals the prior-year closing cash.",
                        evidence, regs, 0.9)
    return _finding(rid, title, "FAIL", "HIGH",
                    f"The current-year opening cash is {_fmt(opening.cur)} but the prior-year closing cash was "
                    f"{_fmt(closing.prev)}, a difference of {_fmt(diff)}.", evidence, regs, 0.9)


def rule_cf_ties_to_balance_sheet(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "CFS-007", "Closing cash agrees with the balance sheet"
    rows, cf = _cf(ctx)
    closing = _row(cf, "closing") if cf else None
    sheet = _balance_sheet(rows)
    if closing is None or not sheet:
        return None
    cash = _find(sheet.assets, "cashandcashequivalents")
    if cash is None:
        return None
    problems = []
    for year, attr in _all_years(closing, cash):
        diff = getattr(closing, attr) - getattr(cash, attr)
        if abs(diff) > TOLERANCE:
            problems.append(f"{year}: closing cash is {_fmt(getattr(closing, attr))} but the balance sheet shows "
                            f"{_fmt(getattr(cash, attr))}")
    evidence = _facts(closing, cash)
    if problems:
        return _finding(rid, title, "FAIL", "MEDIUM",
                        "; ".join(problems) + ". Cash and cash equivalents should agree unless bank overdrafts "
                        "or restricted balances are treated differently.", evidence, regs, 0.85)
    return _finding(rid, title, "PASS", "LOW",
                    "Closing cash and cash equivalents agree with the balance sheet in each year.",
                    evidence, regs, 0.9)


def rule_cf_ties_to_profit_and_loss(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "CFS-008", "Profit, depreciation and finance cost agree with the statement of profit and loss"
    rows, cf = _cf(ctx)
    pl = _profit_and_loss(rows)
    if not cf or not pl:
        return None
    cf_rows = cf.rows[cf.start:]
    pairs = [
        ("profit before tax", _row(cf, "pbt"), _find(pl.rows, "profitbeforetax", exact=True)),
        ("depreciation", _find(cf_rows, "depreciation"), _find(pl.rows, "depreciation")),
        ("finance cost", _find(cf_rows, "financecost", "interestexpense"), _find(pl.rows, "financecost")),
    ]
    problems, evidence, compared = [], [], 0
    for label, in_cf, in_pl in pairs:
        if in_cf is None or in_pl is None:
            continue
        evidence += _facts(in_cf, in_pl)
        for year, attr in _all_years(in_cf, in_pl):
            compared += 1
            # Finance cost in the cash flow may be shown with the opposite sign when paid.
            a, b = getattr(in_cf, attr), getattr(in_pl, attr)
            if abs(a - b) > TOLERANCE and abs(abs(a) - abs(b)) > TOLERANCE:
                problems.append(f"{label} ({year}): {_fmt(a)} in the cash flow statement but {_fmt(b)} in the "
                                "statement of profit and loss")
    if not compared:
        return None
    if problems:
        return _finding(rid, title, "FAIL", "HIGH", "; ".join(problems) + ".", evidence, regs, 0.85)
    return _finding(rid, title, "PASS", "LOW",
                    f"{compared} figure(s) agree between the cash flow statement and the statement of profit and loss.",
                    evidence, regs, 0.85)


def rule_cf_included(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "CFS-009", "Cash flow statement included (s.2(40))"
    rows = _rows(ctx)
    if not (_balance_sheet(rows) and _profit_and_loss(rows)):
        return None  # not a full set of statements, so completeness cannot be judged
    if _cash_flow(rows) or _mentioned(ctx, r"(cashflowstatement|statementofcashflows|cashflowsfromoperatingactivities)"):
        return _finding(rid, title, "PASS", "LOW",
                        "A cash flow statement accompanies the balance sheet and statement of profit and loss.",
                        [], regs, 0.8)
    return _finding(rid, title, "REVIEW", "LOW",
                    "The balance sheet and statement of profit and loss are present but no cash flow statement "
                    "was found. Financial statements include a cash flow statement (s.2(40)) unless the company "
                    "is a one person company, a small company or a dormant company. Confirm whether it applies "
                    "or whether the statement was omitted from this document.", [], regs, 0.7)


CASH_FLOW_RULES: list[tuple[str, str, Evaluator]] = [
    ("CFS-001", "Cash flow statement has all required parts (AS 3 / Ind AS 7)", rule_cf_structure),
    ("CFS-002", "Operating activities add up", rule_cf_operating),
    ("CFS-003", "Investing and financing totals add up", rule_cf_investing_financing),
    ("CFS-004", "Net change in cash equals A + B + C", rule_cf_net_change),
    ("CFS-005", "Opening cash plus net change equals closing cash", rule_cf_closing),
    ("CFS-006", "Opening cash equals the prior year's closing cash", rule_cf_continuity),
    ("CFS-007", "Closing cash agrees with the balance sheet", rule_cf_ties_to_balance_sheet),
    ("CFS-008", "Profit, depreciation and finance cost agree with the statement of profit and loss",
     rule_cf_ties_to_profit_and_loss),
    ("CFS-009", "Cash flow statement included (s.2(40))", rule_cf_included),
]


def _build() -> list[ComplianceRule]:
    return [
        ComplianceRule(rule_id=rule_id, title=title,
                       statement_types={"cash_flow", "balance_sheet", "profit_and_loss"}, evaluator=evaluator)
        for rule_id, title, evaluator in CASH_FLOW_RULES
    ]


CASH_FLOW_STATEMENT_RULES: list[ComplianceRule] = _build()
