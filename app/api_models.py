from pydantic import BaseModel, Field


class RegulationIn(BaseModel):
    regulation_id: str
    title: str
    content: str
    source_uri: str
    effective_from: str | None = None
    effective_to: str | None = None


class RegulationSearchIn(BaseModel):
    query: str = Field(min_length=3)
    top_k: int = Field(default=5, ge=1, le=20)
