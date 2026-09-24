from pydantic import BaseModel, Field


class ComplianceEvaluateRequest(BaseModel):
    document_type: str
    facts: list[dict]
    jurisdiction: str = "IN"
    framework: str = "Ind AS"
    reporting_date: str | None = None
    retrieve_regulations: bool = True
    regulation_top_k: int = Field(default=3, ge=1, le=10)


class ComplianceFindingResponse(BaseModel):
    rule_id: str
    status: str
    severity: str
    title: str
    message: str
    evidence: list[dict]
    regulatory_evidence: list[dict]
    confidence: float = Field(ge=0, le=1)
