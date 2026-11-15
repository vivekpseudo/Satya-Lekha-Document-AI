from types import SimpleNamespace as NS

from app.normalizer import normalize_document


def text_block(t):
    return NS(text_block=NS(text=t, blocks=[]), table_block=None, list_block=None,
              page_span=NS(page_start=1))


def cell(t):
    return NS(blocks=[text_block(t)])


def test_layout_parser_output_is_normalized():
    table = NS(
        text_block=None, list_block=None, page_span=NS(page_start=1),
        table_block=NS(
            header_rows=[NS(cells=[cell("Particulars"), cell("2024")])],
            body_rows=[NS(cells=[cell("Total assets"), cell("1,000")])],
        ),
    )
    doc = NS(text="", mime_type="application/pdf", entities=[], pages=[],
             document_layout=NS(blocks=[text_block("Balance Sheet"), table]))
    out = normalize_document(doc)
    assert "Balance Sheet" in out["text"]
    rows = out["pages"][0]["tables"][0]["body_rows"]
    assert rows[0][0]["text"] == "Total assets" and rows[0][1]["text"] == "1,000"
