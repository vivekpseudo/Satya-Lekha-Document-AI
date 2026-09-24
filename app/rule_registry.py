from datetime import date

from app.applicability import RuleMetadata


RULE_REGISTRY = {
    "INDAS-FS-001": RuleMetadata(
        rule_id="INDAS-FS-001",
        regulators=("MCA",),
        frameworks=("Ind AS",),
    ),
    "DATA-QUALITY-001": RuleMetadata(
        rule_id="DATA-QUALITY-001",
        regulators=(),
        frameworks=("Ind AS", "Other"),
    ),
}


def get_rule_metadata(rule_id: str) -> RuleMetadata | None:
    return RULE_REGISTRY.get(rule_id)


def active_rule_ids(
    *,
    jurisdiction: str,
    framework: str,
    entity_type: str | None,
    listed: bool | None,
    reporting_date: date | None,
) -> set[str]:
    from app.applicability import ApplicabilityContext

    ctx = ApplicabilityContext(
        jurisdiction=jurisdiction,
        framework=framework,
        entity_type=entity_type,
        listed=listed,
        reporting_date=reporting_date,
    )
    return {
        rule_id
        for rule_id, metadata in RULE_REGISTRY.items()
        if metadata.applies_to(ctx)
    }
