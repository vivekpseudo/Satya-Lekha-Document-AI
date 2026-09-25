import type { Finding, ProcessedDocument } from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `API request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function processDocument(file: File): Promise<ProcessedDocument> {
  const body = new FormData();
  body.append("file", file);

  const response = await fetch(`${API_BASE}/api/v1/documents/process-and-store`, {
    method: "POST",
    body,
  });
  return parseResponse<ProcessedDocument>(response);
}

export async function evaluateCompliance(
  input: Pick<ProcessedDocument, "classification" | "facts" | "reporting_date"> & {
    framework?: string;
    entity_type?: string;
    listed?: boolean;
  },
): Promise<Finding[]> {
  const response = await fetch(`${API_BASE}/api/v1/compliance/evaluate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      document_type: input.classification.document_type,
      facts: input.facts,
      reporting_date: input.reporting_date,
      framework: input.framework || "Ind AS",
      entity_type: input.entity_type,
      listed: input.listed,
      retrieve_regulations: true,
      regulation_top_k: 3,
    }),
  });
  return parseResponse<Finding[]>(response);
}

export async function downloadComplianceReport(
  document: ProcessedDocument,
): Promise<Blob> {
  const response = await fetch(`${API_BASE}/api/v1/compliance/report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      company_name: "Satya-Lekha Client",
      document_name: document.document_name,
      reporting_date: document.reporting_date,
      classification: document.classification,
      findings: document.findings,
    }),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.blob();
}

export function apiBaseUrl() {
  return API_BASE;
}
