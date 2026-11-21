import glob
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def payload(company: str) -> dict:
    return {
        "company_name": company,
        "document_name": "schedule.pdf",
        "reporting_date": "2024-03-31",
        "classification": {"document_type": "balance_sheet", "confidence": 0.9},
        "findings": [{"rule_id": "FSBS-001", "status": "PASS", "severity": "LOW", "title": "Balances",
                      "message": "ok", "evidence": [], "regulatory_evidence": [], "confidence": 0.9}],
    }


def leftovers() -> set[str]:
    return set(glob.glob(os.path.join(tempfile.gettempdir(), "satya_lekha_report_*.pdf")))


def test_report_is_a_pdf_and_leaves_no_temporary_file_behind():
    before = leftovers()
    response = client.post("/api/v1/compliance/report", json=payload("Acme Ltd"))
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert leftovers() == before


def test_simultaneous_exports_and_prints_do_not_overwrite_each_other():
    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(pool.map(lambda i: client.post("/api/v1/compliance/report", json=payload(f"Company {i}")),
                                  range(6)))
    assert all(r.status_code == 200 and r.content.startswith(b"%PDF") for r in responses)
    assert all(r.content.rstrip().endswith(b"%%EOF") for r in responses)  # none was cut off mid-write
