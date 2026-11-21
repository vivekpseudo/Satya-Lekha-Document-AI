import copy
import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.classifier import classify_document
from app.financial_normalizer import normalize_table_rows
from app.local_extractor import extract_pdf
from app.rules_engine import ComplianceRulesEngine, RuleContext


def row(label, cur, prev, page=5):
    return {"label": label, "value": str(cur), "values": [str(cur), str(prev)], "source_page": page}


# A consistent cash flow statement (indirect method), current year then prior year.
CASH_FLOW = [
    row("Net Profit before tax", 100000, 80000),
    row("Depreciation", 20000, 18000),
    row("Finance cost", 5000, 6000),
    row("Operating profit before working capital changes", 125000, 104000),
    row("(Increase)/decrease in trade receivables", -10000, 5000),
    row("Increase/(decrease) in trade payables", 8000, -3000),
    row("Cash generated from operations", 123000, 106000),
    row("Less: Income tax paid", -25000, -20000),
    row("Net cash flow from operating activities (A)", 98000, 86000),
    row("Purchase of fixed assets", -60000, -30000),
    row("Net cash used in investing activities (B)", -60000, -30000),
    row("Proceeds from borrowings", 20000, 10000),
    row("Finance cost paid", -5000, -6000),
    row("Net cash from financing activities (C)", 15000, 4000),
    row("Net increase/(decrease) in cash and cash equivalents (A+B+C)", 53000, 60000),
    row("Cash and cash equivalents at the beginning of the year", 80000, 20000),
    row("Cash and cash equivalents at the end of the year", 133000, 80000),
]
BALANCE_SHEET = [
    row("TOTAL", 500000, 450000, 1),
    row("(c ) Cash and cash equivalents", 133000, 80000, 1),
    row("TOTAL", 500000, 450000, 1),
]
PROFIT_AND_LOSS = [
    row("Depreciation", 20000, 18000, 2),
    row("Finance Cost", 5000, 6000, 2),
    row("Total Expenses", 80000, 70000, 2),
    row("viii. Profit before tax", 100000, 80000, 2),
]
TEXT = "STATEMENT OF CASH FLOWS Cash flows from operating activities investing activities financing activities"


def run(facts, text=TEXT, doc_type="cash_flow"):
    ctx = RuleContext(document_type=doc_type, facts=facts, text=text, framework="Other")
    return {f.rule_id: f for f in ComplianceRulesEngine().evaluate(ctx) if f.rule_id.startswith("CFS")}


def changed(label, *, cur=None, prev=None, base=None):
    facts = copy.deepcopy(base if base is not None else CASH_FLOW)
    f = next(x for x in facts if x["label"].startswith(label))
    if cur is not None:
        f["value"], f["values"][0] = str(cur), str(cur)
    if prev is not None:
        f["values"][1] = str(prev)
    return facts


def test_consistent_cash_flow_passes_every_rule():
    result = run(CASH_FLOW)
    assert set(result) == {f"CFS-00{n}" for n in (1, 2, 3, 4, 5, 6)}
    assert {f.status for f in result.values()} == {"PASS"}, {k: f.message for k, f in result.items() if f.status != "PASS"}


def test_full_set_of_statements_ties_everything_together():
    result = run(BALANCE_SHEET + PROFIT_AND_LOSS + CASH_FLOW, doc_type="balance_sheet")
    assert set(result) == {f"CFS-00{n}" for n in range(1, 10)}
    assert {f.status for f in result.values()} == {"PASS"}, {k: f.message for k, f in result.items() if f.status != "PASS"}


def test_operating_chain_breaks_are_caught_at_the_step_that_fails():
    assert run(changed("Operating profit before", cur=130000))["CFS-002"].status == "FAIL"
    assert run(changed("Cash generated from operations", cur=120000))["CFS-002"].status == "FAIL"
    result = run(changed("Net cash flow from operating", prev=90000))
    assert result["CFS-002"].status == "FAIL" and "prior year" in result["CFS-002"].message


def test_tax_shown_as_a_positive_deduction_is_accepted():
    facts = changed("Less: Income tax paid", cur=25000, prev=20000)
    assert run(facts)["CFS-002"].status == "PASS"


def test_investing_and_financing_lines_must_add_up():
    assert run(changed("Net cash used in investing", cur=-50000))["CFS-003"].status == "FAIL"
    assert run(changed("Net cash from financing", prev=9000))["CFS-003"].status == "FAIL"


def test_net_change_must_equal_a_plus_b_plus_c():
    result = run(changed("Net increase/(decrease)", cur=50000))
    assert result["CFS-004"].status == "FAIL" and "operating + investing + financing" in result["CFS-004"].message


def test_opening_plus_net_change_must_equal_closing():
    assert run(changed("Cash and cash equivalents at the end", cur=140000))["CFS-005"].status == "FAIL"


def test_negative_closing_cash_is_flagged():
    facts = changed("Cash and cash equivalents at the end", prev=-500)
    facts = changed("Cash and cash equivalents at the beginning", prev=-60500, base=facts)
    assert run(facts)["CFS-005"].status == "FAIL"


def test_opening_must_equal_prior_year_closing():
    result = run(changed("Cash and cash equivalents at the beginning", cur=75000))
    assert result["CFS-006"].status == "FAIL" and "75,000.00" in result["CFS-006"].message


def test_closing_cash_must_agree_with_the_balance_sheet():
    bs = copy.deepcopy(BALANCE_SHEET)
    bs[1]["value"], bs[1]["values"][0] = "130000", "130000"
    result = run(bs + PROFIT_AND_LOSS + CASH_FLOW, doc_type="balance_sheet")
    assert result["CFS-007"].status == "FAIL" and "130,000.00" in result["CFS-007"].message


def test_profit_depreciation_and_finance_cost_must_agree_with_the_pl():
    pl = copy.deepcopy(PROFIT_AND_LOSS)
    pl[3]["values"][0] = "90000"
    result = run(BALANCE_SHEET + pl + CASH_FLOW, doc_type="balance_sheet")
    assert result["CFS-008"].status == "FAIL" and "profit before tax" in result["CFS-008"].message


def test_missing_parts_are_reported():
    facts = [f for f in CASH_FLOW if not f["label"].startswith(("Cash and cash equivalents at the end", "Net increase"))]
    result = run(facts)
    assert result["CFS-001"].status == "REVIEW" and "closing" in result["CFS-001"].message


def test_a_cash_flow_document_with_no_recognisable_totals_fails_the_structure_check():
    result = run([row("Something else", 1, 2)])
    assert result["CFS-001"].status == "FAIL"


def test_missing_cash_flow_statement_is_flagged_only_for_a_full_set_of_statements():
    result = run(BALANCE_SHEET + PROFIT_AND_LOSS, text="BALANCE SHEET PROFIT AND LOSS", doc_type="balance_sheet")
    assert result["CFS-009"].status == "REVIEW" and "s.2(40)" in result["CFS-009"].message
    assert "CFS-009" not in run(BALANCE_SHEET, text="BALANCE SHEET", doc_type="balance_sheet")


def test_rules_do_not_run_on_other_document_types():
    assert run(CASH_FLOW, doc_type="invoice") == {}


def test_cash_flow_rules_do_not_fire_on_an_ordinary_balance_sheet():
    assert run(BALANCE_SHEET + PROFIT_AND_LOSS, text="BALANCE SHEET", doc_type="balance_sheet").keys() <= {"CFS-009"}


# ---------------------------------------------------------------------------- end to end

def _cash_flow_pdf() -> bytes:
    lines = [
        ("Net Profit before tax", "100,000", "80,000"),
        ("Depreciation", "20,000", "18,000"),
        ("Finance cost", "5,000", "6,000"),
        ("Operating profit before working capital changes", "125,000", "104,000"),
        ("(Increase)/decrease in trade receivables", "(10,000)", "5,000"),
        ("Increase/(decrease) in trade payables", "8,000", "(3,000)"),
        ("Cash generated from operations", "123,000", "106,000"),
        ("Less: Income tax paid", "(25,000)", "(20,000)"),
        ("Net cash flow from operating activities (A)", "98,000", "86,000"),
        ("Purchase of fixed assets", "(60,000)", "(30,000)"),
        ("Net cash used in investing activities (B)", "(60,000)", "(30,000)"),
        ("Proceeds from borrowings", "20,000", "10,000"),
        ("Finance cost paid", "(5,000)", "(6,000)"),
        ("Net cash from financing activities (C)", "15,000", "4,000"),
        ("Net increase/(decrease) in cash and cash equivalents (A+B+C)", "53,000", "60,000"),
        ("Cash and cash equivalents at the beginning of the year", "80,000", "20,000"),
        ("Cash and cash equivalents at the end of the year", "133,000", "80,000"),
    ]
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 9)
    c.drawString(50, 800, "ABC PRIVATE LIMITED")
    c.drawString(50, 786, "CASH FLOW STATEMENT FOR THE YEAR ENDED 31ST MARCH, 2024")
    c.drawString(50, 772, "(Amount in Rs.)   Particulars   2023-24   2022-23")
    y = 750
    for label, cur, prev in lines:
        c.drawString(50, y, label)
        c.drawRightString(440, y, cur)
        c.drawRightString(520, y, prev)
        y -= 16
    c.save()
    return buf.getvalue()


def test_a_generated_cash_flow_pdf_passes_the_rules_end_to_end():
    extracted = extract_pdf(_cash_flow_pdf())
    assert classify_document(extracted["text"]).document_type == "cash_flow"
    facts = []
    for page in extracted["pages"]:
        for table in page["tables"]:
            for r in normalize_table_rows(table["body_rows"], page["page_number"]):
                vals = [str(v) if v is not None else None for v in r.values]
                value = next((v for v in vals if v is not None), None)
                if value is not None:
                    facts.append({"label": r.label, "value": value, "values": vals, "source_page": r.source_page})
    result = run(facts, text=extracted["text"])
    assert {f.status for f in result.values()} == {"PASS"}, {k: f.message for k, f in result.items() if f.status != "PASS"}
    assert len(result) == 6
