from app.rules_engine import ComplianceRulesEngine, RuleContext

DIRECTORS = """DIRECTORS' REPORT
Your Directors have pleasure in presenting their Annual Report for the Financial Year ended on 31st March, 2024.
OPERATION IN BUSINESS PERFORMANCE: net loss.
1.NUMBER OF BOARD MEETING HELD DURING THE YEAR: Company convened 4 board meetings during the year.
2.DATE OF BOARD MEETINGS HELD DURING THE YEAR: The board meetings were on 09/06/2023, 05/09/2023, 20/12/2023, 22/03/2024.
3. NUMBERS AND DATE OF COMMITTEE MEETINGS HELD DURING THE YEAR: None.
EXTRACT OF ANNUAL RETURN: an extract of annual return in MGT 9 is annexed.
COMMENTS BY BOARD OF DIRECTORS ON AUDITORS REPORT: self explanatory.
PARTICULARS OF LOANS, GUARANTEES OR INVESTMENTS UNDER SECTION 186: none.
DIVIDEND: none. RESERVES: none.
STATUTORY AUDITORS: M/s Mishra N & Co appointed; certificate under section 141 received.
PARTICULARS OF CONTRACTS WITH RELATED PARTIES: nil.
CONSERVATION OF ENERGY: not applicable. RISK MANAGEMENT: in place. CORPORATE SOCIAL RESPONSIBILITY: not applicable.
DIRECTORS' RESPONSIBILITY STATEMENT: applicable accounting standards have been followed; the Directors have
selected such accounting policies and applied them consistently; maintenance of adequate accounting records;
annual accounts on a going concern basis.
BRIEF DESCRIPTION OF STATE OF COMPANY'S AFFAIRS. MATERIAL CHANGES AND COMMITMENTS: none.
For & Behalf of Board of Directors
VIVEK KUSHWAHA   AWANTEKAA SINGH
DIN No.:- 09551132   DIN No.:- 09551131
Date:- 06.09.2024
Place:- Lucknow"""

AUDITOR = """TO THE MEMBERS OF ABC PVT LTD
Report on the Audit of the Financial Statements
Opinion We have audited the financial statements as at March 31, 2024.
In our opinion the statements give a true and fair view.
Basis for Opinion We conducted our audit in accordance with the Standards on Auditing specified under section 143(10).
We are independent in accordance with the Code of Ethics. The audit evidence is sufficient and appropriate.
Management's Responsibility ... going concern ... Auditor's Responsibility ...
Report on Other Legal and Regulatory Requirements: as required by section 143(3) ... section 164(2) ... Rule 11.
As required by the Companies (Auditor's Report) Order, 2020 ...
Report on internal financial controls over financial reporting: the Company has an adequate internal financial controls system.
For: Mishra N & Co. FRN: 031764C CA. Nitesh Mishra Membership No. 423745
UDIN No: 24423745BKFVXY1234
Place: Lucknow Date: 06/09/2024"""


def run(doc_type, text):
    findings = ComplianceRulesEngine().evaluate(RuleContext(document_type=doc_type, facts=[], text=text))
    return {f.rule_id: f for f in findings}


def test_directors_report_flags_mgt9_only():
    result = run("directors_report", DIRECTORS)
    assert len(result) == 11
    assert {k for k, f in result.items() if f.status != "PASS"} == {"DIRREP-009"}
    assert "MGT-9" in result["DIRREP-009"].message


def test_board_meeting_count_mismatch_fails():
    result = run("directors_report", DIRECTORS.replace("convened 4 board", "convened 5 board"))
    assert result["DIRREP-002"].status == "FAIL"


def test_board_meeting_gap_over_120_days_fails():
    result = run("directors_report", DIRECTORS.replace("20/12/2023", "20/02/2024"))
    assert result["DIRREP-003"].status == "FAIL" and "gap" in result["DIRREP-003"].message


def test_report_dated_before_year_end_fails():
    result = run("directors_report", DIRECTORS.replace("06.09.2024", "06.02.2024"))
    assert result["DIRREP-011"].status == "FAIL"


def test_single_director_signature_needs_review():
    result = run("directors_report", DIRECTORS.replace("DIN No.:- 09551131", ""))
    assert result["DIRREP-010"].status == "REVIEW"


def test_missing_responsibility_statement_fails():
    text = DIRECTORS.split("DIRECTORS' RESPONSIBILITY STATEMENT")[0] + "\nDate:- 06.09.2024"
    assert run("directors_report", text)["DIRREP-001"].status == "FAIL"


def test_complete_auditors_report_passes_everything():
    result = run("auditors_report", AUDITOR)
    assert len(result) == 9
    assert {f.status for f in result.values()} == {"PASS"}


def test_missing_udin_fails():
    result = run("auditors_report", AUDITOR.replace("24423745BKFVXY1234", ""))
    assert result["AUDREP-008"].status == "FAIL" and "UDIN" in result["AUDREP-008"].message


def test_blank_udin_followed_by_place_is_not_mistaken_for_a_udin():
    text = AUDITOR.replace("UDIN No: 24423745BKFVXY1234\nPlace: Lucknow", "U DIN No:\nPlace: Lucknow")
    assert run("auditors_report", text)["AUDREP-008"].status == "FAIL"


def test_caro_2016_is_flagged_and_2020_passes():
    assert run("auditors_report", AUDITOR)["AUDREP-006"].status == "PASS"
    old = run("auditors_report", AUDITOR.replace("Order, 2020", "Order, 2016"))["AUDREP-006"]
    assert old.status == "REVIEW" and "2016" in old.message


def test_modified_opinion_is_flagged():
    text = AUDITOR.replace("Basis for Opinion", "Basis for Qualified Opinion")
    assert run("auditors_report", text)["AUDREP-002"].status == "REVIEW"


def test_font_spacing_artifacts_do_not_break_matching():
    spaced = AUDITOR.replace("Basis for Opinion", "Ba sis fo r Opi nion").replace("Code of Ethics", "Cod e of Et hics")
    assert run("auditors_report", spaced)["AUDREP-003"].status == "PASS"


def test_pages_are_reported_when_text_has_page_breaks():
    paged = "intro page\f" + AUDITOR
    ev = run("auditors_report", paged)["AUDREP-003"].evidence
    assert {e["source_page"] for e in ev} == {2}


def test_no_text_gives_review_not_a_crash():
    result = run("auditors_report", "")
    assert len(result) == 9 and {f.status for f in result.values()} == {"REVIEW"}


def test_rules_do_not_run_for_other_document_types():
    assert run("invoice", DIRECTORS) == {}
