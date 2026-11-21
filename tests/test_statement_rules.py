import copy

from app.rules_engine import ComplianceRulesEngine, RuleContext


def row(label, cur, prev, page):
    return {"label": label, "value": str(cur), "values": [str(cur), str(prev)], "source_page": page}


BASE_FACTS = [
    # balance sheet (page 1)
    row("Shareholder's Funds", 110722, 146726, 1),
    row("(a) Share Capital", 200000, 200000, 1),
    row("(b) Reserves and Surplus", -89278, -53274, 1),
    row("Current Liabilities", 81546, 74322, 1),
    row("(c )Other Current Liabilities", 81546, 74322, 1),
    row("TOTAL", 192268, 221048, 1),
    row("Current Assets", 192268, 221048, 1),
    row("(c ) Cash and cash equivalents", 110848, 112488, 1),
    row("(e) Other current assets", 81420, 108560, 1),
    row("TOTAL", 192268, 221048, 1),
    # statement of profit and loss (page 2)
    row("Finance Cost", "364.00", "214.00", 2),
    row("Other Expenses", "35640.00", "53060.00", 2),
    row("Total Expenses", "36004.00", "53274.00", 2),
    row("viii. Profit before tax", "-36004.00", "-53274.00", 2),
    row("x. Profit(Loss) for the year", "-36004.00", "-53274.00", 2),
    row("- Basic & Diluted", "-1.80", "-2.66", 2),
    # notes (pages 3-4)
    row("Total", "200000.00", "200000.00", 3),
    row("Total", "-89278.00", "-53274.00", 3),
    row("Total", "81546.00", "74322.23", 3),
    row("Total", "110848.29", "112488.23", 3),
    row("Total", "81420.00", "108560.00", 3),
    row("Total", "364.00", "214.00", 3),
    row("Total", "35640.00", "53060.00", 4),
]

SIGNATURE = ("FOR : MISHRA N & CO. CHARTERED ACCOUNTANT FRN.: 031764C CA NITESH MISHRA (Proprietor) "
             "For & On Behalf Of: ABC PRIVATE LIMITED VIVEK KUSHWAHA AWANTEKAA SINGH DIN: 09551132 DIN: 09551131 "
             "M.No- 423745 UDIN: {udin} Place: LUCKNOW Date: 05-09-2024")
PAGE1 = ("ABC PRIVATE LIMITED BALANCE SHEET AS AT 31ST MARCH, 2024 (Amount In Rs.) Particulars At 31-March-2024 "
         "EQUITY AND LIABILITIES Shareholder's Funds (a) Share Capital (b) Reserves and Surplus "
         "Share Application money pending allotment Non-Current Liabilities (a) Long-Term Borrowings "
         "Current Liabilities (b) Trade Payables TOTAL ASSETS Non-Current Assets Current Assets (a) Inventories "
         "(b) Trade receivables (c ) Cash and cash equivalents TOTAL ")
PAGE2 = ("PROFIT & LOSS STATEMENT FOR THE YEAR ENDED 31ST MARCH, 2024 Revenue from operations Other Income "
         "Total Income EXPENDITURE Employee benefits expenses Finance Cost Depreciation Other Expenses Total Expenses "
         "Profit before tax Tax expense: Profit(Loss) for the year Earning per equity share: Basic & Diluted ")
PAGE3 = ("Notes forming part of the Financial Statements Note 1 Share Capital 20000 EQUITY SHARES OF RS. 10/- EACH. ")


def text(udin="24423745BKFVXY1234", page1=PAGE1, page2=PAGE2):
    sig = SIGNATURE.format(udin=udin)
    return "\f".join([page1 + sig, page2 + sig, PAGE3, "Note 20 Other Expenses"])


def run(facts=None, doc_text=None, doc_type="balance_sheet", framework="Other"):
    ctx = RuleContext(document_type=doc_type, facts=BASE_FACTS if facts is None else facts,
                      text=text() if doc_text is None else doc_text, framework=framework)
    return {f.rule_id: f for f in ComplianceRulesEngine().evaluate(ctx)}


def with_change(label_key, *, cur=None, prev=None, nth=0):
    facts = copy.deepcopy(BASE_FACTS)
    matches = [f for f in facts if f["label"] == label_key]
    f = matches[nth]
    if cur is not None:
        f["value"], f["values"][0] = str(cur), str(cur)
    if prev is not None:
        f["values"][1] = str(prev)
    return facts


def test_consistent_statements_pass_every_statement_rule():
    result = run()
    ids = [k for k in result if k.startswith(("FSBS", "FSPL", "FSX"))]
    assert len(ids) == 13
    failing = {k: result[k].message for k in ids if result[k].status != "PASS" and k != "FSPL-005"}
    assert failing == {}


def test_prior_year_eps_inconsistent_with_share_capital_is_reviewed():
    facts = with_change("- Basic & Diluted", prev="-5.33")
    result = run(facts)
    assert result["FSPL-005"].status == "REVIEW" and "9,995" in result["FSPL-005"].message
    assert run()["FSPL-005"].status == "PASS"  # -2.66 on 20,000 shares is consistent


def test_current_year_imbalance_fails():
    facts = with_change("TOTAL", cur=190000, nth=1)
    assert run(facts)["FSBS-001"].status == "FAIL"


def test_prior_year_imbalance_fails_even_when_current_year_balances():
    facts = with_change("TOTAL", prev=230000, nth=1)
    result = run(facts)
    assert result["FSBS-001"].status == "FAIL" and "prior year" in result["FSBS-001"].message


def test_subtotals_that_do_not_add_up_to_the_total_fail():
    facts = with_change("Current Liabilities", cur=70000)
    assert run(facts)["FSBS-002"].status == "FAIL"


def test_nil_headings_missing_from_the_facts_count_as_zero():
    # Non-Current Liabilities / Assets are all dashes in the PDF so they never reach the facts.
    assert all("Non-Current" not in f["label"] for f in BASE_FACTS)
    assert run()["FSBS-002"].status == "PASS"


def test_line_items_that_do_not_add_up_to_their_section_fail():
    facts = with_change("(c ) Cash and cash equivalents", cur=100000)
    result = run(facts)
    assert result["FSBS-003"].status == "FAIL" and "current assets" in result["FSBS-003"].message


def test_a_note_total_that_matches_no_statement_line_is_reviewed():
    facts = with_change("Total", cur="123456.00", nth=2)  # the "other current liabilities" note
    result = run(facts)
    assert result["FSBS-006"].status == "REVIEW" and "123,456.00" in result["FSBS-006"].message


def test_missing_prior_year_column_and_units_are_reviewed():
    facts = copy.deepcopy(BASE_FACTS)
    for f in facts[:10]:
        f["values"] = f["values"][:1]
    assert run(facts)["FSBS-005"].status == "REVIEW"
    no_units = text().replace("(Amount In Rs.)", "")
    assert run(doc_text=no_units)["FSBS-005"].status == "REVIEW"


def test_division_one_layout_under_ind_as_is_flagged_for_confirmation():
    result = run(framework="Ind AS")["FSBS-004"]
    assert result.status == "REVIEW" and "Division I" in result.message
    assert run(framework="Other")["FSBS-004"].status == "PASS"


def test_division_two_layout_is_checked_against_ind_as_headings():
    ind_as = "BALANCE SHEET Equity share capital Other equity Non-current liabilities Financial liabilities " \
             "Current liabilities Total equity and liabilities Non-current assets Property, plant and equipment " \
             "Financial assets Current assets Inventories Total assets"
    assert run(doc_text=ind_as, framework="Ind AS")["FSBS-004"].status == "PASS"


def test_profit_and_loss_arithmetic_failures():
    assert run(with_change("Total Expenses", cur="30000.00"))["FSPL-002"].status == "FAIL"
    assert run(with_change("viii. Profit before tax", cur="-30000.00"))["FSPL-003"].status == "FAIL"
    assert run(with_change("x. Profit(Loss) for the year", cur="-30000.00"))["FSPL-004"].status == "FAIL"


def test_eps_with_the_wrong_sign_fails():
    assert run(with_change("- Basic & Diluted", cur="1.80"))["FSPL-005"].status == "FAIL"


def test_reserves_that_do_not_move_by_the_profit_are_reviewed():
    facts = with_change("(b) Reserves and Surplus", prev=-40000)
    result = run(facts)
    assert result["FSX-001"].status == "REVIEW" and "Dividends" in result["FSX-001"].message


def test_blank_udin_fails_and_valid_udin_passes():
    assert run()["FSBS-007"].status == "PASS"
    result = run(doc_text=text(udin=""))
    assert result["FSBS-007"].status == "FAIL" and "UDIN" in result["FSBS-007"].message


def test_a_lone_directors_signature_is_incomplete():
    lone = text().replace("DIN: 09551131", "")
    assert run(doc_text=lone)["FSBS-007"].status == "FAIL"


def test_statement_rules_do_not_run_for_other_document_types():
    result = run(doc_type="invoice")
    assert not any(k.startswith(("FSBS", "FSPL", "FSX")) for k in result)


def test_a_balance_sheet_alone_does_not_trigger_profit_and_loss_rules():
    result = run(facts=BASE_FACTS[:10], doc_text=PAGE1)
    assert not any(k.startswith(("FSPL", "FSX")) for k in result)
    assert result["FSBS-001"].status == "PASS"


def test_facts_without_a_values_list_still_work():
    facts = [{"label": f["label"], "value": f["value"], "source_page": f["source_page"]} for f in BASE_FACTS]
    result = run(facts)
    assert result["FSBS-001"].status == "PASS"
