from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ApplicabilityContext:
    jurisdiction: str
    framework: str
    entity_type: str | None = None
    listed: bool | None = None
    reporting_date: date | None = None


@dataclass(frozen=True)
class RuleMetadata:
    rule_id: str
    regulators: tuple[str, ...]
    frameworks: tuple[str, ...]
    entity_types: tuple[str, ...] = ()
    listed_only: bool | None = None
    effective_from: date | None = None
    effective_to: date | None = None

    def applies_to(self, ctx: ApplicabilityContext) -> bool:
        if ctx.jurisdiction != "IN":
            return False
        if self.frameworks and ctx.framework not in self.frameworks:
            return False
        if self.entity_types and ctx.entity_type and ctx.entity_type not in self.entity_types:
            return False
        if self.listed_only is True and ctx.listed is not True:
            return False
        if ctx.reporting_date:
            if self.effective_from and ctx.reporting_date < self.effective_from:
                return False
            if self.effective_to and ctx.reporting_date > self.effective_to:
                return False
        return True
