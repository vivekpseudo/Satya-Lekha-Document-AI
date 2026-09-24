from app.classifier import classify_document


def test_classify_balance_sheet():
    result = classify_document(
        "BALANCE SHEET\nAssets\nLiabilities\nShareholders' Equity"
    )
    assert result.document_type == "balance_sheet"
    assert result.confidence >= 0.8
