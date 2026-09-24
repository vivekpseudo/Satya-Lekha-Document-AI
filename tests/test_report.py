from pathlib import Path

from app.report import build_compliance_report


def test_build_report(tmp_path: Path):
    output = tmp_path / "report.pdf"
    result = build_compliance_report(
        str(output),
        company_name="Test Ltd",
        document_name="annual-report.pdf",
        reporting_date="2025-03-31",
        classification={"document_type": "balance_sheet", "confidence": 0.91},
        findings=[{
            "rule_id": "TEST-001",
            "status": "PASS",
            "severity": "LOW",
            "title": "Test finding",
            "message": "Test message",
            "evidence": [{"label": "Total Assets", "source_page": 1, "value": "100"}],
            "regulatory_evidence": [],
            "confidence": 0.95
        }],
    )
    assert output.exists()
    assert result.endswith(".pdf")
    assert output.stat().st_size > 1000
