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


# Narrative-document rules (Companies Act, 2013): Board's Report and Auditor's Report.
# They apply whatever the accounting framework, so "Other" is included.
for _rule_id in (
    *(f"DIRREP-{n:03d}" for n in range(1, 12)),
    *(f"AUDREP-{n:03d}" for n in range(1, 10)),
):
    RULE_REGISTRY[_rule_id] = RuleMetadata(
        rule_id=_rule_id, regulators=("MCA",), frameworks=("Ind AS", "Other"),
    )


# AGM notice (Companies Act, 2013 / SS-2) and invoice (CGST Rule 46) rules.
for _rule_id in (
    *(f"NOTICE-{n:03d}" for n in range(1, 11)),
    *(f"INV-{n:03d}" for n in range(1, 9)),
):
    RULE_REGISTRY[_rule_id] = RuleMetadata(
        rule_id=_rule_id,
        regulators=("MCA",) if _rule_id.startswith("NOTICE") else ("CBIC",),
        frameworks=("Ind AS", "Other"),
    )


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
