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
