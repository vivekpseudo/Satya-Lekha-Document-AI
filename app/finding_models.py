from pydantic import BaseModel, Field


class ComplianceEvaluateRequest(BaseModel):
    document_type: str
    facts: list[dict]
    jurisdiction: str = "IN"
    framework: str = "Ind AS"
    reporting_date: str | None = None
    entity_type: str | None = None
    listed: bool | None = None
    text: str = ""
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


class CrossCheckDocument(BaseModel):
    document_type: str
    document_name: str = ""
    text: str = ""
    facts: list[dict] = Field(default_factory=list)


class CrossCheckRequest(BaseModel):
    documents: list[CrossCheckDocument] = Field(min_length=2, max_length=20)
