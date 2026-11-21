"""Deterministic compliance rules for narrative documents.

Covers the Board's (Directors') Report and the Independent Auditor's Report of an
Indian company. The rules check that statutory content is *present and
internally consistent*; they do not judge whether the content is adequate or
true. Every finding cites the text it relied on.

Matching runs on a "squashed" copy of the text (letters and digits only,
lower-case) so it survives line breaks, punctuation and the stray spaces some
PDF fonts put inside words ("Au dit of t he"). Evidence excerpts are cut from
the original text.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date
from typing import Any, Callable

from app.rules_engine import (
    ComplianceFinding,
    ComplianceRule,
    RegulationEvidence,
    RuleContext,
    _reg_evidence,
)

_MONTHS = {
    m: i for i, m in enumerate(
        ["january", "february", "march", "april", "may", "june", "july",
         "august", "september", "october", "november", "december"], start=1)
}
_MONTH_RE = "|".join(_MONTHS)


class TextIndex:
    """Squashed view of a document that can map matches back to the source text."""

    def __init__(self, text: str):
        self.text = text
        chars: list[str] = []
        self._origin: list[int] = []
        for i, ch in enumerate(text):
            for c in ch.lower():
                if c.isascii() and c.isalnum():
                    chars.append(c)
                    self._origin.append(i)
        self.squashed = "".join(chars)
        self.has_pages = "\f" in text

    def search(self, pattern: str) -> re.Match | None:
        return re.search(pattern, self.squashed)

    def has(self, pattern: str) -> bool:
        return self.search(pattern) is not None

    def page_of(self, source_index: int) -> int | None:
        return self.text.count("\f", 0, source_index) + 1 if self.has_pages else None

    def evidence(self, pattern: str, label: str, width: int = 240) -> dict[str, Any] | None:
        match = self.search(pattern)
        if not match or match.end() <= match.start():
            return None
        start = self._origin[match.start()]
        end = self._origin[match.end() - 1]
        excerpt = " ".join(self.text[start:max(end + 1, start + width)].replace("\f", " ").split())
        return {"label": label, "value": excerpt[:width], "source_page": self.page_of(start)}


def _finding(
    rule_id: str, title: str, status: str, severity: str, message: str,
    evidence: list[dict[str, Any]], regulations: list[RegulationEvidence], confidence: float,
) -> ComplianceFinding:
    return ComplianceFinding(
        rule_id=rule_id, status=status, severity=severity, title=title, message=message,
        evidence=evidence, regulatory_evidence=_reg_evidence(regulations), confidence=confidence,
    )


def _no_text(rule_id: str, title: str, regs: list[RegulationEvidence]) -> ComplianceFinding:
    return _finding(rule_id, title, "REVIEW", "MEDIUM",
                    "The document text was not available, so this check could not be run.", [], regs, 0.5)


Evaluator = Callable[[RuleContext, list[RegulationEvidence]], ComplianceFinding | None]


def _checklist(
    rule_id: str, title: str, reference: str, items: list[tuple[str, str]],
    *, none_status: str = "FAIL", none_severity: str = "HIGH",
    partial_severity: str = "MEDIUM", confidence: float = 0.8,
) -> Evaluator:
    """All items present -> PASS; some -> REVIEW; none -> ``none_status``."""

    def evaluate(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
        if not ctx.text.strip():
            return _no_text(rule_id, title, regs)
        index = TextIndex(ctx.text)
        found = [(label, index.evidence(pattern, label)) for label, pattern in items]
        present = [ev for _, ev in found if ev]
        missing = [label for label, ev in found if not ev]
        if not missing:
            return _finding(rule_id, title, "PASS", "LOW",
                            f"All expected disclosures are present ({reference}).", present, regs, confidence)
        if not present:
            return _finding(rule_id, title, none_status, none_severity,
                            f"None of the expected disclosures were found ({reference}): "
                            + "; ".join(missing) + ".", [], regs, confidence)
        return _finding(rule_id, title, "REVIEW", partial_severity,
                        f"Missing or not recognised ({reference}): " + "; ".join(missing) + ".",
                        present, regs, confidence)

    return evaluate


# --------------------------------------------------------------------------- dates

def _long_dates(index: TextIndex) -> list[date]:
    out: list[date] = []
    patterns = (
        (rf"(\d{{1,2}})(?:st|nd|rd|th)?({_MONTH_RE})(\d{{4}})", ("d", "m", "y")),
        (rf"({_MONTH_RE})(\d{{1,2}})(?:st|nd|rd|th)?(\d{{4}})", ("m", "d", "y")),
    )
    for pattern, order in patterns:
        for match in re.finditer(pattern, index.squashed):
            parts = dict(zip(order, match.groups()))
            try:
                out.append(date(int(parts["y"]), _MONTHS[parts["m"]], int(parts["d"])))
            except ValueError:
                continue
    return out


def _signature_date(index: TextIndex) -> date | None:
    """The last 'Date: dd/mm/yyyy' in the document (signature block)."""
    matches = re.findall(r"dated?(\d{2})(\d{2})(\d{4})", index.squashed)
    for d, m, y in reversed(matches):
        try:
            return date(int(y), int(m), int(d))
        except ValueError:
            continue
    return None


def _period_end(index: TextIndex) -> date | None:
    """The balance-sheet date: the long-form date quoted most often (ties: the latest)."""
    dates = _long_dates(index)
    if not dates:
        return None
    counts = Counter(dates)
    top = max(counts.values())
    return max(d for d, c in counts.items() if c == top)


def _date_consistency(rule_id: str, title: str, doc_name: str) -> Evaluator:
    def evaluate(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
        if not ctx.text.strip():
            return _no_text(rule_id, title, regs)
        index = TextIndex(ctx.text)
        signed = _signature_date(index)
        period_end = _period_end(index)
        evidence = [e for e in (index.evidence(r"date\d{8}", "Signature date"),) if e]
        if signed is None or period_end is None:
            return _finding(rule_id, title, "REVIEW", "MEDIUM",
                            f"Could not read both the {doc_name} date and the financial year-end date.",
                            evidence, regs, 0.6)
        if signed < period_end:
            return _finding(rule_id, title, "FAIL", "HIGH",
                            f"The {doc_name} is dated {signed:%d %b %Y}, before the financial year-end "
                            f"({period_end:%d %b %Y}).", evidence, regs, 0.9)
        return _finding(rule_id, title, "PASS", "LOW",
                        f"The {doc_name} is dated {signed:%d %b %Y}, after the financial year-end "
                        f"({period_end:%d %b %Y}).", evidence, regs, 0.85)

    return evaluate


# ------------------------------------------------------------------- directors' report

def _board_meeting_dates(index: TextIndex) -> list[date]:
    section = re.search(
        r"dateofboardmeetings(?:held)?(?:duringtheyear)?(.*?)(?:numbers?anddateofcommittee|nocommittee|numberofcommittee)",
        index.squashed,
    )
    if not section:
        return []
    out: list[date] = []
    for run in re.findall(r"\d{8,}", section.group(1)):
        for i in range(0, len(run) - len(run) % 8, 8):
            chunk = run[i:i + 8]
            try:
                out.append(date(int(chunk[4:]), int(chunk[2:4]), int(chunk[:2])))
            except ValueError:
                return []
    return out


def _board_meeting_count(index: TextIndex) -> int | None:
    match = (index.search(r"numberofboardmeetings?.{0,60}?convened(\d{1,2})boardmeeting")
             or index.search(r"convened(\d{1,2})boardmeeting")
             or index.search(r"numberofboardmeetings?heldduringtheyear.{0,40}?(\d{1,2})"))
    return int(match.group(1)) if match else None


def rule_board_meetings_disclosed(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "DIRREP-002", "Board meetings disclosed (s.134(3)(b))"
    if not ctx.text.strip():
        return _no_text(rid, title, regs)
    index = TextIndex(ctx.text)
    evidence = [e for e in (index.evidence(r"numberofboardmeeting", "Number of board meetings"),
                            index.evidence(r"dateofboardmeeting", "Dates of board meetings")) if e]
    count, dates = _board_meeting_count(index), _board_meeting_dates(index)
    if not index.has(r"boardmeeting"):
        return _finding(rid, title, "FAIL", "HIGH",
                        "The report does not state the number of Board meetings held during the year.",
                        [], regs, 0.85)
    if count is None:
        return _finding(rid, title, "REVIEW", "MEDIUM",
                        "Board meetings are mentioned but the number held could not be read.", evidence, regs, 0.65)
    if not dates:
        return _finding(rid, title, "REVIEW", "MEDIUM",
                        f"The report states {count} Board meetings but the dates could not be read.",
                        evidence, regs, 0.65)
    if len(dates) != count:
        return _finding(rid, title, "FAIL", "MEDIUM",
                        f"The report states {count} Board meetings but lists {len(dates)} dates.",
                        evidence, regs, 0.85)
    return _finding(rid, title, "PASS", "LOW",
                    f"The report states {count} Board meetings and lists {len(dates)} matching dates.",
                    evidence, regs, 0.85)


def rule_board_meeting_frequency(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "DIRREP-003", "Board meeting frequency (s.173)"
    if not ctx.text.strip():
        return _no_text(rid, title, regs)
    index = TextIndex(ctx.text)
    evidence = [e for e in (index.evidence(r"dateofboardmeeting", "Dates of board meetings"),) if e]
    dates = sorted(_board_meeting_dates(index))
    if not dates:
        return _finding(rid, title, "REVIEW", "MEDIUM",
                        "Board meeting dates could not be read, so frequency could not be checked.",
                        evidence, regs, 0.6)
    gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
    problems = []
    if len(dates) < 4:
        problems.append(f"only {len(dates)} meetings (at least 4 are required in a year)")
    if gaps and max(gaps) > 120:
        problems.append(f"a gap of {max(gaps)} days between meetings (maximum 120)")
    if problems:
        return _finding(rid, title, "FAIL", "HIGH", "Section 173 is not met: " + "; ".join(problems) + ".",
                        evidence, regs, 0.85)
    return _finding(rid, title, "PASS", "LOW",
                    f"{len(dates)} meetings with a largest gap of {max(gaps) if gaps else 0} days "
                    "(at least 4 meetings and gaps of at most 120 days).", evidence, regs, 0.85)


def rule_annual_return(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "DIRREP-009", "Annual return disclosure (s.92(3) / s.134(3)(a))"
    if not ctx.text.strip():
        return _no_text(rid, title, regs)
    index = TextIndex(ctx.text)
    mention = index.evidence(r"annualreturn", "Annual return reference")
    evidence = [mention] if mention else []
    if not mention:
        return _finding(rid, title, "REVIEW", "MEDIUM",
                        "The report does not mention the annual return.", [], regs, 0.8)
    if index.has(r"mgt9"):
        return _finding(rid, title, "REVIEW", "MEDIUM",
                        "The report refers to an MGT-9 extract of the annual return. MGT-9 was discontinued "
                        "in 2020; the Board's report now needs to give the web address where the annual "
                        "return is placed. Confirm the current requirement is met.", evidence, regs, 0.8)
    if index.has(r"(www|http|webaddress|website)"):
        return _finding(rid, title, "PASS", "LOW",
                        "The report refers to a web address for the annual return.", evidence, regs, 0.75)
    return _finding(rid, title, "REVIEW", "LOW",
                    "The annual return is mentioned but no web address was found.", evidence, regs, 0.7)


def rule_directors_signature(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "DIRREP-010", "Report signed by directors (s.134(6))"
    if not ctx.text.strip():
        return _no_text(rid, title, regs)
    index = TextIndex(ctx.text)
    dins = set(re.findall(r"(?<!u)din(?:no)?(\d{8})", index.squashed))
    evidence = [e for e in (index.evidence(r"forbehalfofboard|foronbehalfofboard", "Signature block"),
                            index.evidence(r"date\d{8}", "Date")) if e]
    has_place = index.has(r"place[a-z]{3,}")
    signed = _signature_date(index)
    problems = []
    if not dins:
        problems.append("no director names with DIN were found")
    elif len(dins) < 2:
        problems.append("only one signatory with a DIN was found (two directors are needed unless the "
                        "company is a one-person company)")
    if signed is None:
        problems.append("no date")
    if not has_place:
        problems.append("no place")
    if not problems:
        return _finding(rid, title, "PASS", "LOW",
                        f"Signed by {len(dins)} directors (DINs found), with date and place.", evidence, regs, 0.85)
    return _finding(rid, title, "FAIL" if not dins else "REVIEW", "HIGH" if not dins else "MEDIUM",
                    "Signature block issues: " + "; ".join(problems) + ".", evidence, regs, 0.8)


DIRECTORS_REPORT_RULES: list[tuple[str, str, Evaluator]] = [
    ("DIRREP-001", "Directors' Responsibility Statement (s.134(5))", _checklist(
        "DIRREP-001", "Directors' Responsibility Statement (s.134(5))", "s.134(3)(c), s.134(5)", [
            ("statement heading", r"directorsresponsibilitystatement"),
            ("applicable accounting standards followed", r"accountingstandards.{0,200}followed"),
            ("accounting policies applied consistently / true and fair view",
             r"(accountingpoliciesandappliedthemconsistently|trueandfairview)"),
            ("proper accounting records and fraud prevention", r"maintenanceofadequateaccountingrecords"),
            ("annual accounts on a going concern basis", r"goingconcernbasis"),
        ])),
    ("DIRREP-002", "Board meetings disclosed (s.134(3)(b))", rule_board_meetings_disclosed),
    ("DIRREP-003", "Board meeting frequency (s.173)", rule_board_meeting_frequency),
    ("DIRREP-004", "Auditor disclosures (s.134(3)(f), s.139, s.141)", _checklist(
        "DIRREP-004", "Auditor disclosures (s.134(3)(f), s.139, s.141)", "s.134(3)(f), s.139, s.141", [
            ("statutory auditors named / appointed", r"statutoryauditors"),
            ("eligibility certificate (s.141)", r"section141"),
            ("Board's comments on the auditor's report", r"commentsbyboard.{0,40}auditorsreport"),
        ], none_status="FAIL", none_severity="MEDIUM")),
    ("DIRREP-005", "State of affairs, reserves, dividend, material changes (s.134(3)(i)-(l))", _checklist(
        "DIRREP-005", "State of affairs, reserves, dividend, material changes (s.134(3)(i)-(l))",
        "s.134(3)(i), (j), (k), (l)", [
            ("state of the company's affairs", r"(stateofcompan(y|ys)affair|operationinbusinessperformance)"),
            ("amounts to be carried to reserves", r"reserves"),
            ("dividend", r"dividend"),
            ("material changes and commitments after year-end", r"materialchangesandcommitments"),
        ], none_status="FAIL", none_severity="HIGH")),
    ("DIRREP-006", "Loans, guarantees and investments (s.186, s.134(3)(g))", _checklist(
        "DIRREP-006", "Loans, guarantees and investments (s.186, s.134(3)(g))", "s.134(3)(g), s.186",
        [("section 186 particulars", r"section186")], none_status="REVIEW", none_severity="MEDIUM")),
    ("DIRREP-007", "Related party transactions (s.188, s.134(3)(h))", _checklist(
        "DIRREP-007", "Related party transactions (s.188, s.134(3)(h))", "s.134(3)(h), s.188",
        [("related party contracts or arrangements", r"relatedpart(y|ies)")],
        none_status="REVIEW", none_severity="MEDIUM")),
    ("DIRREP-008", "Other statutory disclosures (s.134(3)(m)-(o))", _checklist(
        "DIRREP-008", "Other statutory disclosures (s.134(3)(m)-(o))", "s.134(3)(m), (n), (o)", [
            ("conservation of energy, technology absorption, foreign exchange", r"conservationofenergy|energyconservation"),
            ("risk management", r"riskmanagement"),
            ("corporate social responsibility", r"corporatesocialresponsibility"),
        ], none_status="REVIEW", none_severity="MEDIUM")),
    ("DIRREP-009", "Annual return disclosure (s.92(3) / s.134(3)(a))", rule_annual_return),
    ("DIRREP-010", "Report signed by directors (s.134(6))", rule_directors_signature),
    ("DIRREP-011", "Report dated after the financial year-end",
     _date_consistency("DIRREP-011", "Report dated after the financial year-end", "Directors' Report")),
]


# ------------------------------------------------------------------- auditor's report

_MODIFIED_OPINION = re.compile(
    r"(basisforqualifiedopinion|qualifiedopinion|basisforadverseopinion|adverseopinion"
    r"|basisfordisclaimerofopinion|disclaimerofopinion|exceptfortheeffectsofthematter|exceptforthematterdescribed)"
)


def rule_opinion(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "AUDREP-002", "Audit opinion present and type (SA 700 / SA 705)"
    if not ctx.text.strip():
        return _no_text(rid, title, regs)
    index = TextIndex(ctx.text)
    opinion = index.evidence(r"inouropinion", "Opinion")
    evidence = [opinion] if opinion else []
    if not index.has(r"opinion") or not opinion:
        return _finding(rid, title, "FAIL", "HIGH",
                        "No opinion paragraph ('In our opinion ...') was found.", [], regs, 0.85)
    modified = _MODIFIED_OPINION.search(index.squashed)
    if modified:
        extra = index.evidence(_MODIFIED_OPINION.pattern, "Modification wording")
        return _finding(rid, title, "REVIEW", "HIGH",
                        "The report appears to contain a modified opinion (qualified, adverse or disclaimer). "
                        "Review the basis for the modification.",
                        evidence + ([extra] if extra else []), regs, 0.8)
    true_fair = index.has(r"trueandfair")
    return _finding(rid, title, "PASS" if true_fair else "REVIEW", "LOW" if true_fair else "MEDIUM",
                    "The report contains an unmodified opinion giving a true and fair view."
                    if true_fair else
                    "An opinion paragraph is present but it does not state a 'true and fair view'.",
                    evidence, regs, 0.8)


def rule_auditor_signature(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "AUDREP-008", "Auditor's signature block and UDIN (SA 700, ICAI)"
    if not ctx.text.strip():
        return _no_text(rid, title, regs)
    index = TextIndex(ctx.text)
    checks = [
        ("firm registration number (FRN)", r"frn\d{5,6}[a-z]?"),
        ("membership number", r"membership(no)?\d{6}"),
        ("UDIN", r"udin(no)?\d{8}[a-z0-9]{10}"),
        ("place", r"place[a-z]{3,}"),
        ("date", r"date\d{8}"),
    ]
    missing = [label for label, pattern in checks if not index.has(pattern)]
    evidence = [e for e in (index.evidence(r"frn\d{5,6}", "Auditor details", 200),
                            index.evidence(r"udinno", "UDIN line", 80)) if e]
    if not missing:
        return _finding(rid, title, "PASS", "LOW",
                        "Firm registration number, membership number, UDIN, place and date are all present.",
                        evidence, regs, 0.85)
    udin_only = missing == ["UDIN"]
    return _finding(rid, title, "FAIL", "MEDIUM" if udin_only else "HIGH",
                    "The signature block is incomplete. Missing: " + ", ".join(missing) + "."
                    + (" A UDIN is mandatory on audit reports under ICAI rules." if "UDIN" in missing else ""),
                    evidence, regs, 0.85)


def rule_caro(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "AUDREP-006", "CARO reference and version"
    if not ctx.text.strip():
        return _no_text(rid, title, regs)
    index = TextIndex(ctx.text)
    cited = index.evidence(r"(companiesauditorsreportorder|caro)(20\d{2})?", "CARO reference")
    evidence = [cited] if cited else []
    if index.has(r"(companiesauditorsreportorder|caro)2020"):
        return _finding(rid, title, "PASS", "LOW",
                        "The report refers to the Companies (Auditor's Report) Order, 2020.", evidence, regs, 0.85)
    if index.has(r"(companiesauditorsreportorder|caro)2016"):
        return _finding(rid, title, "REVIEW", "MEDIUM",
                        "The report refers to the Companies (Auditor's Report) Order, 2016. That Order was "
                        "replaced by CARO 2020 for financial years beginning on or after 1 April 2019. "
                        "Confirm which Order applies.", evidence, regs, 0.85)
    return _finding(rid, title, "REVIEW", "LOW",
                    "No reference to the Companies (Auditor's Report) Order was found. Confirm whether CARO 2020 "
                    "applies or the company is exempt (for example, a small private company).",
                    evidence, regs, 0.7)


AUDITORS_REPORT_RULES: list[tuple[str, str, Evaluator]] = [
    ("AUDREP-001", "Addressee and title (SA 700)", _checklist(
        "AUDREP-001", "Addressee and title (SA 700)", "SA 700", [
            ("addressed to the members of the company", r"tothemembersof"),
            ("report title / audit of the financial statements",
             r"(independentauditorsreport|reportontheauditofthefinancialstatements)"),
        ], none_status="FAIL", none_severity="MEDIUM")),
    ("AUDREP-002", "Audit opinion present and type (SA 700 / SA 705)", rule_opinion),
    ("AUDREP-003", "Basis for Opinion (SA 700)", _checklist(
        "AUDREP-003", "Basis for Opinion (SA 700)", "SA 700", [
            ("'Basis for Opinion' section", r"basisforopinion"),
            ("audit conducted under Standards on Auditing, s.143(10)", r"standardsonauditing"),
            ("independence and Code of Ethics", r"codeofethics"),
            ("sufficient and appropriate audit evidence", r"sufficientandappropriate"),
        ], none_status="FAIL", none_severity="HIGH")),
    ("AUDREP-004", "Responsibilities of management and auditor (SA 700)", _checklist(
        "AUDREP-004", "Responsibilities of management and auditor (SA 700)", "SA 700", [
            ("management / Board responsibility for the financial statements", r"management(s)?responsibilit"),
            ("auditor's responsibility for the audit", r"auditors?responsibilit"),
            ("going concern assessment", r"goingconcern"),
        ], none_status="FAIL", none_severity="MEDIUM")),
    ("AUDREP-005", "Report on other legal and regulatory requirements (s.143(3))", _checklist(
        "AUDREP-005", "Report on other legal and regulatory requirements (s.143(3))", "s.143(3), Rule 11", [
            ("'Other legal and regulatory requirements' section", r"otherlegalandregulatoryrequirements"),
            ("matters required by s.143(3)", r"section1433"),
            ("directors' disqualification, s.164(2)", r"section1642"),
            ("Companies (Audit and Auditors) Rules, 2014, Rule 11", r"rule11"),
        ], none_status="FAIL", none_severity="HIGH")),
    ("AUDREP-006", "CARO reference and version", rule_caro),
    ("AUDREP-007", "Internal financial controls report (s.143(3)(i))", _checklist(
        "AUDREP-007", "Internal financial controls report (s.143(3)(i))", "s.143(3)(i)", [
            ("report on internal financial controls over financial reporting",
             r"internalfinancialcontrolsoverfinancialreporting"),
            ("opinion on the adequacy and operating effectiveness of controls",
             r"adequateinternalfinancialcontrolssystem"),
        ], none_status="REVIEW", none_severity="MEDIUM")),
    ("AUDREP-008", "Auditor's signature block and UDIN (SA 700, ICAI)", rule_auditor_signature),
    ("AUDREP-009", "Report dated after the financial year-end",
     _date_consistency("AUDREP-009", "Report dated after the financial year-end", "audit report")),
]


def _build_rules() -> list[ComplianceRule]:
    rules = []
    for doc_type, group in (("directors_report", DIRECTORS_REPORT_RULES),
                            ("auditors_report", AUDITORS_REPORT_RULES)):
        for rule_id, title, evaluator in group:
            rules.append(ComplianceRule(rule_id=rule_id, title=title,
                                        statement_types={doc_type}, evaluator=evaluator))
    return rules


TEXT_RULES: list[ComplianceRule] = _build_rules()
