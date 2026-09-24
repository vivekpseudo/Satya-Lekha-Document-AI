from app.rules_engine import ComplianceRulesEngine, RuleContext


def test_balance_sheet_pass():
    facts = [
        {"label": "Total Assets", "value": "1500", "source_page": 1},
        {"label": "Total Liabilities", "value": "900", "source_page": 1},
        {"label": "Total Equity", "value": "600", "source_page": 1},
    ]
    findings = ComplianceRulesEngine().evaluate(
        RuleContext(document_type="balance_sheet", facts=facts)
    )
    assert findings[0].rule_id == "INDAS-FS-001"
    assert findings[0].status == "PASS"


def test_balance_sheet_review_when_totals_missing():
    findings = ComplianceRulesEngine().evaluate(
        RuleContext(
            document_type="balance_sheet",
            facts=[{"label": "Total Assets", "value": "1500", "source_page": 1}],
        )
    )
    assert findings[0].status == "REVIEW"
