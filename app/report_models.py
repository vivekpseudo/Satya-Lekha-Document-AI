from pydantic import BaseModel


class ComplianceReportRequest(BaseModel):
    company_name: str
    document_name: str
    reporting_date: str | None = None
    classification: dict
    findings: list[dict]
