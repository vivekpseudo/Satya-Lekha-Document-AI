import type { Finding, ProcessedDocument, ReportDetail, ReportSummary, Session, User } from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

const TOKEN_KEY = "satya-lekha-token";

export function getToken(): string | null {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}
export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch { /* storage unavailable: the user just signs in again next visit */ }
}

/** Set by the auth provider: called when the API says the saved sign-in is no longer valid. */
let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(handler: () => void) { onUnauthorized = handler; }

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// FastAPI reports errors as {"detail": "..."} or {"detail": [{"msg": "..."}]}; show just the sentence.
async function errorMessage(response: Response): Promise<string> {
  const text = await response.text();
  try {
    const detail = JSON.parse(text).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
  } catch { /* not JSON */ }
  return text || `API request failed: ${response.status}`;
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) throw new Error(await errorMessage(response));
  return response.json() as Promise<T>;
}

async function authed<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...(init.headers as Record<string, string>), ...authHeaders() },
  });
  if (response.status === 401) onUnauthorized();
  return parseResponse<T>(response);
}

export async function register(input: {
  email: string; password: string; full_name: string; organization: string; accepted_terms: boolean;
}): Promise<Session> {
  const response = await fetch(`${API_BASE}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return parseResponse<Session>(response);
}

export async function login(email: string, password: string): Promise<Session> {
  const response = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return parseResponse<Session>(response);
}

export const fetchMe = () => authed<User>("/api/v1/auth/me");

export function saveReport(document: ProcessedDocument): Promise<ReportSummary> {
  return authed<ReportSummary>("/api/v1/reports", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      document_name: document.document_name,
      reporting_date: document.reporting_date,
      classification: document.classification,
      findings: document.findings,
    }),
  });
}

export const listReports = () => authed<ReportSummary[]>("/api/v1/reports");
export const getReport = (id: number) => authed<ReportDetail>(`/api/v1/reports/${id}`);

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
  input: Pick<ProcessedDocument, "classification" | "facts" | "reporting_date" | "text"> & {
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
      text: input.text ?? "",
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

/** Compare several documents of one filing (reports, statements, notice) with each other. */
export async function crossCheckDocuments(documents: ProcessedDocument[]): Promise<Finding[]> {
  const response = await fetch(`${API_BASE}/api/v1/compliance/cross-check`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      documents: documents.map((doc) => ({
        document_type: doc.classification.document_type,
        document_name: doc.document_name,
        text: doc.text ?? "",
        facts: doc.facts,
      })),
    }),
  });
  return parseResponse<Finding[]>(response);
}

export async function downloadComplianceReport(
  document: Pick<ProcessedDocument, "document_name" | "reporting_date" | "classification" | "findings">,
  companyName = "Satya-Lekha Client",
): Promise<Blob> {
  const response = await fetch(`${API_BASE}/api/v1/compliance/report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      company_name: companyName,
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
