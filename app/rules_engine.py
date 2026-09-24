from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Any


@dataclass(frozen=True)
class RuleContext:
    document_type: str
    facts: list[dict[str, Any]]
    jurisdiction: str = "IN"
    framework: str = "Ind AS"
    reporting_date: str | None = None


@dataclass(frozen=True)
class ComplianceFinding:
    rule_id: str
    status: str
    severity: str
    title: str
    message: str
    evidence: list[dict[str, Any]]
    confidence: float


@dataclass(frozen=True)
class ComplianceRule:
    rule_id: str
    title: str
    statement_types: set[str]
    evaluator: Callable[[RuleContext], ComplianceFinding | None]


def _find_facts(ctx: RuleContext, *keywords: str) -> list[dict[str, Any]]:
    matches = []
    for fact in ctx.facts:
        label = str(fact.get("label", "")).lower()
        if any(keyword.lower() in label for keyword in keywords):
            matches.append(fact)
    return matches


def rule_balance_sheet_basic(ctx: RuleContext) -> ComplianceFinding | None:
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
            confidence=0.78,
        )

    a = Decimal(str(asset[0]["value"]))
    l = Decimal(str(liabilities[0]["value"]))
    e = Decimal(str(equity[0]["value"]))
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
        confidence=0.96,
    )


def rule_negative_revenue(ctx: RuleContext) -> ComplianceFinding | None:
    revenue = _find_facts(ctx, "revenue", "turnover", "sales")
    if not revenue:
        return None

    negative = [fact for fact in revenue if Decimal(str(fact["value"])) < 0]
    if not negative:
        return ComplianceFinding(
            rule_id="DATA-QUALITY-001",
            status="PASS",
            severity="LOW",
            title="Revenue sign check",
            message="No extracted revenue fact is negative.",
            evidence=revenue,
            confidence=0.92,
        )

    return ComplianceFinding(
        rule_id="DATA-QUALITY-001",
        status="REVIEW",
        severity="MEDIUM",
        title="Negative revenue extracted",
        message="A negative revenue value was extracted. This may be valid in some contexts, but requires source-document review.",
        evidence=negative,
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

    def evaluate(self, context: RuleContext) -> list[ComplianceFinding]:
        findings = []
        for rule in self.rules:
            if context.document_type not in rule.statement_types and "other" not in rule.statement_types:
                continue
            finding = rule.evaluator(context)
            if finding is not None:
                findings.append(finding)
        return findings
