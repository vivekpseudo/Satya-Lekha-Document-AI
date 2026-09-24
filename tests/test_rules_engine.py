from app.rules_engine import ComplianceRulesEngine, RegulationEvidence, RuleContext


def test_balance_sheet_pass():
    facts = [
        {"label": "Total Assets", "value": "1500", "source_page": 1},
        {"label": "Total Liabilities", "value": "900", "source_page": 1},
        {"label": "Total Equity", "value": "600", "source_page": 1},
    ]
    evidence = RegulationEvidence(
        regulation_id="TEST-001",
        title="Test source",
        text="Authoritative test evidence.",
        source_uri="https://example.com/test",
        effective_from="2020-01-01",
        effective_to=None,
        similarity=0.91,
    )
    findings = ComplianceRulesEngine().evaluate(
        RuleContext(document_type="balance_sheet", facts=facts),
        regulation_provider=lambda rule_id, ctx: [evidence],
    )
    assert findings[0].rule_id == "INDAS-FS-001"
    assert findings[0].status == "PASS"
    assert findings[0].regulatory_evidence[0]["regulation_id"] == "TEST-001"


def test_balance_sheet_review_when_totals_missing():
    findings = ComplianceRulesEngine().evaluate(
        RuleContext(
            document_type="balance_sheet",
            facts=[{"label": "Total Assets", "value": "1500", "source_page": 1}],
        )
    )
    assert findings[0].status == "REVIEW"
