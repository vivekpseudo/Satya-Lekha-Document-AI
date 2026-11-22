import { useEffect, useMemo, useRef, useState } from "react";
import {
  AuditOutlined,
  CheckOutlined,
  CloudUploadOutlined,
  DownloadOutlined,
  FilePdfOutlined,
  InboxOutlined,
  PrinterOutlined,
  LeftOutlined,
  RightOutlined,
} from "@ant-design/icons";
import { Button, Dropdown, Progress, Upload, message } from "antd";
import type { UploadProps } from "antd";
import { getDocument, GlobalWorkerOptions, type PDFDocumentProxy } from "pdfjs-dist";
import { crossCheckDocuments, downloadComplianceReport, evaluateCompliance, processDocument, saveReport } from "./api";
import { useAuth } from "./auth";
import { FindingCard, countFindings, scoreFindings } from "./report";
import { Link } from "./router";
import SiteHeader from "./SiteHeader";
import type { DocumentPage, EvidenceBox, Finding, ProcessedDocument } from "./types";

GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

function normalizeEvidence(raw: EvidenceBox): EvidenceBox {
  // The API reports the page as source_page; the viewer filters on page.
  const evidence = { ...raw, page: raw.page ?? raw.source_page ?? 1 };
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
    if (!source || !isPdfDocument(document)) {
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
  }, [document.document_url, document.document_mime]);

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

        await pdfPage.render({ canvas, canvasContext: context, viewport }).promise;
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

  if (!isPdfDocument(document)) {
    return (
      <div className="pdf-error">
        A page preview is only available for PDF files. Your findings are shown on the right.
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

// The API returns pages as { page_number, ... }; the viewer works with { pageNumber }.
function normalizePages(raw: unknown): DocumentPage[] {
  const pages = Array.isArray(raw) ? (raw as Array<Record<string, unknown>>) : [];
  if (!pages.length) return [{ pageNumber: 1 }];
  return pages.map((item, index) => ({
    pageNumber: Number(item.pageNumber ?? item.page_number ?? index + 1) || index + 1,
  }));
}

// Uploaded files get a blob: URL with no ".pdf" suffix, so detect PDFs by MIME type too.
function isPdfDocument(doc: { document_url?: string; document_mime?: string }): boolean {
  if (!doc.document_url) return false;
  return doc.document_mime === "application/pdf" || /\.pdf($|#)/i.test(doc.document_url);
}

export default function Workspace() {
  const { user } = useAuth();
  const [document, setDocument] = useState<ProcessedDocument | null>(null);
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState("");
  const [showPins, setShowPins] = useState(true);
  const [loading, setLoading] = useState(false);
  // Documents uploaded this session, by name, so they can be cross-checked against each other.
  const sessionDocuments = useRef(new Map<string, ProcessedDocument>());
  const [messageApi, contextHolder] = message.useMessage();

  const findings = document?.findings ?? [];
  const counts = useMemo(() => countFindings(findings), [findings]);
  const score = useMemo(() => scoreFindings(findings), [findings]);
  const selected = findings.find((x) => x.rule_id === selectedId) || findings[0];
  const totalPages = Math.max(document?.pages.length ?? 1, 1);

  const runDocument = async (file: File) => {
    setLoading(true);
    try {
      const localUrl = URL.createObjectURL(file);
      const processed = await processDocument(file);
      const ownFindings = await evaluateCompliance(processed);
      sessionDocuments.current.set(processed.document_name, processed);
      let all = ownFindings;
      let crossNote = "";
      if (sessionDocuments.current.size >= 2) {
        try {
          const crossFindings = await crossCheckDocuments([...sessionDocuments.current.values()]);
          all = [...ownFindings, ...crossFindings];
          crossNote = ` Cross-checked against ${sessionDocuments.current.size - 1} other document(s).`;
        } catch {
          messageApi.warning("Cross-document checks could not be run.");
        }
      }
      const result: ProcessedDocument = {
        ...processed,
        document_url: processed.document_url || localUrl,
        document_mime: file.type,
        findings: all,
        pages: normalizePages(processed.pages),
      };
      setDocument(result);
      setPage(1);
      setSelectedId(all[0]?.rule_id || "");
      // Only the report is kept in History, never the uploaded file.
      try {
        await saveReport(result);
        messageApi.success(`Report ready and saved to your History.${crossNote}`);
      } catch {
        messageApi.warning("Report ready, but it could not be saved to your History.");
      }
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "Processing failed");
    } finally {
      setLoading(false);
    }
  };

  const uploadProps: UploadProps = {
    showUploadList: false,
    accept: ".pdf,.png,.jpg,.jpeg,.tif,.tiff",
    disabled: loading,
    beforeUpload: (file) => {
      void runDocument(file);
      return false;
    },
  };

  const exportPdf = async () => {
    if (!document) return;
    try {
      const blob = await downloadComplianceReport(document, user?.organization);
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

  // Prints the same PDF that "Export PDF report" downloads, not the web page.
  const printReport = async () => {
    if (!document) return;
    try {
      const blob = await downloadComplianceReport(document, user?.organization);
      const url = URL.createObjectURL(blob);
      const frame = window.document.createElement("iframe");
      frame.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0;visibility:hidden";
      frame.src = url;
      const cleanup = () => {
        frame.remove();
        URL.revokeObjectURL(url);
      };
      frame.onload = () => {
        try {
          frame.contentWindow?.focus();
          frame.contentWindow?.print();
          setTimeout(cleanup, 60000);
        } catch {
          // Some browsers will not print an embedded PDF: open it so it can be printed from there.
          window.open(url, "_blank");
          setTimeout(cleanup, 60000);
        }
      };
      window.document.body.appendChild(frame);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "Unable to print the report");
    }
  };

  const jumpToEvidence = (finding: Finding, evidence: EvidenceBox) => {
    if (!document) return;
    setSelectedId(finding.rule_id);
    // Cross-document evidence can come from another file; only jump within this one.
    if (evidence.document && evidence.document !== document.document_name) return;
    const target = evidence.page || evidence.source_page || 1;
    setPage(Math.min(Math.max(target, 1), totalPages));
  };

  const header = (
    <SiteHeader
      actions={
        <>
          <Upload {...uploadProps}>
            <Button loading={loading} icon={<CloudUploadOutlined />}>{document ? "Check another" : "Upload document"}</Button>
          </Upload>
          {document && (
            <Dropdown menu={{ items: [
              { key: "pdf", icon: <FilePdfOutlined />, label: "Export PDF report", onClick: exportPdf },
              { key: "print", icon: <PrinterOutlined />, label: "Print report", onClick: printReport },
            ] }}>
              <Button icon={<DownloadOutlined />} aria-label="Export or print" />
            </Dropdown>
          )}
        </>
      }
    />
  );

  if (!document) {
    return (
      <div className="page">
        {contextHolder}
        {header}
        <main className="empty-workspace">
          <h1>Check a filing document</h1>
          <p>Upload a PDF from your annual filing. You get a control score and every finding with the text or figures it relied on.</p>
          <Upload.Dragger {...uploadProps} className="dropzone">
            <p className="ant-upload-drag-icon"><InboxOutlined /></p>
            <p className="ant-upload-text">{loading ? "Reading and checking your document…" : "Click or drag a document here"}</p>
            <p className="ant-upload-hint">PDF, PNG, JPG or TIFF, up to 20 MB. Only the finished report is kept, not your file.</p>
          </Upload.Dragger>
          <p className="muted">Past reports are in your <Link to="/history">History</Link>.</p>
        </main>
      </div>
    );
  }

  return (
    <div className="page">
      {contextHolder}
      {header}

      <section className="document-strip">
        <div className="document-context">
          <span className="context-dot" />
          <strong>{document.document_name}</strong>
          <i /><span>Framework: {document.framework || "Ind AS"}</span>
          <i /><span>Reporting date: {document.reporting_date || "Not provided"}</span>
        </div>
        <div className="audit-status">
          Compliance status: <b>{counts.fail + counts.review} items need attention</b>
          <span className="classification-pill">Classified as {document.classification.document_type} • {(document.classification.confidence * 100).toFixed(0)}%</span>
        </div>
      </section>

      <main className="workspace">
        <section className="document-pane">
          <div className="pane-toolbar">
            <div className="toolbar-title"><FilePdfOutlined /> Document preview <span>Page {page} of {totalPages}</span></div>
            <div className="toolbar-actions">
              <Button size="small" disabled={page <= 1} icon={<LeftOutlined />} aria-label="Previous page" onClick={() => setPage((p) => Math.max(1, p - 1))} />
              <span>{page} / {totalPages}</span>
              <Button size="small" disabled={page >= totalPages} icon={<RightOutlined />} aria-label="Next page" onClick={() => setPage((p) => Math.min(totalPages, p + 1))} />
              <Button size="small" type={showPins ? "primary" : "default"} icon={<CheckOutlined />} onClick={() => setShowPins((v) => !v)}>Audit pins</Button>
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
              <div><h2>Compliance report</h2><p>Findings and the evidence behind them</p></div>
            </div>
            <div className="integrity">
              <span>CONTROL SCORE</span><strong>{score} / 100</strong>
              <Progress type="circle" percent={score} size={54} showInfo={false} />
            </div>
          </div>

          <div className="stat-grid">
            <StatCard title="Critical flags" value={String(counts.fail)} detail="Requires remediation" tone="critical" />
            <StatCard title="Warnings" value={String(counts.review)} detail="Requires review" tone="warning" />
            <StatCard title="Verified checks" value={String(counts.pass)} detail="Passed configured rules" tone="verified" />
          </div>

          <div className="finding-list">
            {findings.map((finding) => (
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
            <div className="ledger-state"><span /> Saved to your <Link to="/history">History</Link></div>
            <Button icon={<DownloadOutlined />} onClick={exportPdf}>Export PDF</Button>
          </div>
        </aside>
      </main>
    </div>
  );
}

function StatCard({ title, value, detail, tone }: { title: string; value: string; detail: string; tone: "critical" | "warning" | "verified" }) {
  return <div className={`stat-card stat-${tone}`}><div className="flex items-center justify-between gap-2"><span>{title}</span><span className="stat-dot">{value}</span></div><strong>{detail}</strong></div>;
}
