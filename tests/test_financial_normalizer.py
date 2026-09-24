from decimal import Decimal

from app.financial_normalizer import normalize_table_rows, parse_amount


def test_parse_amount():
    assert parse_amount("₹1,234.50") == Decimal("1234.50")
    assert parse_amount("(500)") == Decimal("-500")
    assert parse_amount("-") is None


def test_normalize_rows():
    rows = normalize_table_rows(
        [["Cash and cash equivalents", "1,000", "900"], ["", "200"]], 3
    )
    assert len(rows) == 1
    assert rows[0].label == "Cash and cash equivalents"
    assert rows[0].values[0] == Decimal("1000")
    assert rows[0].source_page == 3
