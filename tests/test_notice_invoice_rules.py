from app.notice_invoice_rules import gstin_is_valid, indian_words
from app.rules_engine import ComplianceRulesEngine, RuleContext

NOTICE = """To the Members, Directors and Auditors of ABC Private Limited
NOTICE
Notice is hereby given that the Annual General Meeting of the Company will be held at the Registered Office
of the Company at 12 Park Road, Lucknow on 30.09.2024 at 4.30 p.m. to transact the following business:-
1. To consider and adopt the audited Balance Sheet as at 31st March, 2024 along with the report of Auditors and Directors thereon.
2. To appoint M/s Mishra N & Co. Chartered Accountants as Company Auditors to hold office from the conclusion
of this Annual General Meeting till the conclusion of the Annual General Meeting to be held in 2029
at a remuneration to be decided by the Board of Directors.
Notes
A member entitled to attend and vote is entitled to appoint a proxy and the proxy need not be a member.
The proxy form (MGT-11) duly completed must be deposited at least 48 hours before the meeting.
Place: Lucknow    BY ORDER OF THE BOARD
Dated: 06/09/2024   Director"""

INVOICE_TEXT = """TAX INVOICE
Invoice No. INV/2024/001 Dated 3-Apr-24
Supplier GSTIN: 27AAPFU0939F1ZV  ABC Traders, Mumbai
Party : XYZ Private Limited, 5 Park Street, Delhi-110001  GSTIN: 07AAGFF2194N1Z1
PAN/IT No :AAMCP7676G
Place of Supply: Delhi
Sl Particulars HSN/SAC Amount
1 Consulting 998313 3,500.00
2 Filing 998313 3,500.00
IGST 18% 1,260.00
Total 8,260.00
Amount Chargeable (in words) INR Eight Thousand Two Hundred Sixty Only
Authorised Signatory"""

FACTS = [
    {"label": "1 Consulting", "value": "3500.00"},
    {"label": "2 Filing", "value": "3500.00"},
    {"label": "IGST 18%", "value": "1260.00"},
    {"label": "Total", "value": "8260.00"},
]


def run(doc_type, text, facts=None):
    ctx = RuleContext(document_type=doc_type, facts=facts or [], text=text)
    return {f.rule_id: f for f in ComplianceRulesEngine().evaluate(ctx)}


# ------------------------------------------------------------------------------ notice

def test_compliant_notice_passes_everything_applicable():
    result = run("agm_notice", NOTICE)
    assert {f.status for f in result.values()} == {"PASS"}
    assert "NOTICE-010" not in result  # no special business, so the rule does not apply


def test_font_spacing_artifacts_do_not_break_the_notice_rules():
    spaced = NOTICE.replace("Notice is hereby", "No tice is her eby").replace("30.09.2024", "30.09 .2024")
    result = run("agm_notice", spaced)
    assert result["NOTICE-001"].status == "PASS" and result["NOTICE-004"].status == "PASS"


def test_agm_after_six_months_fails():
    result = run("agm_notice", NOTICE.replace("30.09.2024", "15.10.2024"))
    assert result["NOTICE-003"].status == "FAIL"


def test_short_notice_fails_unless_shorter_notice_is_mentioned():
    short = NOTICE.replace("06/09/2024", "25/09/2024")
    assert run("agm_notice", short)["NOTICE-004"].status == "FAIL"
    consented = short + "\nShorter notice consented by members."
    assert run("agm_notice", consented)["NOTICE-004"].status == "REVIEW"


def test_sunday_and_out_of_hours_meeting_fails():
    sunday = NOTICE.replace("30.09.2024", "29.09.2024")  # a Sunday
    assert run("agm_notice", sunday)["NOTICE-002"].status == "FAIL"
    night = NOTICE.replace("4.30 p.m.", "9.30 p.m.")
    assert run("agm_notice", night)["NOTICE-002"].status == "FAIL"


def test_any_other_business_and_ratification_wording_are_flagged():
    text = NOTICE.replace("Notes", "3. Any other business with permission of the chair.\nNotes").replace(
        "to be held in 2029", "to be held in 2029 (subject to ratification at every Annual General Meeting)")
    result = run("agm_notice", text)
    assert result["NOTICE-005"].status == "REVIEW"
    assert result["NOTICE-006"].status == "REVIEW" and "2018" in result["NOTICE-006"].message


def test_missing_proxy_details_and_addressees_need_review():
    text = NOTICE.replace("The proxy form (MGT-11) duly completed must be deposited at least 48 hours before the meeting.\n", "")
    text = text.replace("To the Members, Directors and Auditors of ABC Private Limited\n", "")
    result = run("agm_notice", text)
    assert result["NOTICE-007"].status == "REVIEW"
    assert result["NOTICE-009"].status == "REVIEW"


def test_special_business_needs_an_explanatory_statement():
    text = NOTICE + "\nSpecial Business: to pass a Special Resolution to alter the articles."
    assert run("agm_notice", text)["NOTICE-010"].status == "FAIL"
    assert run("agm_notice", text + "\nExplanatory Statement under section 102.")["NOTICE-010"].status == "PASS"


# ----------------------------------------------------------------------------- invoice

def test_gstin_check_digit():
    assert gstin_is_valid("27AAPFU0939F1ZV") and gstin_is_valid("07AAGFF2194N1Z1")
    assert not gstin_is_valid("27AAPFU0939F1ZX")  # wrong check digit
    assert not gstin_is_valid("27AAPFU0939F1Z")  # too short


def test_indian_number_words():
    assert indian_words(7000) == "seventhousand"
    assert indian_words(8260) == "eightthousandtwohundredsixty"
    assert indian_words(123456) == "onelakhtwentythreethousandfourhundredfiftysix"


def test_complete_gst_invoice_passes():
    result = run("invoice", INVOICE_TEXT, FACTS)
    assert {f.status for f in result.values()} == {"PASS"}, {k: f.message for k, f in result.items() if f.status != "PASS"}


def test_invoice_without_gst_details_is_a_review_not_a_failure():
    plain = "Invoice No. BILL/133 3-Apr-24 Dated\nINVOICE\nParty : ABC Pvt Ltd, Delhi-110001\nAuthorised Signatory"
    result = run("invoice", plain)
    assert result["INV-003"].status == "REVIEW"


def test_invoice_that_mentions_gst_but_lacks_particulars_fails():
    partial = INVOICE_TEXT.replace("GSTIN: 07AAGFF2194N1Z1", "").replace("Place of Supply: Delhi", "")
    assert run("invoice", partial, FACTS)["INV-003"].status == "FAIL"


def test_invalid_gstin_fails():
    bad = INVOICE_TEXT.replace("27AAPFU0939F1ZV", "27AAPFU0939F1ZX")
    assert run("invoice", bad, FACTS)["INV-004"].status == "FAIL"


def test_line_items_that_do_not_add_up_fail():
    facts = [dict(f) for f in FACTS]
    facts[1]["value"] = "3000.00"
    assert run("invoice", INVOICE_TEXT, facts)["INV-006"].status == "FAIL"


def test_amount_in_words_mismatch_fails():
    wrong = INVOICE_TEXT.replace("Eight Thousand Two Hundred Sixty", "Eight Thousand Two Hundred Fifty")
    assert run("invoice", wrong, FACTS)["INV-007"].status == "FAIL"


def test_overlong_invoice_number_is_flagged():
    long_no = INVOICE_TEXT.replace("INV/2024/001", "INV/2024/ABCDEFGHIJKL/0001")
    assert run("invoice", long_no, FACTS)["INV-001"].status == "REVIEW"


def test_pan_entity_type_mismatch_is_flagged():
    wrong = INVOICE_TEXT.replace("AAMCP7676G", "AAMPP7676G")
    assert run("invoice", wrong, FACTS)["INV-005"].status == "REVIEW"


def test_empty_text_gives_review_not_a_crash():
    result = run("invoice", "")
    assert result and all(f.status == "REVIEW" for f in result.values())
