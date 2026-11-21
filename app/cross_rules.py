"""Cross-document checks for an annual filing package.

Each per-document rule looks at one document. These rules compare documents with
each other: the Directors' Report, the Auditor's Report, the financial
statements and the AGM notice should agree on who the company is, which year
they cover, who the auditor is, what the results were, and in what order they
were signed.

A rule runs only when the documents it needs are present, and says nothing
otherwise. Agreement between documents does not make them correct, and a
disagreement may have an innocent explanation; findings quote the passages on
both sides so a reviewer can judge.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Callable

from app.notice_invoice_rules import _meeting_datetime
from app.rules_engine import ComplianceFinding, RuleContext
from app.statement_rules import (
    TOLERANCE,
    Row,
    _balance_sheet,
    _find,
    _fmt,
    _profit_and_loss,
    _profit_row,
    _rows,
)
from app.text_rules import _MODIFIED_OPINION, TextIndex, _finding, _period_end, _signature_date

FS_TYPES = {"balance_sheet", "profit_and_loss", "cash_flow"}
LABELS = {"directors_report": "Directors' Report", "auditors_report": "Auditor's Report",
          "agm_notice": "AGM notice", "balance_sheet": "Financial statements",
          "profit_and_loss": "Financial statements", "cash_flow": "Financial statements"}


@dataclass
class Doc:
    type: str
    name: str
    text: str
    facts: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.index = TextIndex(self.text)
        self.kind = LABELS.get(self.type, self.type)  # used in messages
        self.label = self.name or self.kind  # used in evidence

    @property
    def context(self) -> RuleContext:
        return RuleContext(document_type=self.type, facts=self.facts, text=self.text)

    def evidence(self, pattern: str, label: str, width: int = 200) -> dict[str, Any] | None:
        found = self.index.evidence(pattern, label, width)
        if found:
            found["label"] = f"{self.label} — {label}"
            found["document"] = self.label
        return found


class Package:
    def __init__(self, docs: list[Doc]):
        self.docs = docs

    def of(self, *types: str) -> list[Doc]:
        return [d for d in self.docs if d.type in types]

    def one(self, *types: str) -> Doc | None:
        found = self.of(*types)
        return found[0] if found else None

    def statements(self) -> list[Doc]:
        return self.of(*FS_TYPES)

    def profit_and_loss(self):
        for doc in self.statements():
            rows = _rows(doc.context)
            pl = _profit_and_loss(rows)
            if pl:
                return doc, rows, pl
        return None

    def balance_sheet(self):
        for doc in self.statements():
            rows = _rows(doc.context)
            sheet = _balance_sheet(rows)
            if sheet:
                return doc, rows, sheet
        return None


Rule = Callable[[Package], ComplianceFinding | None]


def _upper_first(text: str) -> str:
    return text[:1].upper() + text[1:]


def _result(rid: str, title: str, status: str, severity: str, message: str,
            evidence: list[dict[str, Any] | None], confidence: float = 0.8) -> ComplianceFinding:
    return _finding(rid, title, status, severity, message, [e for e in evidence if e], [], confidence)


def _row_evidence(doc: Doc, row: Row | None, label: str) -> dict[str, Any] | None:
    if row is None:
        return None
    return {"label": f"{doc.label} — {label}", "value": row.label, "source_page": row.page, "document": doc.label}


# ----------------------------------------------------------------------- identity

_CIN = r"cin(?:no)?([a-z]\d{5}[a-z]{2}\d{4}[a-z]{3}\d{6})"
_ENTITY_DOCS = ("directors_report", "auditors_report", "agm_notice", *FS_TYPES)


def _company_core(docs: list[Doc]) -> str | None:
    """The company's name token, read from a letterhead that opens with 'X Private Limited'."""
    for doc in docs:
        match = re.match(r"([a-z0-9]{3,30}?)(?:private|pvt)(?:limited|ltd)", doc.index.squashed[:80])
        if match:
            return match.group(1)
    return None


def xdoc_identity(pkg: Package) -> ComplianceFinding | None:
    rid, title = "XDOC-001", "Company name and CIN agree across documents"
    docs = pkg.of(*_ENTITY_DOCS)
    if len(docs) < 2:
        return None
    ordered = sorted(docs, key=lambda d: d.type not in ("directors_report", *FS_TYPES))
    core = _company_core(ordered)
    cins = {d.kind: set(re.findall(_CIN, d.index.squashed)) for d in docs}
    stated = {name: c for name, c in cins.items() if c}
    distinct = set().union(*stated.values()) if stated else set()
    problems, evidence = [], []
    if len(distinct) > 1:
        problems.append("different CINs appear: " + "; ".join(f"{n}: {', '.join(sorted(c)).upper()}"
                                                              for n, c in stated.items()))
    for doc in docs:
        if doc.kind in stated:
            evidence.append(doc.evidence(_CIN, "CIN", 60))
    unnamed = []
    if core:
        mention = rf"{re.escape(core)}(?:private|pvt)(?:limited|ltd)"
        for doc in docs:
            found = doc.evidence(mention, "Company name", 80)
            (evidence if found else unnamed).append(found or doc.kind)
    elif not stated:
        return None
    if problems:
        return _result(rid, title, "FAIL", "HIGH", _upper_first("; ".join(problems)) + ".", evidence, 0.9)
    if unnamed:
        return _result(rid, title, "REVIEW", "LOW",
                       f"The company name '{core}' is not found in: " + ", ".join(unnamed) + ". "
                       "The documents should identify the same company by name.", evidence, 0.75)
    cin_note = f" and share the CIN {next(iter(distinct)).upper()}" if distinct else ""
    return _result(rid, title, "PASS", "LOW",
                   f"{len(docs)} documents name the same company{cin_note}.", evidence, 0.85)


def xdoc_period(pkg: Package) -> ComplianceFinding | None:
    rid, title = "XDOC-002", "Financial year-end agrees across documents"
    docs = pkg.of(*_ENTITY_DOCS)
    ends = {d.kind: _period_end(d.index) for d in docs}
    ends = {name: end for name, end in ends.items() if end}
    if len(ends) < 2:
        return None
    evidence = [d.evidence(r"(31|30|29|28)(st|nd|rd|th)?(january|february|march|april|may|june|july|august|"
                           r"september|october|november|december)\d{4}|(january|february|march|april|may|june|"
                           r"july|august|september|october|november|december)\d{1,2}(st|nd|rd|th)?\d{4}",
                           "Year-end date", 80) for d in docs if d.kind in ends]
    if len(set(ends.values())) > 1:
        return _result(rid, title, "FAIL", "HIGH",
                       "The documents refer to different year-ends: "
                       + "; ".join(f"{n}: {e:%d %b %Y}" for n, e in ends.items()) + ".", evidence, 0.85)
    only = next(iter(ends.values()))
    return _result(rid, title, "PASS", "LOW",
                   f"All {len(ends)} documents refer to the year ended {only:%d %b %Y}.", evidence, 0.85)


# ---------------------------------------------------------------------- the auditor

_AUDITOR_NAME = r"ms(.{3,40}?)charteredaccountants"


def _auditor_core(doc: Doc | None) -> str | None:
    if not doc:
        return None
    match = re.search(_AUDITOR_NAME, doc.index.squashed)
    return match.group(1) if match else None


def xdoc_auditor(pkg: Package) -> ComplianceFinding | None:
    rid, title = "XDOC-003", "Auditor named consistently across documents"
    report = pkg.one("auditors_report")
    others = [d for d in pkg.of("directors_report", "agm_notice", *FS_TYPES)]
    if not report or not others:
        return None
    named = [(d, _auditor_core(d)) for d in pkg.of("directors_report", "agm_notice")]
    named = [(d, c) for d, c in named if c]
    signers = [d for d in [report, *pkg.statements()] if re.search(r"frn\d{5,6}", d.index.squashed)]
    frns = {d.kind: set(re.findall(r"frn(\d{5,6}[a-z]?)", d.index.squashed)) for d in signers}
    members = {d.kind: set(re.findall(r"(?:mno|membershipno)(\d{6})", d.index.squashed)) for d in signers}
    problems, evidence = [], []
    all_frns = set().union(*frns.values()) if frns else set()
    all_members = set().union(*members.values()) if members else set()
    if len(all_frns) > 1:
        problems.append("different firm registration numbers: " + "; ".join(
            f"{n}: {', '.join(sorted(v)).upper()}" for n, v in frns.items() if v))
    if len(all_members) > 1:
        problems.append("different membership numbers: " + "; ".join(
            f"{n}: {', '.join(sorted(v))}" for n, v in members.items() if v))
    for doc, core in named:
        evidence.append(doc.evidence(_AUDITOR_NAME, "Auditor named", 160))
        if core not in report.index.squashed:
            problems.append(f"{doc.kind} appoints '{core}' but that name does not appear in the Auditor's Report")
    for doc in signers:
        evidence.append(doc.evidence(r"frn\d{5,6}", "Auditor FRN", 160))
    if not named and not all_frns:
        return None
    if problems:
        return _result(rid, title, "FAIL", "HIGH", _upper_first("; ".join(problems)) + ".", evidence, 0.85)
    parts = []
    if named:
        parts.append("the firm named in the " + " and ".join(d.kind for d, _ in named) + " signed the report")
    if all_frns:
        parts.append(f"the firm registration number {next(iter(all_frns)).upper()} is the same wherever it appears")
    return _result(rid, title, "PASS", "LOW", "Consistent: " + "; ".join(parts) + ".", evidence, 0.85)


# ---------------------------------------------------------------------------- dates

def _signed(doc: Doc) -> date | None:
    return _signature_date(doc.index)


def xdoc_dates(pkg: Package) -> ComplianceFinding | None:
    rid, title = "XDOC-004", "Documents are signed in a sensible order"
    statements = [d for d in pkg.statements() if _signed(d)]
    pairs = {
        "financial statements": _signed(statements[0]) if statements else None,
        "Directors' Report": _signed(pkg.one("directors_report")) if pkg.one("directors_report") else None,
        "Auditor's Report": _signed(pkg.one("auditors_report")) if pkg.one("auditors_report") else None,
        "AGM notice": _signed(pkg.one("agm_notice")) if pkg.one("agm_notice") else None,
    }
    dates = {name: d for name, d in pairs.items() if d}
    if len(dates) < 2:
        return None
    issues = []
    audit, notice = dates.get("Auditor's Report"), dates.get("AGM notice")
    directors_date = dates.get("Directors' Report")
    if audit and "financial statements" in dates and audit < dates["financial statements"]:
        issues.append(f"the Auditor's Report ({audit:%d %b %Y}) is dated before the financial statements "
                      f"were signed ({dates['financial statements']:%d %b %Y})")
    if audit and directors_date and audit < directors_date:
        issues.append(f"the Auditor's Report ({audit:%d %b %Y}) is dated before the Directors' Report "
                      f"({directors_date:%d %b %Y}); the Board should approve the statements before the "
                      "auditor signs")
    if notice:
        later = [n for n in ("financial statements", "Directors' Report", "Auditor's Report")
                 if n in dates and dates[n] > notice]
        for name in later:
            issues.append(f"the AGM notice ({notice:%d %b %Y}) is dated before the {name} ({dates[name]:%d %b %Y})")
    docs = {"financial statements": statements[0] if statements else None,
            "Directors' Report": pkg.one("directors_report"), "Auditor's Report": pkg.one("auditors_report"),
            "AGM notice": pkg.one("agm_notice")}
    evidence = [docs[n].evidence(r"dated?\d{8}", f"{n} date", 60) for n in dates if docs[n]]
    summary = ", ".join(f"{n} {d:%d %b %Y}" for n, d in sorted(dates.items(), key=lambda x: x[1]))
    if issues:
        return _result(rid, title, "REVIEW", "MEDIUM", "Review the order of dates: " + "; ".join(issues) + ".",
                       evidence, 0.75)
    return _result(rid, title, "PASS", "LOW", f"Dates are in a sensible order: {summary}.", evidence, 0.8)


# ----------------------------------------------------- directors' report vs auditor

_SELF_EXPLANATORY = r"(selfexplanatory|donotcall(s)?foranyfurthercomment|neednofurthercomment)"


def xdoc_board_comments(pkg: Package) -> ComplianceFinding | None:
    rid, title = "XDOC-005", "Board's reply matches the auditor's opinion (s.134(3)(f))"
    dr, ar = pkg.one("directors_report"), pkg.one("auditors_report")
    if not dr or not ar:
        return None
    modified = _MODIFIED_OPINION.search(ar.index.squashed)
    comments = dr.evidence(r"commentsbyboard.{0,160}", "Board's comments on the auditor's report", 240)
    self_explanatory = dr.index.has(_SELF_EXPLANATORY)
    evidence = [comments, ar.evidence(r"inouropinion", "Opinion", 200)]
    if modified:
        extra = ar.evidence(_MODIFIED_OPINION.pattern, "Modification wording", 160)
        evidence.append(extra)
        if not comments:
            return _result(rid, title, "FAIL", "HIGH",
                           "The auditor's report appears modified, but the Directors' Report has no section giving "
                           "the Board's explanations or comments (s.134(3)(f)).", evidence, 0.8)
        if self_explanatory:
            return _result(rid, title, "REVIEW", "HIGH",
                           "The auditor's report appears modified (qualified, adverse or disclaimer), yet the "
                           "Directors' Report calls the observations 'self-explanatory'. The Board should explain "
                           "each qualification (s.134(3)(f)).", evidence, 0.8)
        return _result(rid, title, "PASS", "LOW",
                       "The auditor's report appears modified and the Directors' Report responds to it.",
                       evidence, 0.7)
    if not comments:
        return _result(rid, title, "REVIEW", "LOW",
                       "The Directors' Report does not mention the auditor's report. It should at least say there "
                       "is nothing to explain.", evidence, 0.7)
    return _result(rid, title, "PASS", "LOW",
                   "The auditor's opinion is not modified and the Directors' Report addresses the auditor's report.",
                   evidence, 0.8)


# ------------------------------------------------------- results across documents

def _sign_word(value: Decimal) -> str:
    return "loss" if value < 0 else "profit"


def xdoc_results_wording(pkg: Package) -> ComplianceFinding | None:
    rid, title = "XDOC-006", "Profit or loss is described consistently"
    found = pkg.profit_and_loss()
    if not found:
        return None
    fs_doc, rows, pl = found
    profit = _profit_row(pl)
    if not profit or profit.cur is None:
        return None
    truth = {"current year": profit.cur, "prior year": profit.prev}
    issues, evidence, checked = [], [_row_evidence(fs_doc, profit, "Profit/(loss) for the year")], 0
    ar, dr = pkg.one("auditors_report"), pkg.one("directors_report")
    if ar:
        said = ar.index.search(r"andits(loss|profit)fortheyearended")
        if said:
            checked += 1
            evidence.append(ar.evidence(r"andits(loss|profit)fortheyearended", "Opinion wording", 160))
            if said.group(1) != _sign_word(profit.cur) and profit.cur != 0:
                issues.append(f"the Auditor's Report refers to the company's {said.group(1)} but the statements "
                              f"show a {_sign_word(profit.cur)} of {_fmt(abs(profit.cur))}")
    if dr:
        said = dr.index.search(r"net(loss|profit)ofrs(\d+)asagainstnet(loss|profit)ofrs(\d+)")
        if said:
            checked += 1
            evidence.append(dr.evidence(r"net(loss|profit)ofrs\d+asagainstnet(loss|profit)ofrs\d+",
                                        "Operations narrative", 220))
            for year, word, amount in (("current year", said.group(1), said.group(2)),
                                       ("prior year", said.group(3), said.group(4))):
                actual = truth[year]
                if actual is None:
                    continue
                if word != _sign_word(actual) and actual != 0:
                    issues.append(f"the Directors' Report says a net {word} of Rs. {int(amount):,} for the "
                                  f"{year}, but the statements show a {_sign_word(actual)} of {_fmt(abs(actual))}")
                elif abs(abs(actual) - Decimal(amount)) > TOLERANCE:
                    issues.append(f"the Directors' Report gives Rs. {int(amount):,} for the {year} but the "
                                  f"statements show {_fmt(abs(actual))}")
    if not checked:
        return None
    if issues:
        return _result(rid, title, "FAIL", "HIGH", _upper_first("; ".join(issues)) + ".", evidence, 0.85)
    return _result(rid, title, "PASS", "LOW",
                   "The profit or loss described in the reports agrees with the statements.", evidence, 0.85)


def xdoc_financial_summary(pkg: Package) -> ComplianceFinding | None:
    rid, title = "XDOC-007", "Directors' Report financial summary agrees with the statements"
    dr, found = pkg.one("directors_report"), pkg.profit_and_loss()
    if not dr or not found:
        return None
    fs_doc, _, pl = found
    dr_rows = []
    for r in _rows(dr.context):
        r.key = re.sub(r"^\d{1,2}", "", r.key)
        dr_rows.append(r)
    eps = next((r for r in pl.rows if "basic" in r.key or r.key.startswith(("earning", "eps"))), None)
    pairs = [
        ("total expenditure", _find(dr_rows, "totalexpenditure", "totalexpenses"), pl.total_expenses, TOLERANCE),
        ("profit before tax", _find(dr_rows, "profitbeforetax"), _find(pl.rows, "profitbeforetax", exact=True), TOLERANCE),
        ("profit after tax", _find(dr_rows, "profitaftertax", "profitfortheyear"), _profit_row(pl), TOLERANCE),
        ("EPS", _find(dr_rows, "eps", "earning"), eps, Decimal("0.01")),
    ]
    issues, evidence, compared = [], [], 0
    for label, in_dr, in_fs, tolerance in pairs:
        if in_dr is None or in_fs is None:
            continue
        evidence += [_row_evidence(dr, in_dr, label), _row_evidence(fs_doc, in_fs, label)]
        for year, attr in (("current year", "cur"), ("prior year", "prev")):
            a, b = getattr(in_dr, attr), getattr(in_fs, attr)
            if a is None or b is None:
                continue
            compared += 1
            if abs(a - b) > tolerance:
                issues.append(f"{label} ({year}): {_fmt(a)} in the Directors' Report but {_fmt(b)} in the statements")
    if not compared:
        return None
    if issues:
        return _result(rid, title, "FAIL", "HIGH", "; ".join(issues) + ".", evidence, 0.85)
    return _result(rid, title, "PASS", "LOW",
                   f"{compared} figures in the Directors' Report summary agree with the statements.", evidence, 0.85)


def xdoc_share_capital(pkg: Package) -> ComplianceFinding | None:
    rid, title = "XDOC-008", "Share capital change matches the Directors' Report"
    dr, found = pkg.one("directors_report"), pkg.balance_sheet()
    if not dr or not found:
        return None
    claim = dr.evidence(r"nochangein(share|sharecapital)c[a-z]{3,7}|nochangeinshare[a-z]{0,3}capital", "Share capital statement")
    if not claim:
        return None
    fs_doc, _, sheet = found
    capital = _find(sheet.liabilities, "sharecapital")
    if capital is None or capital.cur is None or capital.prev is None:
        return None
    evidence = [claim, _row_evidence(fs_doc, capital, "Share capital")]
    if abs(capital.cur - capital.prev) <= TOLERANCE:
        return _result(rid, title, "PASS", "LOW",
                       f"The Directors' Report says there was no change in share capital and the balance sheet "
                       f"shows {_fmt(capital.cur)} in both years.", evidence, 0.85)
    return _result(rid, title, "FAIL", "HIGH",
                   f"The Directors' Report says there was no change in share capital, but the balance sheet "
                   f"shows {_fmt(capital.prev)} in the prior year and {_fmt(capital.cur)} in the current year.",
                   evidence, 0.9)


_DIN = r"(?<!u)din(?:no)?(\d{8})"


def xdoc_directors(pkg: Package) -> ComplianceFinding | None:
    rid, title = "XDOC-009", "Same directors sign the Directors' Report and the statements"
    dr, statements = pkg.one("directors_report"), pkg.statements()
    if not dr or not statements:
        return None
    report = set(re.findall(_DIN, dr.index.squashed))
    signing = {d.kind: set(re.findall(_DIN, d.index.squashed)) for d in statements}
    signing = {n: s for n, s in signing.items() if s}
    if not report or not signing:
        return None
    evidence = [dr.evidence(_DIN, "Director DIN", 80)] + [d.evidence(_DIN, "Director DIN", 80)
                                                         for d in statements if d.kind in signing]
    differing = {n: s for n, s in signing.items() if s != report}
    if differing:
        return _result(rid, title, "REVIEW", "LOW",
                       "The directors' DINs differ: Directors' Report " + ", ".join(sorted(report)) + "; "
                       + "; ".join(f"{n} {', '.join(sorted(s))}" for n, s in differing.items())
                       + ". Confirm who signed each document.", evidence, 0.75)
    return _result(rid, title, "PASS", "LOW",
                   f"The same {len(report)} directors (by DIN) sign the Directors' Report and the statements.",
                   evidence, 0.85)


def xdoc_auditor_term(pkg: Package) -> ComplianceFinding | None:
    rid, title = "XDOC-010", "Auditor's term agrees between the Directors' Report and the notice"
    dr, notice = pkg.one("directors_report"), pkg.one("agm_notice")
    if not dr or not notice:
        return None
    appointed = dr.evidence(r"appointedasstatutoryauditors.{0,200}", "Auditor appointment", 240)
    if not appointed:
        return None
    in_notice = notice.evidence(r"toappoint.{0,260}", "Auditor appointment", 260)
    meeting = _meeting_datetime(notice.index)
    until = notice.index.search(r"heldin(20\d{2})")
    if not in_notice or not meeting or not until:
        return None
    notice_years = int(until.group(1)) - meeting[0].year
    if dr.index.has(r"ensuingannualgen\w{0,3}ralmeeting"):
        report_years = 1
    elif dr.index.has(r"(fiveconsecutive|fiveyears|sixthannualgen)"):
        report_years = 5
    else:
        return None
    evidence = [appointed, in_notice]
    if report_years != notice_years:
        return _result(rid, title, "REVIEW", "MEDIUM",
                       f"The Directors' Report appoints the auditor for {report_years} year(s) (until the "
                       f"{'ensuing' if report_years == 1 else 'fifth'} AGM) but the notice proposes a term of "
                       f"{notice_years} years (until the AGM in {until.group(1)}). Confirm which term the "
                       "Board and members are approving (s.139).", evidence, 0.8)
    return _result(rid, title, "PASS", "LOW",
                   f"Both documents describe a term of {notice_years} year(s).", evidence, 0.8)


def xdoc_statements_covered(pkg: Package) -> ComplianceFinding | None:
    rid, title = "XDOC-011", "Statements named in the audit opinion are in the package"
    ar = pkg.one("auditors_report")
    statements = pkg.statements()
    if not ar or not statements:
        return None
    claimed = ar.index.search(r"whichcomprise(.{0,220}?)(?:foryear|fortheyear|including)")
    if not claimed:
        return None
    text = claimed.group(1)
    have = {"cash flows": False, "changes in equity": False}
    for doc in statements:
        sq = doc.index.squashed
        have["cash flows"] |= bool(re.search(r"(cashflowstatement|statementofcashflows|cashflowsfromoperatingactivities)", sq))
        have["changes in equity"] |= bool(re.search(r"statementofchangesinequity", sq))
    named = {"cash flows": bool(re.search(r"(statementofcashflows|cashflowstatement)", text)),
             "changes in equity": bool(re.search(r"statementofchangesinequity", text))}
    missing = [f"a statement of {k}" for k in named if named[k] and not have[k]]
    evidence = [ar.evidence(r"whichcomprise.{0,220}", "What the audit covers", 260)]
    if missing:
        return _result(rid, title, "REVIEW", "MEDIUM",
                       "The Auditor's Report says the financial statements include " + " and ".join(missing)
                       + ", but none was found in the financial statements provided. Either the statement is "
                       "missing from the package, or the audit report wording needs correcting (a small company "
                       "or one person company is exempt from a cash flow statement).", evidence, 0.75)
    return _result(rid, title, "PASS", "LOW",
                   "Every statement named in the audit opinion is present in the financial statements.",
                   evidence, 0.75)


CROSS_RULES: list[tuple[str, str, Rule]] = [
    ("XDOC-001", "Company name and CIN agree across documents", xdoc_identity),
    ("XDOC-002", "Financial year-end agrees across documents", xdoc_period),
    ("XDOC-003", "Auditor named consistently across documents", xdoc_auditor),
    ("XDOC-004", "Documents are signed in a sensible order", xdoc_dates),
    ("XDOC-005", "Board's reply matches the auditor's opinion (s.134(3)(f))", xdoc_board_comments),
    ("XDOC-006", "Profit or loss is described consistently", xdoc_results_wording),
    ("XDOC-007", "Directors' Report financial summary agrees with the statements", xdoc_financial_summary),
    ("XDOC-008", "Share capital change matches the Directors' Report", xdoc_share_capital),
    ("XDOC-009", "Same directors sign the Directors' Report and the statements", xdoc_directors),
    ("XDOC-010", "Auditor's term agrees between the Directors' Report and the notice", xdoc_auditor_term),
    ("XDOC-011", "Statements named in the audit opinion are in the package", xdoc_statements_covered),
]


class CrossDocumentEngine:
    def evaluate(self, documents: list[dict[str, Any]]) -> list[ComplianceFinding]:
        docs = [Doc(d.get("document_type", "other"), d.get("document_name", ""), d.get("text", "") or "",
                    d.get("facts") or []) for d in documents]
        package = Package(docs)
        findings = []
        for _, _, rule in CROSS_RULES:
            finding = rule(package)
            if finding:
                findings.append(finding)
        return findings
