import copy

from fastapi.testclient import TestClient

from app.cross_rules import CrossDocumentEngine
from app.main import app


def fact(label, cur, prev, page=1):
    return {"label": label, "value": str(cur), "values": [str(cur), str(prev)], "source_page": page}


FS_FACTS = [
    fact("Shareholder's Funds", 110722, 146726),
    fact("(a) Share Capital", 200000, 200000),
    fact("(b) Reserves and Surplus", -89278, -53274),
    fact("Current Liabilities", 81546, 74322),
    fact("(c )Other Current Liabilities", 81546, 74322),
    fact("TOTAL", 192268, 221048),
    fact("Current Assets", 192268, 221048),
    fact("(c ) Cash and cash equivalents", 110848, 112488),
    fact("(e) Other current assets", 81420, 108560),
    fact("TOTAL", 192268, 221048),
    fact("Finance Cost", "364.00", "214.00", 2),
    fact("Other Expenses", "35640.00", "53060.00", 2),
    fact("Total Expenses", "36004.00", "53274.00", 2),
    fact("viii. Profit before tax", "-36004.00", "-53274.00", 2),
    fact("x. Profit(Loss) for the year", "-36004.00", "-53274.00", 2),
    fact("- Basic & Diluted", "-1.80", "-2.66", 2),
    fact("2 LEGAL AND PROFESSIONAL FEES", "8500.00", "8500.00", 3),
]
FS_TEXT = (
    "ABC PRIVATE LIMITED Registered Office: 5434/35, Flat No-106 Pragati Vihar DLF Phase- 4 Gurugram Gurgaon HR 122009 IN "
    "CIN:- U72501HR2022PTC102347 BALANCE SHEET AS AT 31ST MARCH, 2024 "
    "STATEMENT OF CASH FLOWS FOR THE YEAR ENDED 31ST MARCH, 2024 "
    "FOR : MISHRA N & CO. CHARTERED ACCOUNTANT FRN.: 031764C CA NITESH MISHRA "
    "VIVEK KUSHWAHA AWANTEKAA SINGH DIN: 09551132 DIN: 09551131 M.No- 423745 UDIN: Place: LUCKNOW Date: 05-09-2024"
)
DR_FACTS = [
    fact("3 Total Expenditure", "36004.00", "53274.00"),
    fact("4 Profit Before Tax", "-36004.00", "-53274.00"),
    fact("6 Profit after Tax", "-36004.00", "-53274.00"),
    fact("7 EPS", "-1.80", "-2.66"),
]
DR_TEXT = (
    "ABC Private Limited 5434/35, Flat No-106 Pragati Vihar DLF Phase- 4 Gurugram-122009 "
    "CIN No : U72501HR2022PTC102347 DIRECTORS' REPORT "
    "Annual Report for the Financial Year ended on 31st March, 2024. "
    "Your Company has incurred Net loss of Rs. 36004 as against Net loss of Rs. 53274 in the previous year. "
    "COMMENTS BY BOARD OF DIRECTORS ON AUDITORS REPORT: The observations of the Statutory Auditors are self explanatory. "
    "DIVIDEND: Considering the current year loss, your Board of Directors do not recommend payment of dividend. "
    "CHANGE IN SHARE CAPITAL: There has been no change in Share capital of the company. "
    "STATUTORY AUDITORS M/s. Mishra N & Co., Chartered Accountants, be and hereby appointed as Statutory Auditors "
    "of the Company for a term of five consecutive years. "
    "For & Behalf of Board of Directors VIVEK KUSHWAHA AWANTEKAA SINGH DIN No.:- 09551132 DIN No.:- 09551131 "
    "Date:- 06.09.2024 Place:- Lucknow"
)
AR_TEXT = (
    "MISHRA N & Co. CHARTERED ACCOUNTANTS TO THE MEMBERS OF ABC PVT LTD Report on the Audit of the Financial Statements "
    "Opinion We have audited the financial statements of ABC PVT LTD, which comprise the balance sheet as at 31st March 2024 "
    "and the statement of profit and loss, and statement of cash flows for the year then ended, and notes. "
    "In our opinion the statements give a true and fair view of the state of affairs as at March 31, 2024, "
    "and its loss for the year ended on that date. "
    "For: Mishra N & Co. Chartered Accountant FRN: 031764C CA. Nitesh Mishra Membership No. 423745 UDIN No: "
    "Place: Lucknow Date: 06/09/2024"
)
NT_TEXT = (
    "5434/ 35, Fla t No-106 Pragati Vihar DLF P hase- 4 G urugram-1220 09 CIN:- U72501HR2022PTC102347 NOTICE "
    "Notice is hereby given that the Annual General Meeting of ABC Private Limited "
    "will be held at the Registered Office on 30.09.2024 at 4.30 p.m. 1. To consider and adopt the audited Balance Sheet as at "
    "31st March, 2024 along with the report of Auditors and Directors thereon. 2. To appoint M/s Mishra N & Co. Chartered Accountants as Company Auditors to hold office "
    "till the conclusion of the Annual General Meeting to be held in 2029. Place: Lucknow Dated: 06/09/2024"
)


def package(**overrides):
    docs = {
        "fs": {"document_type": "balance_sheet", "document_name": "fs.pdf", "text": FS_TEXT, "facts": FS_FACTS},
        "dr": {"document_type": "directors_report", "document_name": "dr.pdf", "text": DR_TEXT, "facts": DR_FACTS},
        "ar": {"document_type": "auditors_report", "document_name": "ar.pdf", "text": AR_TEXT, "facts": []},
        "nt": {"document_type": "agm_notice", "document_name": "nt.pdf", "text": NT_TEXT, "facts": []},
    }
    for key, change in overrides.items():
        if change is None:
            docs.pop(key)
        else:
            docs[key] = {**docs[key], **change}
    return list(docs.values())


def run(**overrides):
    return {f.rule_id: f for f in CrossDocumentEngine().evaluate(package(**overrides))}


def text_swap(key, old, new):
    base = {"fs": FS_TEXT, "dr": DR_TEXT, "ar": AR_TEXT, "nt": NT_TEXT}[key]
    assert old in base, old
    return {key: {"text": base.replace(old, new)}}


def test_a_consistent_package_passes_every_cross_check():
    result = run()
    assert len(result) == 14
    assert {f.status for f in result.values()} == {"PASS"}, {k: f.message for k, f in result.items() if f.status != "PASS"}


def test_different_cins_fail():
    result = run(**text_swap("dr", "U72501HR2022PTC102347", "U99999MH2020PTC111111"))
    assert result["XDOC-001"].status == "FAIL" and "CINs appear" in result["XDOC-001"].message


def test_a_document_that_does_not_name_the_company_is_reviewed():
    result = run(**text_swap("nt", "of ABC Private Limited", "of the Company"))
    assert result["XDOC-001"].status == "REVIEW" and "AGM notice" in result["XDOC-001"].message


def test_company_name_variants_pvt_ltd_and_private_limited_match():
    assert run()["XDOC-001"].status == "PASS"  # the auditor's report says "PVT LTD"


def test_different_year_ends_fail():
    result = run(**text_swap("ar", "31st March 2024", "31st March 2023"))
    assert result["XDOC-002"].status in ("FAIL", "PASS")  # one stray date is outvoted by March 31, 2024
    both = {**text_swap("ar", "31st March 2024", "31st March 2023")["ar"]}
    both["text"] = both["text"].replace("March 31, 2024", "March 31, 2023")
    assert run(ar=both)["XDOC-002"].status == "FAIL"


def test_auditor_registration_number_must_match():
    result = run(**text_swap("ar", "FRN: 031764C", "FRN: 099999C"))
    assert result["XDOC-003"].status == "FAIL" and "registration numbers" in result["XDOC-003"].message


def test_auditor_named_in_the_directors_report_must_appear_in_the_audit_report():
    result = run(**text_swap("dr", "M/s. Mishra N & Co., Chartered", "M/s. Sharma & Associates, Chartered"))
    assert result["XDOC-003"].status == "FAIL" and "sharmaassociates" in result["XDOC-003"].message


def test_audit_report_dated_before_the_statements_or_directors_report_is_reviewed():
    before_fs = run(**text_swap("ar", "Date: 06/09/2024", "Date: 04/09/2024"))["XDOC-004"]
    assert before_fs.status == "REVIEW" and "before the financial statements" in before_fs.message
    before_dr = run(**text_swap("ar", "Date: 06/09/2024", "Date: 05/09/2024"))["XDOC-004"]
    assert before_dr.status == "REVIEW" and "Directors' Report" in before_dr.message


def test_notice_dated_before_the_reports_is_reviewed():
    result = run(**text_swap("nt", "Dated: 06/09/2024", "Dated: 01/09/2024"))
    assert result["XDOC-004"].status == "REVIEW" and "AGM notice" in result["XDOC-004"].message


def test_a_modified_audit_opinion_needs_a_real_reply_from_the_board():
    modified = text_swap("ar", "Opinion We have audited", "Basis for Qualified Opinion We have audited")
    assert run(**modified)["XDOC-005"].status == "REVIEW"
    no_reply = dict(modified)
    no_reply["dr"] = {"text": DR_TEXT.replace("COMMENTS BY BOARD OF DIRECTORS ON AUDITORS REPORT: The observations "
                                              "of the Statutory Auditors are self explanatory.", "")}
    assert run(**no_reply)["XDOC-005"].status == "FAIL"


def test_the_narrative_must_agree_with_the_statements_on_profit_or_loss():
    wrong_year = run(**text_swap("dr", "as against Net loss of Rs. 53274", "as against Net profit of Rs. 53274"))
    assert wrong_year["XDOC-006"].status == "FAIL" and "prior year" in wrong_year["XDOC-006"].message
    wrong_amount = run(**text_swap("dr", "Net loss of Rs. 36004", "Net loss of Rs. 30000"))
    assert wrong_amount["XDOC-006"].status == "FAIL" and "36,004" in wrong_amount["XDOC-006"].message
    audit_says_profit = run(**text_swap("ar", "and its loss for the year", "and its profit for the year"))
    assert audit_says_profit["XDOC-006"].status == "FAIL" and "Auditor's Report" in audit_says_profit["XDOC-006"].message


def test_the_directors_report_summary_must_match_the_statements():
    facts = copy.deepcopy(DR_FACTS)
    facts[1]["values"][0] = "-30000.00"
    result = run(dr={"facts": facts})
    assert result["XDOC-007"].status == "FAIL" and "profit before tax" in result["XDOC-007"].message


def test_no_change_in_share_capital_must_match_the_balance_sheet():
    facts = copy.deepcopy(FS_FACTS)
    facts[1]["values"][1] = "150000"
    result = run(fs={"facts": facts})
    assert result["XDOC-008"].status == "FAIL" and "150,000.00" in result["XDOC-008"].message


def test_a_misspelt_no_change_statement_is_still_recognised():
    result = run(**text_swap("dr", "no change in Share capital", "no change in Share caipt al"))
    assert result["XDOC-008"].status == "PASS"


def test_differing_director_dins_are_reviewed():
    result = run(**text_swap("fs", "DIN: 09551131", "DIN: 09559999"))
    assert result["XDOC-009"].status == "REVIEW"


def test_auditor_term_must_agree_between_report_and_notice():
    one_year = run(**text_swap("dr", "for a term of five consecutive years",
                               "to hold office till the conclusion of ensuing Annual General Meeting"))
    assert one_year["XDOC-010"].status == "REVIEW" and "5 years" in one_year["XDOC-010"].message


def test_the_audit_opinion_must_not_name_a_statement_that_is_absent():
    result = run(**text_swap("fs", "STATEMENT OF CASH FLOWS FOR THE YEAR ENDED 31ST MARCH, 2024", ""))
    assert result["XDOC-011"].status == "REVIEW" and "cash flows" in result["XDOC-011"].message


def test_rules_that_need_a_missing_document_stay_silent():
    result = run(fs=None, nt=None)  # directors' and auditor's reports only
    assert set(result) == {"XDOC-001", "XDOC-002", "XDOC-003", "XDOC-004", "XDOC-005"}
    assert run(dr=None, ar=None, nt=None).keys() == set()  # one document cannot be cross-checked


def test_findings_quote_both_documents():
    result = run(**text_swap("dr", "as against Net loss of Rs. 53274", "as against Net profit of Rs. 53274"))
    assert {e.get("document") for e in result["XDOC-006"].evidence} >= {"fs.pdf", "dr.pdf"}


def test_cross_check_endpoint():
    client = TestClient(app)
    response = client.post("/api/v1/compliance/cross-check", json={"documents": package()})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 14 and {f["status"] for f in body} == {"PASS"}
    assert client.post("/api/v1/compliance/cross-check", json={"documents": package()[:1]}).status_code == 422


# ------------------------------------------------------------------ notice and invoice

INVOICE_TEXT = (
    "SUBJECT TO LUCKNOW JURISDICTION Invoice No. BILL/133 3-Apr-24 Dated Mishra N & Co. UGF-004, Church Road, Aliganj "
    "Lucknow INVOICE Party : ABC Private Limited 5434/35, Flat No-106, Pragati Vihar, DLF Phase-4 Gurugram, "
    "Haryana-122009 PAN/IT No :AAMCP7676G Sl Particulars Amount No. "
    "1 Balance Sheet & Projections 3,500.00 ITR and Financials FY 23-24 2 ROC Filing Fees 3,500.00 Form AOC-4, MGT-7 "
    "Total 7,000.00 Amount Chargeable (in words) INR Seven Thousand Only Company's Bank Details "
    "A/c Holder's Name : Mishra N & Co. Bank Name : UCO Bank for Mishra N & Co. Authorised Signatory"
)
INVOICE_FACTS = [
    {"label": "1 Balance Sheet & Projections", "value": "3500.00", "values": ["3500.00"], "source_page": 1},
    {"label": "2 ROC Filing Fees", "value": "3500.00", "values": ["3500.00"], "source_page": 1},
    {"label": "Total", "value": "7000.00", "values": ["7000.00"], "source_page": 1},
]


def with_invoice(**overrides):
    docs = package(**overrides)
    docs.append({"document_type": "invoice", "document_name": "bill.pdf", "text": INVOICE_TEXT,
                 "facts": INVOICE_FACTS})
    return docs


def run_invoice(text_change=None, **overrides):
    docs = with_invoice(**overrides)
    if text_change:
        docs[-1] = {**docs[-1], **text_change}
    return {f.rule_id: f for f in CrossDocumentEngine().evaluate(docs)}


def test_a_package_with_an_invoice_passes_except_the_auditor_services_review():
    result = run_invoice()
    assert len(result) == 17
    not_passing = {k: f.status for k, f in result.items() if f.status != "PASS"}
    assert not_passing == {"XDOC-016": "REVIEW"}, not_passing


def test_a_different_pin_code_or_flat_in_any_document_is_reviewed():
    pin = run(**text_swap("nt", "G urugram-1220 09", "G urugram-1220 01"))
    assert pin["XDOC-012"].status == "REVIEW" and "PIN code differs" in pin["XDOC-012"].message
    flat = run(**text_swap("dr", "Flat No-106", "Flat No-206"))
    assert flat["XDOC-012"].status == "REVIEW" and "building and flat" in flat["XDOC-012"].message
    invoice = run_invoice({"text": INVOICE_TEXT.replace("Haryana-122009", "Haryana-122001")})
    assert invoice["XDOC-012"].status == "REVIEW"


def test_the_building_number_is_not_mistaken_for_a_pin_code():
    # "5434/35" squashes to a six digit number; it must not be read as a PIN.
    assert run()["XDOC-012"].status == "PASS"


def test_the_notice_needs_every_paper_it_asks_members_to_adopt():
    result = run(ar=None)
    assert result["XDOC-013"].status == "REVIEW" and "Auditor's Report" in result["XDOC-013"].message
    assert run(dr=None)["XDOC-013"].status == "REVIEW"
    assert run(fs=None)["XDOC-013"].status == "REVIEW"
    assert run()["XDOC-013"].status == "PASS"


def test_dividend_must_agree_between_the_directors_report_and_the_notice():
    declared = run(**text_swap("nt", "1. To consider", "0. To declare a final dividend. 1. To consider"))
    assert declared["XDOC-014"].status == "REVIEW" and declared["XDOC-014"].severity == "HIGH"
    recommended = run(**text_swap("dr", "do not recommend payment of dividend",
                                  "recommend a dividend of Rs. 5 per share"))
    assert recommended["XDOC-014"].status == "REVIEW" and "no item to declare" in recommended["XDOC-014"].message
    both = text_swap("dr", "do not recommend payment of dividend", "recommend a dividend of Rs. 5 per share")
    both["nt"] = {"text": NT_TEXT.replace("1. To consider", "0. To declare a final dividend. 1. To consider")}
    assert run(**both)["XDOC-014"].status == "PASS"


def test_the_invoice_must_be_addressed_to_the_company():
    result = run_invoice({"text": INVOICE_TEXT.replace("Party : ABC Private Limited", "Party : Other Traders Pvt Ltd")})
    assert result["XDOC-015"].status == "REVIEW" and "abc" in result["XDOC-015"].message


def test_an_invoice_from_the_statutory_auditor_for_accounting_work_is_flagged():
    result = run_invoice()["XDOC-016"]
    assert result.status == "REVIEW" and "Balance Sheet" in result.message


def test_an_audit_fee_invoice_from_the_auditor_is_not_flagged():
    audit_only = INVOICE_TEXT.replace("Balance Sheet & Projections", "Statutory audit fee").replace(
        "ITR and Financials FY 23-24", "for the year").replace("ROC Filing Fees", "Out of pocket expenses").replace(
        "Form AOC-4, MGT-7", "")
    assert run_invoice({"text": audit_only})["XDOC-016"].status == "PASS"


def test_an_invoice_from_someone_who_is_not_the_auditor_is_not_checked_for_independence():
    other = INVOICE_TEXT.replace("Mishra N & Co.", "Sharma & Associates")
    assert "XDOC-016" not in run_invoice({"text": other})


def test_the_auditor_is_recognised_from_the_audit_report_signature_even_without_the_other_reports():
    result = run_invoice(dr=None, nt=None)
    assert result["XDOC-016"].status == "REVIEW"


def test_a_year_end_invoice_for_the_year_must_be_accrued_in_the_statements():
    base = run_invoice()["XDOC-017"]
    assert base.status == "PASS" and "8,500.00" in base.message
    facts = copy.deepcopy(FS_FACTS)
    facts[-1]["values"][0] = "5000.00"
    facts[-1]["value"] = "5000.00"
    assert run_invoice(fs={"facts": facts})["XDOC-017"].status == "REVIEW"
    no_fees = [f for f in FS_FACTS if "PROFESSIONAL" not in f["label"]]
    result = run_invoice(fs={"facts": no_fees})["XDOC-017"]
    assert result.status == "REVIEW" and result.severity == "LOW"


def test_an_invoice_dated_within_the_year_has_no_cutoff_question():
    inside = INVOICE_TEXT.replace("3-Apr-24", "3-Mar-24")
    assert "XDOC-017" not in run_invoice({"text": inside})
    unspecific = INVOICE_TEXT.replace("FY 23-24", "")
    assert "XDOC-017" not in run_invoice({"text": unspecific})


def test_invoice_rules_stay_silent_without_an_invoice():
    assert not any(k in run() for k in ("XDOC-015", "XDOC-016", "XDOC-017"))


def test_invoice_labels_use_the_file_name_in_evidence():
    result = run_invoice()
    assert "bill.pdf" in {e.get("document") for e in result["XDOC-016"].evidence}
