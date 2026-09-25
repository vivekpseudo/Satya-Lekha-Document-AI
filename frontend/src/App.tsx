import { useEffect, useMemo, useRef, useState } from "react";
import {
  AuditOutlined,
  CheckCircleFilled,
  CheckOutlined,
  CloudUploadOutlined,
  DownloadOutlined,
  FilePdfOutlined,
  InfoCircleOutlined,
  MenuOutlined,
  PlayCircleFilled,
  PrinterOutlined,
  SafetyCertificateOutlined,
  LeftOutlined,
  RightOutlined,
  WarningFilled,
  ExclamationCircleFilled,
} from "@ant-design/icons";
import { Button, Dropdown, Progress, Tag, Upload, message } from "antd";
import type { UploadProps } from "antd";
import { getDocument, GlobalWorkerOptions, type PDFDocumentProxy } from "pdfjs-dist";
import { downloadComplianceReport, evaluateCompliance, processDocument } from "./api";
import type { EvidenceBox, Finding, ProcessedDocument, Status } from "./types";

GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

const demo: ProcessedDocument = {
  document_name: "Acme Global Holdings — Annual Report FY2025",
  document_url: "",
  reporting_date: "2025-03-31",
  framework: "Ind AS",
  classification: { document_type: "balance_sheet", confidence: 0.94 },
  pages: [
    { pageNumber: 1 },
    { pageNumber: 2 },
    { pageNumber: 3 },
    { pageNumber: 4 },
  ],
  facts: [
    { label: "Total Assets", value: "137300", source_page: 1 },
    { label: "Total Liabilities", value: "90000", source_page: 1 },
    { label: "Total Equity", value: "47300", source_page: 1 },
  ],
  findings: [
    {
      rule_id: "INDAS-FS-001",
      status: "FAIL",
      severity: "HIGH",
      title: "Balance-sheet equation variance",
      message: "Total assets do not reconcile to total liabilities plus equity within the configured tolerance.",
      confidence: 0.96,
      evidence: [
        { page: 1, label: "Total Assets", value: "₹137,300", bbox: { x: .18, y: .66, width: .52, height: .055 } },
        { page: 1, label: "Total Liabilities", value: "₹90,000", bbox: { x: .18, y: .74, width: .52, height: .055 } },
        { page: 1, label: "Total Equity", value: "₹47,300", bbox: { x: .18, y: .82, width: .52, height: .055 } },
      ],
      regulatory_evidence: [],
    },
    {
      rule_id: "DISC-002",
      status: "REVIEW",
      severity: "MEDIUM",
      title: "Retained earnings roll-forward",
      message: "Opening retained earnings, current-year profit and dividends require source-note verification.",
      confidence: 0.82,
      evidence: [
        { page: 3, label: "Retained earnings", value: "₹137,300", bbox: { x: .13, y: .38, width: .68, height: .06 } },
      ],
      regulatory_evidence: [],
    },
    {
      rule_id: "DATA-QUALITY-001",
      status: "PASS",
      severity: "LOW",
      title: "Revenue sign check",
      message: "No negative revenue value was detected in the extracted statement facts.",
      confidence: 0.92,
      evidence: [{ page: 2, label: "Revenue from operations", value: "₹1,248.60" }],
      regulatory_evidence: [],
    },
  ],
};

const statusMeta: Record<Status, { label: string; className: string }> = {
  PASS: { label: "Verified", className: "status-pass" },
  FAIL: { label: "Critical", className: "status-fail" },
  REVIEW: { label: "Review", className: "status-review" },
};

function normalizeEvidence(evidence: EvidenceBox): EvidenceBox {
  if (evidence.bbox) return evidence;
  const vertices = evidence.boundingPoly?.normalizedVertices || [];
  if (!vertices.length) return evidence;
  const xs = vertices.map((v) => v.x ?? 0);
  const ys = vertices.map((v) => v.y ?? 0);
  return {
    ...evidence,
    bbox: {
      x: Math.min(...xs),
      y: Math.min(...ys),
      width: Math.max(...xs) - Math.min(...xs),
      height: Math.max(...ys) - Math.min(...ys),
    },
  };
}

function scoreFindings(findings: Finding[]) {
  if (!findings.length) return 0;
  const weighted = findings.reduce((sum, item) => {
    if (item.status === "PASS") return sum + 1;
    if (item.status === "REVIEW") return sum + 0.5;
    return sum;
  }, 0);
  return Math.round((weighted / findings.length) * 100);
}

function FindingCard({
  finding,
  onEvidence,
}: {
  finding: Finding;
  onEvidence: (evidence: EvidenceBox) => void;
}) {
  const meta = statusMeta[finding.status];
  return (
    <article className={`finding-card ${meta.className}`}>
      <div className="flex items-start gap-3">
        <div className="finding-icon">
          {finding.status === "FAIL" ? <ExclamationCircleFilled /> :
            finding.status === "REVIEW" ? <WarningFilled /> : <CheckCircleFilled />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <Tag bordered={false} className="status-tag">{meta.label}</Tag>
            <span className="rule-label">{finding.rule_id}</span>
          </div>
          <h3>{finding.title}</h3>
          <p>{finding.message}</p>
          <div className="confidence-line">Rule confidence: {(finding.confidence * 100).toFixed(0)}%</div>

          {finding.evidence.length > 0 && (
            <div className="evidence-list">
              {finding.evidence.map((evidence, index) => (
                <button key={`${finding.rule_id}-${index}`} onClick={() => onEvidence(evidence)}>
                  <span>{evidence.label || "Evidence"}</span>
                  <b>{String(evidence.value ?? "")}</b>
                  <small>Page {evidence.page || evidence.source_page}</small>
                </button>
              ))}
            </div>
          )}

          {finding.regulatory_evidence?.length ? (
            <div className="evidence-box">
              <div className="flex items-center gap-2 font-semibold text-slate-700">
                <InfoCircleOutlined /> Regulatory evidence
              </div>
              {finding.regulatory_evidence.slice(0, 2).map((reg, i) => (
                <div key={i} className="reg-source">
                  <b>{reg.regulation_id || "Source"}</b> — {reg.title}
                  <small>{reg.source_uri}</small>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </article>
  );
}

function PdfJsViewer({
  document,
  page,
  selectedFinding,
  showPins,
  onPin,
}: {
  document: ProcessedDocument;
  page: number;
  selectedFinding?: Finding;
  showPins: boolean;
  onPin: (finding: Finding, evidence: EvidenceBox) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const frameRef = useRef<HTMLDivElement | null>(null);
  const [pdf, setPdf] = useState<PDFDocumentProxy | null>(null);
  const [renderError, setRenderError] = useState<string | null>(null);
  const [viewportSize, setViewportSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    let cancelled = false;
    setRenderError(null);

    const source = document.document_url;
    if (!source || !/\.pdf($|#)/i.test(source)) {
      setPdf(null);
      return;
    }

    const loadingTask = getDocument(source);
    loadingTask.promise
      .then((loaded) => {
        if (!cancelled) setPdf(loaded);
        else void loaded.destroy();
      })
      .catch((error) => {
        if (!cancelled) setRenderError(error instanceof Error ? error.message : "Unable to load PDF");
      });

    return () => {
      cancelled = true;
      void loadingTask.destroy();
    };
  }, [document.document_url]);

  useEffect(() => {
    let cancelled = false;

    async function renderPage() {
      if (!pdf || !canvasRef.current) return;
      try {
        const pdfPage = await pdf.getPage(page);
        const baseViewport = pdfPage.getViewport({ scale: 1 });
        const availableWidth = Math.max(frameRef.current?.clientWidth || 760, 320);
        const scale = Math.min(1.8, availableWidth / baseViewport.width);
        const viewport = pdfPage.getViewport({ scale });
        const canvas = canvasRef.current;
        const context = canvas.getContext("2d");
        if (!context) return;

        canvas.width = Math.ceil(viewport.width);
        canvas.height = Math.ceil(viewport.height);
        canvas.style.width = `${viewport.width}px`;
        canvas.style.height = `${viewport.height}px`;
        setViewportSize({ width: viewport.width, height: viewport.height });

        await pdfPage.render({ canvasContext: context, viewport }).promise;
        if (cancelled) context.clearRect(0, 0, canvas.width, canvas.height);
      } catch (error) {
        if (!cancelled) setRenderError(error instanceof Error ? error.message : "Unable to render PDF page");
      }
    }

    void renderPage();
    return () => { cancelled = true; };
  }, [pdf, page]);

  const pageEvidence = (document.findings || []).flatMap((finding) =>
    finding.evidence.map((raw) => ({ finding, evidence: normalizeEvidence(raw) })),
  ).filter(({ evidence }) => evidence.page === page && evidence.bbox);

  const selectedEvidence = (selectedFinding?.evidence || [])
    .map(normalizeEvidence)
    .filter((evidence) => evidence.page === page && evidence.bbox);

  if (!document.document_url || !/\.pdf($|#)/i.test(document.document_url)) {
    return (
      <div className="paper-viewer">
        <div className="paper">
          <div className="paper-header">
            <div>
              <h1>ACME GLOBAL HOLDINGS PVT. LTD.</h1>
              <h2>CONSOLIDATED BALANCE SHEET</h2>
              <p>As at March 31, 2025 and 2024</p>
              <p>(Amounts in ₹ lakhs)</p>
            </div>
            <div className="exhibit">Page<br /><b>{page}</b><small>Document AI preview</small></div>
          </div>
          <div className="paper-rule" />
          <div className="paper-section">ASSETS</div>
          <div className="paper-subsection">Current Assets</div>
          <table className="statement-table">
            <tbody>
              {[
                ["Cash and cash equivalents", "₹184.50"],
                ["Trade receivables, net", "₹92.40"],
                ["Inventories, net", "₹148.20"],
                ["Prepaid expenses and other current assets", "₹21.90"],
              ].map(([label, value]) => (
                <tr key={label}><td>{label}</td><td>{value}</td><td>₹142.20</td></tr>
              ))}
            </tbody>
          </table>
          {selectedEvidence.map((evidence, i) => (
            <div key={i} className="evidence-highlight mock" style={{
              left: `${evidence.bbox!.x * 100}%`, top: `${evidence.bbox!.y * 100}%`,
              width: `${evidence.bbox!.width * 100}%`, height: `${evidence.bbox!.height * 100}%`,
            }} />
          ))}
          {showPins && selectedEvidence.map((_, i) => (
            <div key={i} className={`audit-pin pin-${i % 2 ? "two" : "one"}`}>{i + 1}</div>
          ))}
        </div>
      </div>
    );
  }

  if (renderError) {
    return <div className="pdf-error">PDF preview unavailable: {renderError}</div>;
  }

  return (
    <div className="pdfjs-stage" ref={frameRef}>
      <div className="pdfjs-page" style={{ width: viewportSize.width || "100%" }}>
        <canvas ref={canvasRef} />
        <div className="pdf-overlay" style={{ width: viewportSize.width, height: viewportSize.height }}>
          {showPins && pageEvidence.map(({ finding, evidence }, index) => {
            const box = evidence.bbox!;
            return (
              <button
                key={`${finding.rule_id}-${index}`}
                className={`real-audit-pin ${finding.status.toLowerCase()}`}
                style={{
                  left: `${(box.x + box.width) * 100}%`,
                  top: `${Math.max(box.y, 0.015) * 100}%`,
                }}
                title={`${finding.title} — ${evidence.label || "Evidence"}`}
                onClick={() => onPin(finding, evidence)}
              >
                {index + 1}
              </button>
            );
          })}
          {selectedEvidence.map((evidence, index) => {
            const box = evidence.bbox!;
            return (
              <div
                key={`highlight-${index}`}
                className="evidence-highlight"
                style={{
                  left: `${box.x * 100}%`,
                  top: `${box.y * 100}%`,
                  width: `${Math.max(box.width, 0.005) * 100}%`,
                  height: `${Math.max(box.height, 0.005) * 100}%`,
                }}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [document, setDocument] = useState<ProcessedDocument>(demo);
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState(demo.findings[0].rule_id);
  const [showPins, setShowPins] = useState(true);
  const [loading, setLoading] = useState(false);
  const [messageApi, contextHolder] = message.useMessage();

  const counts = useMemo(() => ({
    fail: document.findings.filter((x) => x.status === "FAIL").length,
    review: document.findings.filter((x) => x.status === "REVIEW").length,
    pass: document.findings.filter((x) => x.status === "PASS").length,
  }), [document.findings]);

  const score = useMemo(() => scoreFindings(document.findings), [document.findings]);
  const selected = document.findings.find((x) => x.rule_id === selectedId) || document.findings[0];
  const totalPages = Math.max(document.pages.length, 1);

  const runDocument = async (file: File) => {
    setLoading(true);
    try {
      const localUrl = URL.createObjectURL(file);
      const processed = await processDocument(file);
      const findings = await evaluateCompliance(processed);
      setDocument({
        ...processed,
        document_url: processed.document_url || localUrl,
        findings,
        pages: processed.pages.length ? processed.pages : [{ pageNumber: 1 }],
      });
      setPage(1);
      setSelectedId(findings[0]?.rule_id || "");
      messageApi.success("Document processed and compliance evaluation completed.");
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "Processing failed");
    } finally {
      setLoading(false);
    }
  };

  const uploadProps: UploadProps = {
    showUploadList: false,
    accept: ".pdf,.png,.jpg,.jpeg,.tif,.tiff",
    beforeUpload: (file) => {
      void runDocument(file);
      return false;
    },
  };

  const exportPdf = async () => {
    try {
      const blob = await downloadComplianceReport(document);
      const url = URL.createObjectURL(blob);
      const anchor = window.document.createElement("a");
      anchor.href = url;
      anchor.download = "satya_lekha_compliance_report.pdf";
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "PDF export failed");
    }
  };

  const jumpToEvidence = (finding: Finding, evidence: EvidenceBox) => {
    setSelectedId(finding.rule_id);
    setPage(evidence.page || evidence.source_page || 1);
  };

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      {contextHolder}
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark"><SafetyCertificateOutlined /></div>
          <div><div className="brand-name">Satya-Lekha</div><div className="brand-subtitle">AI Compliance Intelligence</div></div>
          <span className="product-badge">Ind AS • SEBI • RBI</span>
        </div>
        <div className="header-actions">
          <Upload {...uploadProps}>
            <Button loading={loading} icon={<CloudUploadOutlined />}>Upload Document</Button>
          </Upload>
          <Button type="primary" loading={loading} icon={<PlayCircleFilled />}>Run Compliance</Button>
          <Dropdown menu={{ items: [{ key: "pdf", icon: <FilePdfOutlined />, label: "Export PDF report", onClick: exportPdf }, { key: "print", icon: <PrinterOutlined />, label: "Print report", onClick: () => window.print() }] }}>
            <Button icon={<DownloadOutlined />} />
          </Dropdown>
          <Button className="mobile-menu" icon={<MenuOutlined />} />
        </div>
      </header>

      <section className="document-strip">
        <div className="document-context">
          <span className="context-dot" />
          <strong>{document.document_name}</strong>
          <i /><span>Framework: {document.framework || "Ind AS"}</span>
          <i /><span>Reporting date: {document.reporting_date || "Not provided"}</span>
        </div>
        <div className="audit-status">
          Compliance Status: <b>{counts.fail + counts.review} Items Require Attention</b>
          <span className="classification-pill">Classified as {document.classification.document_type} • {(document.classification.confidence * 100).toFixed(0)}%</span>
        </div>
      </section>

      <main className="workspace">
        <section className="document-pane">
          <div className="pane-toolbar">
            <div className="toolbar-title"><FilePdfOutlined /> Document Preview <span>Page {page} of {totalPages}</span></div>
            <div className="toolbar-actions">
              <Button size="small" disabled={page <= 1} icon={<LeftOutlined />} onClick={() => setPage((p) => Math.max(1, p - 1))} />
              <span>{page} / {totalPages}</span>
              <Button size="small" disabled={page >= totalPages} icon={<RightOutlined />} onClick={() => setPage((p) => Math.min(totalPages, p + 1))} />
              <Button size="small" type={showPins ? "primary" : "default"} icon={<CheckOutlined />} onClick={() => setShowPins((v) => !v)}>Audit Pins</Button>
              <Button size="small" icon={<PrinterOutlined />} onClick={() => window.print()} />
            </div>
          </div>

          <div className="page-nav">
            {document.pages.map((item) => (
              <button key={item.pageNumber} className={item.pageNumber === page ? "active" : ""} onClick={() => setPage(item.pageNumber)}>
                {item.pageNumber}
              </button>
            ))}
          </div>

          <div className="pdf-stage">
            <PdfJsViewer document={document} page={page} selectedFinding={selected} showPins={showPins} onPin={jumpToEvidence} />
          </div>
        </section>

        <aside className="audit-pane">
          <div className="audit-header">
            <div className="audit-heading">
              <AuditOutlined />
              <div><h2>Compliance & Verification Report</h2><p>Financial controls & regulatory evidence log</p></div>
            </div>
            <div className="integrity">
              <span>CONTROL SCORE</span><strong>{score} / 100</strong>
              <Progress type="circle" percent={score} size={54} showInfo={false} />
            </div>
          </div>

          <div className="stat-grid">
            <StatCard title="Critical Flags" value={String(counts.fail)} detail="Requires remediation" tone="critical" />
            <StatCard title="Warnings" value={String(counts.review)} detail="Requires review" tone="warning" />
            <StatCard title="Verified Checks" value={String(counts.pass)} detail="Passed configured rules" tone="verified" />
          </div>

          <div className="finding-filters">
            <button className="active">All Items <b>{document.findings.length}</b></button>
            <button>Critical <b>{counts.fail}</b></button>
            <button>Warnings <b>{counts.review}</b></button>
            <button>Cleared <b>{counts.pass}</b></button>
          </div>

          <div className="finding-list">
            {document.findings.map((finding) => (
              <button key={finding.rule_id} className={`finding-select ${selectedId === finding.rule_id ? "selected" : ""}`} onClick={() => setSelectedId(finding.rule_id)}>
                <span className={`mini-status ${finding.status.toLowerCase()}`} />
                <span className="text-left"><strong>{finding.title}</strong><small>{finding.rule_id}</small></span>
              </button>
            ))}
          </div>

          <div className="detail-scroll">
            {selected && <FindingCard finding={selected} onEvidence={(evidence) => jumpToEvidence(selected, evidence)} />}
          </div>

          <div className="audit-footer">
            <div className="ledger-state"><span /> Regulatory source index: Connected</div>
            <Button>✎ Add Reviewer Note</Button>
            <Button type="primary" icon={<CheckOutlined />}>Certify</Button>
          </div>
        </aside>
      </main>
    </div>
  );
}

function StatCard({ title, value, detail, tone }: { title: string; value: string; detail: string; tone: "critical" | "warning" | "verified" }) {
  return <div className={`stat-card stat-${tone}`}><div className="flex items-center justify-between gap-2"><span>{title}</span><span className="stat-dot">{value}</span></div><strong>{detail}</strong></div>;
}
