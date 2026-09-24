from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Callable


@dataclass(frozen=True)
class RuleContext:
    document_type: str
    facts: list[dict[str, Any]]
    jurisdiction: str = "IN"
    framework: str = "Ind AS"
    reporting_date: str | None = None


@dataclass(frozen=True)
class RegulationEvidence:
    regulation_id: str
    title: str
    text: str
    source_uri: str
    effective_from: str | None = None
    effective_to: str | None = None
    similarity: float | None = None


@dataclass(frozen=True)
class ComplianceFinding:
    rule_id: str
    status: str
    severity: str
    title: str
    message: str
    evidence: list[dict[str, Any]]
    regulatory_evidence: list[dict[str, Any]]
    confidence: float


@dataclass(frozen=True)
class ComplianceRule:
    rule_id: str
    title: str
    statement_types: set[str]
    evaluator: Callable[[RuleContext, list[RegulationEvidence]], ComplianceFinding | None]


def _find_facts(ctx: RuleContext, *keywords: str) -> list[dict[str, Any]]:
    return [
        fact for fact in ctx.facts
        if any(keyword.lower() in str(fact.get("label", "")).lower() for keyword in keywords)
    ]


def _money(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _reg_evidence(rows: list[RegulationEvidence]) -> list[dict[str, Any]]:
    return [
        {
            "regulation_id": row.regulation_id,
            "title": row.title,
            "text": row.text,
            "source_uri": row.source_uri,
            "effective_from": row.effective_from,
            "effective_to": row.effective_to,
            "similarity": row.similarity,
        }
        for row in rows
    ]


def rule_balance_sheet_basic(
    ctx: RuleContext, regulations: list[RegulationEvidence]
) -> ComplianceFinding | None:
    if ctx.document_type != "balance_sheet":
        return None

    asset = _find_facts(ctx, "total assets")
    liabilities = _find_facts(ctx, "total liabilities")
    equity = _find_facts(ctx, "total equity")

    if not (asset and liabilities and equity):
        return ComplianceFinding(
            rule_id="INDAS-FS-001",
            status="REVIEW",
            severity="MEDIUM",
            title="Balance-sheet totals not fully identified",
            message="The extracted document does not contain all three expected totals with recognized labels.",
            evidence=asset + liabilities + equity,
            regulatory_evidence=_reg_evidence(regulations),
            confidence=0.78,
        )

    a = _money(asset[0].get("value"))
    l = _money(liabilities[0].get("value"))
    e = _money(equity[0].get("value"))
    if None in (a, l, e):
        return ComplianceFinding(
            rule_id="INDAS-FS-001",
            status="REVIEW",
            severity="MEDIUM",
            title="Balance-sheet values could not be validated",
            message="One or more extracted totals are not numeric.",
            evidence=asset + liabilities + equity,
            regulatory_evidence=_reg_evidence(regulations),
            confidence=0.70,
        )

    difference = a - (l + e)
    status = "PASS" if abs(difference) <= Decimal("0.01") else "FAIL"
    severity = "LOW" if status == "PASS" else "HIGH"
    message = (
        "Assets equal liabilities plus equity within the configured tolerance."
        if status == "PASS"
        else f"Balance-sheet equation differs by {difference}."
    )

    return ComplianceFinding(
        rule_id="INDAS-FS-001",
        status=status,
        severity=severity,
        title="Balance-sheet equation check",
        message=message,
        evidence=asset + liabilities + equity,
        regulatory_evidence=_reg_evidence(regulations),
        confidence=0.96,
    )


def rule_negative_revenue(
    ctx: RuleContext, regulations: list[RegulationEvidence]
) -> ComplianceFinding | None:
    revenue = _find_facts(ctx, "revenue", "turnover", "sales")
    if not revenue:
        return None

    numeric = [(fact, _money(fact.get("value"))) for fact in revenue]
    negative = [fact for fact, value in numeric if value is not None and value < 0]
    if not negative:
        return ComplianceFinding(
            rule_id="DATA-QUALITY-001",
            status="PASS",
            severity="LOW",
            title="Revenue sign check",
            message="No extracted revenue fact is negative.",
            evidence=revenue,
            regulatory_evidence=_reg_evidence(regulations),
            confidence=0.92,
        )

    return ComplianceFinding(
        rule_id="DATA-QUALITY-001",
        status="REVIEW",
        severity="MEDIUM",
        title="Negative revenue extracted",
        message="A negative revenue value was extracted. This is a data-quality review signal, not by itself a regulatory breach.",
        evidence=negative,
        regulatory_evidence=_reg_evidence(regulations),
        confidence=0.90,
    )


DEFAULT_RULES = [
    ComplianceRule(
        rule_id="INDAS-FS-001",
        title="Balance-sheet equation check",
        statement_types={"balance_sheet"},
        evaluator=rule_balance_sheet_basic,
    ),
    ComplianceRule(
        rule_id="DATA-QUALITY-001",
        title="Revenue sign check",
        statement_types={"profit_and_loss", "other"},
        evaluator=rule_negative_revenue,
    ),
]


class ComplianceRulesEngine:
    def __init__(self, rules: list[ComplianceRule] | None = None):
        self.rules = rules or DEFAULT_RULES

    def evaluate(
        self,
        context: RuleContext,
        regulation_provider: Callable[[str, RuleContext], list[RegulationEvidence]] | None = None,
    ) -> list[ComplianceFinding]:
        findings = []
        for rule in self.rules:
            if context.document_type not in rule.statement_types:
                continue
            regulations = (
                regulation_provider(rule.rule_id, context)
                if regulation_provider
                else []
            )
            finding = rule.evaluator(context, regulations)
            if finding:
                findings.append(finding)
        return findings
