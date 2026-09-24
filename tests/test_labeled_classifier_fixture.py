LABELED_DOCUMENTS = [
    {
        "id": "synthetic-bs-001",
        "label": "balance_sheet",
        "text": "Balance Sheet\nAssets\nLiabilities\nShareholders' Equity",
    },
    {
        "id": "synthetic-pl-001",
        "label": "profit_and_loss",
        "text": "Statement of Profit and Loss\nRevenue\nProfit before tax",
    },
    {
        "id": "synthetic-cf-001",
        "label": "cash_flow",
        "text": "Cash Flow Statement\nOperating Activities\nCash and cash equivalents",
    },
    {
        "id": "synthetic-notes-001",
        "label": "notes_to_accounts",
        "text": "Notes to the Financial Statements\nAccounting policies",
    },
]


def test_fixture_shape():
    assert len(LABELED_DOCUMENTS) == 4
    assert {row["label"] for row in LABELED_DOCUMENTS} == {
        "balance_sheet",
        "profit_and_loss",
        "cash_flow",
        "notes_to_accounts",
    }
