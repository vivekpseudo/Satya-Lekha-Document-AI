from app.classifier import classify_document


def test_classify_balance_sheet():
    result = classify_document(
        "BALANCE SHEET\nAssets\nLiabilities\nShareholders' Equity"
    )
    assert result.document_type == "balance_sheet"
    assert result.confidence >= 0.8


def test_classify_profit_and_loss():
    result = classify_document(
        "Statement of Profit and Loss\nRevenue\nProfit before tax"
    )
    assert result.document_type == "profit_and_loss"


def test_directors_report_mentioning_balance_sheet_is_not_a_balance_sheet():
    text = (
        "ABC Private Limited CIN U12345 DIRECTORS' REPORT To The Members, "
        "Your Directors have pleasure in presenting their Annual Report. "
        "The Balance Sheet and total assets are annexed. Directors' Responsibility Statement."
    )
    assert classify_document(text).document_type == "directors_report"


def test_auditors_report_with_font_spacing_artifacts():
    text = (
        "MISHRA N & Co. CHARTERED ACCOUNTANTS TO THE MEMBE RS OF ABC PV T LTD "
        "Report on the Au dit of t he Financial Statem ents Opinion We have audited "
        "the financ ial statements ... Basis for Opinion ... Balance Sheet ... Key Audit Matters"
    )
    assert classify_document(text).document_type == "auditors_report"


def test_agm_notice():
    text = (
        "NOTICE No tice is hereby given that the Annual General Me eting of the Company "
        "will be held ... Ordinary Business: adopt the audited Balance Sheet"
    )
    assert classify_document(text).document_type == "agm_notice"


def test_invoice():
    text = "Invoice No. BILL/133 Dated 3-Apr-24 INVOICE Party : ABC Pvt Ltd HSN/SAC 9983 Amount Chargeable"
    assert classify_document(text).document_type == "invoice"


def test_unrecognised_text_is_other():
    assert classify_document("Lorem ipsum dolor sit amet").document_type == "other"
