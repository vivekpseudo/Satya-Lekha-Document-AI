export type Status = "PASS" | "FAIL" | "REVIEW";

export type EvidenceBox = {
  page: number;
  label?: string;
  value?: string | number;
  source_page?: number;
  bbox?: { x: number; y: number; width: number; height: number };
  boundingPoly?: { normalizedVertices?: Array<{ x?: number; y?: number }> };
};

export type Finding = {
  rule_id: string;
  status: Status;
  severity: "HIGH" | "MEDIUM" | "LOW" | string;
  title: string;
  message: string;
  confidence: number;
  evidence: EvidenceBox[];
  regulatory_evidence?: Array<{
    regulation_id?: string;
    title?: string;
    text?: string;
    source_uri?: string;
    effective_from?: string;
    effective_to?: string;
    similarity?: number;
  }>;
};

export type DocumentPage = {
  pageNumber: number;
  imageUrl?: string;
  width?: number;
  height?: number;
};

export type ProcessedDocument = {
  document_id?: string;
  document_name: string;
  document_url?: string;
  classification: {
    document_type: string;
    confidence: number;
  };
  reporting_date?: string;
  framework?: string;
  entity_type?: string;
  pages: DocumentPage[];
  facts: Record<string, unknown>[];
  findings: Finding[];
};
