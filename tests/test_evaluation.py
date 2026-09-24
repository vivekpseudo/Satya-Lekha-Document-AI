from app.evaluation import evaluate_texts


def test_evaluation():
    result = evaluate_texts([
        {"label": "balance_sheet", "text": "Balance Sheet Assets Liabilities Equity"},
        {"label": "profit_and_loss", "text": "Statement of Profit and Loss Revenue Profit before tax"},
    ])
    assert result["total"] == 2
    assert result["accuracy"] == 1.0
