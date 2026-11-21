"""Deterministic rules for AGM notices and invoices.

AGM notice: Companies Act, 2013 (ss.96, 101, 102, 105, 139) and Secretarial
Standard SS-2. Invoice: Rule 46 of the CGST Rules, 2017, plus arithmetic and
identifier checks (GSTIN check digit, PAN format, amount in words).

As with the other narrative rules, these confirm that required content is
present and consistent. They do not judge whether the notice was validly
convened or whether the invoice is correct for tax purposes.
"""
from __future__ import annotations

import calendar
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from app.rules_engine import ComplianceFinding, ComplianceRule, RegulationEvidence, RuleContext
from app.text_rules import (
    Evaluator,
    TextIndex,
    _finding,
    _long_dates,
    _MONTH_RE,
    _MONTHS,
    _no_text,
    _period_end,
    _signature_date,
)

# ---------------------------------------------------------------------------- notice


def _add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year, month = d.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def _meeting_datetime(index: TextIndex) -> tuple[date, tuple[int, int] | None] | None:
    """Date (and time, if given) of the meeting: '30.09.2024 at 4.30 p.m.'."""
    candidates = []
    for match in re.finditer(rf"(\d{{2}})(\d{{2}})(20\d{{2}})at(\d{{1,2}})(\d{{2}})?(am|pm)", index.squashed):
        candidates.append((match, "numeric"))
    for match in re.finditer(
        rf"on(\d{{1,2}})(?:st|nd|rd|th)?({_MONTH_RE})(20\d{{2}})at(\d{{1,2}})(\d{{2}})?(am|pm)", index.squashed
    ):
        candidates.append((match, "long"))
    for match, kind in candidates:
        try:
            if kind == "numeric":
                day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
            else:
                day, month, year = int(match.group(1)), _MONTHS[match.group(2)], int(match.group(3))
            when = date(year, month, day)
        except ValueError:
            continue
        hour, minute, meridiem = int(match.group(4)), int(match.group(5) or 0), match.group(6)
        if not 1 <= hour <= 12 or minute > 59:
            return when, None
        hour = hour % 12 + (12 if meridiem == "pm" else 0)
        return when, (hour, minute)
    return None


def _notice_date(index: TextIndex) -> date | None:
    return _signature_date(index)


def rule_notice_meeting_details(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "NOTICE-001", "Meeting date, time and venue stated (s.101, SS-2)"
    if not ctx.text.strip():
        return _no_text(rid, title, regs)
    index = TextIndex(ctx.text)
    meeting = _meeting_datetime(index)
    evidence = [e for e in (index.evidence(r"annualgeneralmeeting", "Meeting notice"),) if e]
    missing = []
    if not meeting:
        missing.append("date and time")
    elif meeting[1] is None:
        missing.append("time")
    if not index.has(r"(registeredoffice|heldat|venue)"):
        missing.append("venue")
    if not index.has(r"annualgeneralmeeting|extraordinarygeneralmeeting"):
        missing.append("type of meeting")
    if missing:
        return _finding(rid, title, "FAIL", "HIGH", "The notice does not clearly state: " + ", ".join(missing) + ".",
                        evidence, regs, 0.8)
    day = meeting[0]
    return _finding(rid, title, "PASS", "LOW",
                    f"Meeting on {day:%A, %d %b %Y} at {meeting[1][0]:02d}:{meeting[1][1]:02d}, with a venue stated.",
                    evidence, regs, 0.85)


def rule_notice_hours(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "NOTICE-002", "AGM day and hours (s.96(2))"
    if not ctx.text.strip():
        return _no_text(rid, title, regs)
    index = TextIndex(ctx.text)
    meeting = _meeting_datetime(index)
    evidence = [e for e in (index.evidence(r"\d{8}at\d{1,4}(am|pm)", "Meeting date and time"),) if e]
    if not meeting or meeting[1] is None:
        return _finding(rid, title, "REVIEW", "MEDIUM",
                        "The meeting date or time could not be read, so the day and hours could not be checked.",
                        evidence, regs, 0.6)
    when, (hour, minute) = meeting
    problems = []
    if when.weekday() == 6:
        problems.append("the meeting falls on a Sunday")
    if not (9 <= hour < 18 or (hour == 18 and minute == 0)):
        problems.append(f"the time {hour:02d}:{minute:02d} is outside 9:00 to 18:00")
    at_office = index.has(r"registeredoffice")
    if problems:
        return _finding(rid, title, "FAIL", "HIGH", "Section 96(2) is not met: " + "; ".join(problems) + ".",
                        evidence, regs, 0.85)
    return _finding(rid, title, "PASS", "LOW",
                    f"Held on a {when:%A}, between 9:00 and 18:00"
                    + (", at the registered office" if at_office else "")
                    + ". Whether the date is a national holiday is not checked.", evidence, regs, 0.8)


def rule_notice_within_six_months(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "NOTICE-003", "AGM within six months of year-end (s.96(1))"
    if not ctx.text.strip():
        return _no_text(rid, title, regs)
    index = TextIndex(ctx.text)
    meeting, period_end = _meeting_datetime(index), _period_end(index)
    evidence = [e for e in (index.evidence(r"\d{8}at\d{1,4}(am|pm)", "Meeting date and time"),
                            index.evidence(r"(balancesheetasat|financialyear|yearended)", "Financial year reference")) if e]
    if not meeting or not period_end:
        return _finding(rid, title, "REVIEW", "MEDIUM",
                        "Could not read both the meeting date and the financial year-end date.", evidence, regs, 0.6)
    deadline = _add_months(period_end, 6)
    if meeting[0] > deadline:
        return _finding(rid, title, "FAIL", "HIGH",
                        f"The AGM on {meeting[0]:%d %b %Y} is after {deadline:%d %b %Y}, six months from the "
                        f"year-end ({period_end:%d %b %Y}). Check whether an extension was obtained.",
                        evidence, regs, 0.85)
    if meeting[0] < period_end:
        return _finding(rid, title, "FAIL", "HIGH",
                        f"The AGM on {meeting[0]:%d %b %Y} is before the financial year-end ({period_end:%d %b %Y}).",
                        evidence, regs, 0.85)
    return _finding(rid, title, "PASS", "LOW",
                    f"The AGM on {meeting[0]:%d %b %Y} is within six months of the year-end "
                    f"({period_end:%d %b %Y}; deadline {deadline:%d %b %Y}).", evidence, regs, 0.85)


def rule_notice_period(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "NOTICE-004", "Notice period of at least 21 clear days (s.101(1))"
    if not ctx.text.strip():
        return _no_text(rid, title, regs)
    index = TextIndex(ctx.text)
    meeting, issued = _meeting_datetime(index), _notice_date(index)
    evidence = [e for e in (index.evidence(r"dated?\d{8}", "Notice date"),) if e]
    if not meeting or not issued:
        return _finding(rid, title, "REVIEW", "MEDIUM",
                        "Could not read both the notice date and the meeting date.", evidence, regs, 0.6)
    clear_days = (meeting[0] - issued).days - 1
    shorter_notice = index.has(r"shorternotice|lessthan21|consent.{0,40}(95|ninetyfive)")
    if clear_days >= 21:
        return _finding(rid, title, "PASS", "LOW",
                        f"{clear_days} clear days between the notice ({issued:%d %b %Y}) and the meeting "
                        f"({meeting[0]:%d %b %Y}), assuming it was sent on the date shown.", evidence, regs, 0.8)
    if shorter_notice:
        return _finding(rid, title, "REVIEW", "MEDIUM",
                        f"Only {clear_days} clear days, but the notice mentions shorter notice. Confirm consent "
                        "was given by at least 95% of members.", evidence, regs, 0.75)
    return _finding(rid, title, "FAIL", "HIGH",
                    f"Only {clear_days} clear days between the notice ({issued:%d %b %Y}) and the meeting "
                    f"({meeting[0]:%d %b %Y}); at least 21 are required.", evidence, regs, 0.85)


def rule_notice_business(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "NOTICE-005", "Business at the AGM (s.102(2), s.139, SS-2)"
    if not ctx.text.strip():
        return _no_text(rid, title, regs)
    index = TextIndex(ctx.text)
    evidence = [e for e in (index.evidence(r"(adoptthe|considerandadopt).{0,40}(financialstatements|balancesheet)",
                                           "Financial statements item"),) if e]
    issues = []
    if not evidence:
        issues.append("no item to consider and adopt the financial statements")
    elif not index.has(r"report.{0,20}(auditors|directors|board)"):
        issues.append("the financial statements item does not mention the reports of the Board and auditors")
    other = index.evidence(r"anyotherbusiness|anyotherterms?|anyothermatters?", "Open-ended item")
    if other:
        evidence.append(other)
        issues.append("an open-ended item ('any other business') is listed; business not specified in the "
                      "notice cannot be taken up at the meeting")
    if not issues:
        return _finding(rid, title, "PASS", "LOW",
                        "The notice lists the financial statements for adoption with the Board and auditors' reports.",
                        evidence, regs, 0.8)
    return _finding(rid, title, "REVIEW", "MEDIUM", "Review: " + "; ".join(issues) + ".", evidence, regs, 0.8)


def rule_notice_auditor_appointment(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "NOTICE-006", "Auditor appointment terms (s.139, s.142)"
    if not ctx.text.strip():
        return _no_text(rid, title, regs)
    index = TextIndex(ctx.text)
    appointment = index.evidence(r"toappoint.{0,80}(charteredaccountants|auditors?)", "Auditor appointment")
    if not appointment:
        return None  # an AGM does not appoint auditors every year
    evidence = [appointment]
    issues = []
    if index.has(r"subjecttoratification|ratificationateve"):
        ratification = index.evidence(r"subjecttoratification|ratificationateve", "Ratification wording")
        if ratification:
            evidence.append(ratification)
        issues.append("the appointment is described as subject to ratification at every AGM; the ratification "
                      "requirement was removed from s.139(1) with effect from 7 May 2018")
    if not index.has(r"remuneration"):
        issues.append("no mention of how the auditors' remuneration is fixed (s.142)")
    if not index.has(r"conclusionof.{0,60}(annualgeneralmeeting|agm)"):
        issues.append("the term of the appointment is not stated")
    if not issues:
        return _finding(rid, title, "PASS", "LOW",
                        "The appointment states the auditors, their term and how remuneration is fixed.",
                        evidence, regs, 0.8)
    return _finding(rid, title, "REVIEW", "MEDIUM", "Review: " + "; ".join(issues) + ".", evidence, regs, 0.8)


def rule_notice_proxy(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "NOTICE-007", "Proxy statement (s.105)"
    if not ctx.text.strip():
        return _no_text(rid, title, regs)
    index = TextIndex(ctx.text)
    items = [
        ("member may appoint a proxy", r"entitledtoappointaproxy"),
        ("proxy need not be a member", r"neednot(to)?beamember"),
        ("proxy form to be deposited at least 48 hours before the meeting", r"(48|fortyeight)hours"),
        ("proxy form (MGT-11) attached", r"(mgt11|formofproxy|proxyform)"),
    ]
    found = [(label, index.evidence(pattern, label)) for label, pattern in items]
    missing = [label for label, ev in found if not ev]
    evidence = [ev for _, ev in found if ev]
    if not missing:
        return _finding(rid, title, "PASS", "LOW", "The proxy statement is complete.", evidence, regs, 0.8)
    if not evidence:
        return _finding(rid, title, "FAIL", "HIGH", "The notice does not contain the statement on proxies.",
                        [], regs, 0.8)
    return _finding(rid, title, "REVIEW", "MEDIUM", "Not found in the notice: " + "; ".join(missing) + ".",
                    evidence, regs, 0.8)


def rule_notice_signature(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "NOTICE-008", "Issued by order of the Board, with place and date"
    if not ctx.text.strip():
        return _no_text(rid, title, regs)
    index = TextIndex(ctx.text)
    evidence = [e for e in (index.evidence(r"byorderoftheboard", "By order of the Board"),
                            index.evidence(r"place", "Place"), index.evidence(r"dated?\d{8}", "Date")) if e]
    missing = []
    if not index.has(r"byorderoftheboard"):
        missing.append("'By order of the Board'")
    if not index.has(r"place[a-z]{3,}"):
        missing.append("place")
    if _notice_date(index) is None:
        missing.append("date")
    if not index.has(r"(director|companysecretary|authori[sz]edsignatory)"):
        missing.append("the designation of the person issuing the notice")
    if missing:
        return _finding(rid, title, "FAIL" if len(missing) > 2 else "REVIEW", "MEDIUM",
                        "Not found: " + ", ".join(missing) + ".", evidence, regs, 0.8)
    return _finding(rid, title, "PASS", "LOW",
                    "Issued by order of the Board with place, date and a director or officer named.",
                    evidence, regs, 0.8)


def rule_notice_addressees(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "NOTICE-009", "Addressed to members, directors and auditors (s.101(1))"
    if not ctx.text.strip():
        return _no_text(rid, title, regs)
    index = TextIndex(ctx.text)
    found = {
        "members": index.has(r"to(the|all)?(the)?(members|shareholders)"),
        "directors": index.has(r"to(the)?directors|(members|shareholders),?(and)?(the)?directors"),
        "auditors": index.has(r"to(the)?auditors|(directors|members|shareholders),?(and)?(the)?auditors"),
    }
    missing = [name for name, ok in found.items() if not ok]
    if not missing:
        return _finding(rid, title, "PASS", "LOW", "The notice is addressed to members, directors and auditors.",
                        [], regs, 0.7)
    return _finding(rid, title, "REVIEW", "LOW",
                    "The notice does not state that it is sent to: " + ", ".join(missing)
                    + ". Section 101(1) requires notice to every member, director and the auditors.",
                    [], regs, 0.7)


def rule_notice_special_business(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "NOTICE-010", "Explanatory statement for special business (s.102(1))"
    if not ctx.text.strip():
        return _no_text(rid, title, regs)
    index = TextIndex(ctx.text)
    special = index.evidence(r"(specialbusiness|specialresolution)", "Special business")
    if not special:
        return None  # no special business, nothing to check
    if index.has(r"explanatorystatement"):
        return _finding(rid, title, "PASS", "LOW", "Special business is accompanied by an explanatory statement.",
                        [special], regs, 0.8)
    return _finding(rid, title, "FAIL", "HIGH",
                    "The notice contains special business but no explanatory statement under s.102(1).",
                    [special], regs, 0.85)


NOTICE_RULES: list[tuple[str, str, Evaluator]] = [
    ("NOTICE-001", "Meeting date, time and venue stated (s.101, SS-2)", rule_notice_meeting_details),
    ("NOTICE-002", "AGM day and hours (s.96(2))", rule_notice_hours),
    ("NOTICE-003", "AGM within six months of year-end (s.96(1))", rule_notice_within_six_months),
    ("NOTICE-004", "Notice period of at least 21 clear days (s.101(1))", rule_notice_period),
    ("NOTICE-005", "Business at the AGM (s.102(2), s.139, SS-2)", rule_notice_business),
    ("NOTICE-006", "Auditor appointment terms (s.139, s.142)", rule_notice_auditor_appointment),
    ("NOTICE-007", "Proxy statement (s.105)", rule_notice_proxy),
    ("NOTICE-008", "Issued by order of the Board, with place and date", rule_notice_signature),
    ("NOTICE-009", "Addressed to members, directors and auditors (s.101(1))", rule_notice_addressees),
    ("NOTICE-010", "Explanatory statement for special business (s.102(1))", rule_notice_special_business),
]


# --------------------------------------------------------------------------- invoice

_GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_GSTIN_RE = (r"(?:gstin|gstuin|gstno|gstregistrationno|gstidentificationnumber)(?:uin)?(?:no)?"
             r"(\d{2}[a-z]{5}\d{4}[a-z][1-9a-z]z[0-9a-z])")
_UNITS = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
          "sixteen seventeen eighteen nineteen").split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def gstin_is_valid(gstin: str) -> bool:
    """Format plus the mod-36 check digit used for GSTINs."""
    gstin = gstin.upper()
    if not re.fullmatch(r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]", gstin):
        return False
    if not 1 <= int(gstin[:2]) <= 99:
        return False
    total = 0
    for position, char in enumerate(gstin[:14]):
        product = _GSTIN_CHARS.index(char) * (1 if position % 2 == 0 else 2)
        total += product // 36 + product % 36
    return gstin[14] == _GSTIN_CHARS[(36 - total % 36) % 36]


def _two_digit_words(n: int) -> str:
    if n < 20:
        return _UNITS[n]
    return _TENS[n // 10] + (_UNITS[n % 10] if n % 10 else "")


def indian_words(n: int) -> str:
    """Number in words, Indian grouping, without spaces: 7250 -> 'seventhousandtwohundredfifty'."""
    if n == 0:
        return "zero"
    parts = []
    for size, name in ((10**7, "crore"), (10**5, "lakh"), (1000, "thousand")):
        chunk, n = divmod(n, size)
        if chunk:
            parts.append(_two_digit_words(chunk) + name)
    hundreds, rest = divmod(n, 100)
    if hundreds:
        parts.append(_UNITS[hundreds] + "hundred")
    if rest:
        parts.append(_two_digit_words(rest))
    return "".join(parts)


def _decimal(value: object) -> Decimal | None:
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def _invoice_total(ctx: RuleContext) -> tuple[int, Decimal] | None:
    """(index in facts, amount) of the invoice total row."""
    for i, fact in enumerate(ctx.facts):
        label = re.sub(r"[^a-z]", "", str(fact.get("label", "")).lower())
        if "total" in label:
            amount = _decimal(fact.get("value"))
            if amount is not None:
                return i, amount
    return None


def _gstins(index: TextIndex) -> list[str]:
    return [m.upper() for m in re.findall(_GSTIN_RE, index.squashed)]


def _has_hsn_code(text: str) -> bool:
    """An HSN/SAC column header followed somewhere by a 4 to 8 digit code."""
    header = re.search(r"hsn|sac", text, re.I)
    if not header:
        return False
    return re.search(r"(?<![\d,.\-])\d{4,8}(?![\d,.])", text[header.end():]) is not None


def rule_invoice_identity(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "INV-001", "Invoice number and date (CGST Rule 46(b), (c))"
    if not ctx.text.strip():
        return _no_text(rid, title, regs)
    index = TextIndex(ctx.text)
    number = re.search(r"invoice\s*(?:no|number|#)\.?\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9/\-]*)", ctx.text, re.I)
    head = ctx.text[:800]
    parsed = None
    for match in re.finditer(r"\b(\d{1,2})[-/. ]([A-Za-z]{3,9})[-/. ,]+(\d{2,4})\b", head):
        month = _MONTHS.get(next((m for m in _MONTHS if m.startswith(match.group(2).lower()[:3])), ""), None)
        if month:
            year = int(match.group(3)) + (2000 if len(match.group(3)) == 2 else 0)
            try:
                parsed = date(year, month, int(match.group(1)))
                break
            except ValueError:
                continue
    if parsed is None:
        for match in re.finditer(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})\b", head):
            try:
                parsed = date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
                break
            except ValueError:
                continue
    evidence = [e for e in (index.evidence(r"invoice(no|number)", "Invoice number and date", 120),) if e]
    problems = []
    if not number:
        problems.append("no invoice number")
    else:
        value = number.group(1)
        if len(value) > 16:
            problems.append(f"the invoice number '{value}' is longer than 16 characters")
    if parsed is None:
        problems.append("no readable invoice date")
    if problems:
        return _finding(rid, title, "FAIL" if not number else "REVIEW", "MEDIUM",
                        "Issues: " + "; ".join(problems) + ".", evidence, regs, 0.8)
    return _finding(rid, title, "PASS", "LOW",
                    f"Invoice number {number.group(1)} dated {parsed:%d %b %Y}.", evidence, regs, 0.85)


def rule_invoice_parties(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "INV-002", "Recipient name and address (CGST Rule 46(e))"
    if not ctx.text.strip():
        return _no_text(rid, title, regs)
    index = TextIndex(ctx.text)
    party = index.evidence(r"(party|billto|buyer|soldto|customer|invoiceto)", "Recipient", 200)
    has_pin = re.search(r"\b\d{6}\b", ctx.text.replace(" ", "")) or re.search(r"[-\s]\d{6}\b", ctx.text)
    evidence = [party] if party else []
    if party and has_pin:
        return _finding(rid, title, "PASS", "LOW",
                        "The invoice names the recipient with an address and PIN code.", evidence, regs, 0.75)
    missing = []
    if not party:
        missing.append("the recipient (party / bill to)")
    if not has_pin:
        missing.append("a PIN code in the address")
    return _finding(rid, title, "REVIEW", "MEDIUM", "Not found: " + ", ".join(missing) + ".", evidence, regs, 0.75)


def rule_invoice_gst_particulars(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "INV-003", "GST particulars on the invoice (CGST Rule 46)"
    if not ctx.text.strip():
        return _no_text(rid, title, regs)
    index = TextIndex(ctx.text)
    gstins = _gstins(index)
    purports_gst = index.has(r"(taxinvoice|gstin|cgst|sgst|igst|utgst|goodsandservicestax)")
    checks = [
        ("supplier GSTIN", len(gstins) >= 1),
        ("recipient GSTIN (or a statement that the recipient is unregistered)",
         len(gstins) >= 2 or index.has(r"unregistered")),
        ("HSN / SAC code", _has_hsn_code(ctx.text)),
        ("rate and amount of CGST/SGST or IGST", index.has(r"(cgst|sgst|igst|utgst)")),
        ("place of supply", index.has(r"placeofsupply")),
    ]
    missing = [label for label, ok in checks if not ok]
    evidence = [e for e in (index.evidence(r"(taxinvoice|gstin|cgst|sgst|igst)", "GST reference"),) if e]
    if not missing:
        return _finding(rid, title, "PASS", "LOW", "GSTIN, HSN/SAC, tax and place of supply are all present.",
                        evidence, regs, 0.8)
    if not purports_gst:
        return _finding(rid, title, "REVIEW", "MEDIUM",
                        "The invoice has no GST details (GSTIN, HSN/SAC, tax lines, place of supply). If the "
                        "supplier is registered under GST, this is not a valid tax invoice under Rule 46; "
                        "confirm the supplier's registration status.", evidence, regs, 0.75)
    return _finding(rid, title, "FAIL", "HIGH",
                    "The invoice refers to GST but is missing: " + "; ".join(missing) + ".", evidence, regs, 0.8)


def rule_invoice_gstin_valid(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "INV-004", "GSTIN format and check digit"
    if not ctx.text.strip():
        return _no_text(rid, title, regs)
    index = TextIndex(ctx.text)
    gstins = _gstins(index)
    if not gstins:
        return None  # INV-003 reports the missing GSTIN
    bad = [g for g in gstins if not gstin_is_valid(g)]
    evidence = [e for e in (index.evidence(_GSTIN_RE, "GSTIN"),) if e]
    if bad:
        return _finding(rid, title, "FAIL", "HIGH",
                        "Invalid GSTIN (format or check digit): " + ", ".join(bad) + ".", evidence, regs, 0.9)
    return _finding(rid, title, "PASS", "LOW",
                    f"{len(gstins)} GSTIN(s) have a valid format and check digit.", evidence, regs, 0.9)


_PAN_ENTITY = {"C": "company", "F": "firm / LLP", "P": "individual", "H": "HUF", "T": "trust",
               "A": "association of persons", "B": "body of individuals", "G": "government", "J": "artificial person",
               "L": "local authority"}


def rule_invoice_pan(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "INV-005", "PAN format and entity type"
    if not ctx.text.strip():
        return _no_text(rid, title, regs)
    pans = re.findall(r"\bPAN(?:/IT)?\s*(?:No\.?)?\s*[:\-]?\s*([A-Z0-9]{10})\b", ctx.text, re.I)
    if not pans:
        return None
    pan = pans[0].upper()
    index = TextIndex(ctx.text)
    evidence = [e for e in (index.evidence(r"pan(it)?(no)?" + pan.lower(), "PAN"),) if e]
    if not re.fullmatch(r"[A-Z]{5}\d{4}[A-Z]", pan):
        return _finding(rid, title, "FAIL", "MEDIUM", f"The PAN '{pan}' does not have a valid format.",
                        evidence, regs, 0.9)
    entity = pan[3]
    looks_company = index.has(r"(privatelimited|pvtltd|limited)")
    if looks_company and entity != "C":
        return _finding(rid, title, "REVIEW", "MEDIUM",
                        f"The PAN {pan} indicates a {_PAN_ENTITY.get(entity, 'different type of entity')} "
                        "(4th character) but the name looks like a company.", evidence, regs, 0.75)
    return _finding(rid, title, "PASS", "LOW",
                    f"The PAN {pan} has a valid format and its entity type ({_PAN_ENTITY.get(entity, entity)}) "
                    "is consistent with the name.", evidence, regs, 0.8)


def rule_invoice_line_total(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "INV-006", "Line items add up to the total"
    total = _invoice_total(ctx)
    if not total:
        return None
    position, amount = total
    lines = []
    for fact in ctx.facts[:position]:
        value = _decimal(fact.get("value"))
        if value is not None:
            lines.append((fact, value))
    if not lines:
        return None
    subtotal = sum(v for _, v in lines)
    evidence = [f for f, _ in lines] + [ctx.facts[position]]
    if abs(subtotal - amount) <= Decimal("0.01"):
        return _finding(rid, title, "PASS", "LOW",
                        f"{len(lines)} line item(s) add up to the invoice total of {amount:,.2f}.",
                        evidence, regs, 0.85)
    return _finding(rid, title, "FAIL", "HIGH",
                    f"The line items add up to {subtotal:,.2f} but the invoice total is {amount:,.2f}.",
                    evidence, regs, 0.85)


def rule_invoice_amount_in_words(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "INV-007", "Amount in words matches the total"
    total = _invoice_total(ctx)
    if not total or not ctx.text.strip():
        return None
    _, amount = total
    index = TextIndex(ctx.text)
    match = index.search(r"inwords(?:eoe)?(?:inr|rs|rupees)?(.{3,160}?)only")
    evidence = [e for e in (index.evidence(r"amountchargeable|inwords", "Amount in words", 120),) if e]
    if not match:
        return _finding(rid, title, "REVIEW", "LOW",
                        "No amount in words was found to compare with the total.", evidence, regs, 0.6)
    written = match.group(1).replace("and", "")
    rupees, paise = int(amount), int((amount - int(amount)) * 100)
    expected = indian_words(rupees).replace("and", "")
    if expected not in written or (paise and "paise" not in written):
        return _finding(rid, title, "FAIL", "HIGH",
                        f"The amount in words does not match the total of {amount:,.2f}.", evidence, regs, 0.85)
    return _finding(rid, title, "PASS", "LOW",
                    f"The amount in words agrees with the total of {amount:,.2f}.", evidence, regs, 0.9)


def rule_invoice_signature(ctx: RuleContext, regs: list[RegulationEvidence]) -> ComplianceFinding | None:
    rid, title = "INV-008", "Supplier's signature (CGST Rule 46(r))"
    if not ctx.text.strip():
        return _no_text(rid, title, regs)
    index = TextIndex(ctx.text)
    signed = index.evidence(r"(authori[sz]edsignatory|digitallysigned|digitalsignature|signatureofsupplier)",
                            "Signature")
    if signed:
        return _finding(rid, title, "PASS", "LOW",
                        "The invoice carries an authorised signatory line for the supplier.", [signed], regs, 0.75)
    generated = index.evidence(r"computergenerated", "Computer generated note")
    return _finding(rid, title, "REVIEW", "LOW",
                    "No signature or authorised signatory line was found. Rule 46(r) requires the supplier's "
                    "signature or digital signature.", [generated] if generated else [], regs, 0.7)


INVOICE_RULES: list[tuple[str, str, Evaluator]] = [
    ("INV-001", "Invoice number and date (CGST Rule 46(b), (c))", rule_invoice_identity),
    ("INV-002", "Recipient name and address (CGST Rule 46(e))", rule_invoice_parties),
    ("INV-003", "GST particulars on the invoice (CGST Rule 46)", rule_invoice_gst_particulars),
    ("INV-004", "GSTIN format and check digit", rule_invoice_gstin_valid),
    ("INV-005", "PAN format and entity type", rule_invoice_pan),
    ("INV-006", "Line items add up to the total", rule_invoice_line_total),
    ("INV-007", "Amount in words matches the total", rule_invoice_amount_in_words),
    ("INV-008", "Supplier's signature (CGST Rule 46(r))", rule_invoice_signature),
]


def _build() -> list[ComplianceRule]:
    rules = []
    for doc_type, group in (("agm_notice", NOTICE_RULES), ("invoice", INVOICE_RULES)):
        for rule_id, title, evaluator in group:
            rules.append(ComplianceRule(rule_id=rule_id, title=title,
                                        statement_types={doc_type}, evaluator=evaluator))
    return rules


NOTICE_INVOICE_RULES: list[ComplianceRule] = _build()
