import { useMemo, useState } from "react";
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
  SearchOutlined,
  WarningFilled,
  ExclamationCircleFilled,
  RightOutlined,
  UploadOutlined,
} from "@ant-design/icons";
import { Button, Dropdown, Progress, Tag, Tooltip, Upload, message } from "antd";
import type { UploadProps } from "antd";

type Status = "PASS" | "FAIL" | "REVIEW";

type Finding = {
  id: string;
  status: Status;
  severity: "HIGH" | "MEDIUM" | "LOW";
  title: string;
  rule: string;
  summary: string;
  reported?: string;
  expected?: string;
  variance?: string;
  source: string;
};

const findings: Finding[] = [
  {
    id: "INDAS-FS-001",
    status: "FAIL",
    severity: "HIGH",
    title: "Balance-sheet equation variance",
    rule: "Financial statement integrity",
    summary:
      "Total assets do not reconcile to total liabilities plus equity within the configured tolerance.",
    reported: "₹137,300",
    expected: "₹279,800",
    variance: "-₹142,500",
    source: "Balance Sheet • Page 1",
  },
  {
    id: "DISC-002",
    status: "REVIEW",
    severity: "MEDIUM",
    title: "Retained earnings roll-forward",
    rule: "Equity reconciliation",
    summary:
      "Opening retained earnings, current-year profit and dividends require source-note verification.",
    reported: "₹137,300",
    expected: "₹279,800",
    variance: "-₹142,500",
    source: "Notes to Accounts • Page 14",
  },
  {
    id: "DATA-QUALITY-001",
    status: "PASS",
    severity: "LOW",
    title: "Revenue sign check",
    rule: "Data quality",
    summary: "No negative revenue value was detected in the extracted statement facts.",
    source: "Statement of Profit & Loss • Page 2",
  },
];

const statusMeta: Record<Status, { label: string; className: string }> = {
  PASS: { label: "Verified", className: "status-pass" },
  FAIL: { label: "Critical", className: "status-fail" },
  REVIEW: { label: "Review", className: "status-review" },
};

function StatCard({
  title,
  value,
  detail,
  tone,
}: {
  title: string;
  value: string;
  detail: string;
  tone: "critical" | "warning" | "verified";
}) {
  return (
    <div className={`stat-card stat-${tone}`}>
      <div className="flex items-center justify-between gap-2">
        <span>{title}</span>
        <span className="stat-dot">{value}</span>
      </div>
      <strong>{detail}</strong>
    </div>
  );
}

function FindingCard({ finding }: { finding: Finding }) {
  const meta = statusMeta[finding.status];
  return (
    <article className={`finding-card ${meta.className}`}>
      <div className="flex items-start gap-3">
        <div className="finding-icon">
          {finding.status === "FAIL" ? (
            <ExclamationCircleFilled />
          ) : finding.status === "REVIEW" ? (
            <WarningFilled />
          ) : (
            <CheckCircleFilled />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <Tag bordered={false} className="status-tag">{meta.label}</Tag>
            <span className="rule-label">{finding.rule}</span>
            <span className="ml-auto text-xs text-slate-400">{finding.source}</span>
          </div>
          <h3>{finding.title}</h3>
          <p>{finding.summary}</p>

          {finding.reported && (
            <div className="variance-grid">
              <div><span>REPORTED</span><b>{finding.reported}</b></div>
              <div><span>EXPECTED</span><b>{finding.expected}</b></div>
              <div><span>VARIANCE</span><b className="text-red-600">{finding.variance}</b></div>
            </div>
          )}

          {finding.status !== "PASS" && (
            <div className="evidence-box">
              <div className="flex items-center gap-2 font-semibold text-slate-700">
                <InfoCircleOutlined />
                Regulatory evidence
              </div>
              <p>
                Candidate regulatory sources are retrieved using the reporting
                date, framework, jurisdiction and entity applicability metadata.
              </p>
              <button className="evidence-link">
                View source evidence <RightOutlined />
              </button>
            </div>
          )}
        </div>
      </div>
    </article>
  );
}

export default function App() {
  const [activeTab, setActiveTab] = useState<"balance" | "pl">("balance");
  const [showPins, setShowPins] = useState(true);
  const [selected, setSelected] = useState(findings[0].id);
  const [messageApi, contextHolder] = message.useMessage();

  const counts = useMemo(
    () => ({
      fail: findings.filter((item) => item.status === "FAIL").length,
      review: findings.filter((item) => item.status === "REVIEW").length,
      pass: findings.filter((item) => item.status === "PASS").length,
    }),
    [],
  );

  const uploadProps: UploadProps = {
    showUploadList: false,
    accept: ".pdf,.png,.jpg,.jpeg,.tif,.tiff",
    beforeUpload: (file) => {
      messageApi.success(`Queued ${file.name} for Document AI processing.`);
      return false;
    },
  };

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      {contextHolder}

      <header className="topbar">
        <div className="brand">
          <div className="brand-mark"><SafetyCertificateOutlined /></div>
          <div>
            <div className="brand-name">Satya-Lekha</div>
            <div className="brand-subtitle">AI Compliance Intelligence</div>
          </div>
          <span className="product-badge">Ind AS • SEBI • RBI</span>
        </div>

        <div className="header-actions">
          <Upload {...uploadProps}>
            <Button icon={<CloudUploadOutlined />}>Upload Document</Button>
          </Upload>
          <Button type="primary" icon={<PlayCircleFilled />}>Run Compliance</Button>
          <Dropdown
            menu={{
              items: [
                { key: "pdf", icon: <FilePdfOutlined />, label: "Export PDF report" },
                { key: "print", icon: <PrinterOutlined />, label: "Print report" },
              ],
            }}
          >
            <Button icon={<DownloadOutlined />} />
          </Dropdown>
          <Button className="mobile-menu" icon={<MenuOutlined />} />
        </div>
      </header>

      <section className="document-strip">
        <div className="document-context">
          <span className="context-dot" />
          <strong>Acme Global Holdings Pvt. Ltd.</strong>
          <span>Consolidated Balance Sheet FY2025</span>
          <i />
          <span>Framework: Ind AS</span>
          <i />
          <span>Materiality threshold: ₹10,00,000</span>
        </div>
        <div className="audit-status">
          Compliance Status: <b>{counts.fail + counts.review} Items Require Attention</b>
          <button>View Methodology</button>
        </div>
      </section>

      <main className="workspace">
        <section className="document-pane">
          <div className="pane-toolbar">
            <div className="toolbar-title"><FilePdfOutlined /> PDF Preview <span>Page 1 of 18</span></div>
            <div className="toolbar-actions">
              <Button size="small" icon={<SearchOutlined />} />
              <span>100%</span>
              <Button size="small">↗</Button>
              <Button
                size="small"
                type={showPins ? "primary" : "default"}
                icon={<CheckOutlined />}
                onClick={() => setShowPins((value) => !value)}
              >
                Audit Pins
              </Button>
              <Button size="small" icon={<PrinterOutlined />} />
            </div>
          </div>

          <div className="statement-tabs">
            <button className={activeTab === "balance" ? "active" : ""} onClick={() => setActiveTab("balance")}>
              Balance Sheet
            </button>
            <button className={activeTab === "pl" ? "active" : ""} onClick={() => setActiveTab("pl")}>
              Income Statement (P&L)
            </button>
          </div>

          <div className="pdf-stage">
            <div className="paper">
              <div className="paper-header">
                <div>
                  <h1>ACME GLOBAL HOLDINGS PVT. LTD.</h1>
                  <h2>{activeTab === "balance" ? "CONSOLIDATED BALANCE SHEET" : "STATEMENT OF PROFIT AND LOSS"}</h2>
                  <p>As at March 31, 2025 and 2024</p>
                  <p>(Amounts in ₹ lakhs)</p>
                </div>
                <div className="exhibit">
                  Exhibit<br /><b>99.1</b>
                  <small>Source: Annual Report</small>
                </div>
              </div>

              <div className="paper-rule" />
              <div className="paper-section">{activeTab === "balance" ? "ASSETS" : "INCOME"}</div>
              <div className="paper-subsection">{activeTab === "balance" ? "Current Assets" : "Revenue from Operations"}</div>

              <table className="statement-table">
                <thead>
                  <tr><th>Line Item Description</th><th>2025</th><th>2024</th></tr>
                </thead>
                <tbody>
                  {(activeTab === "balance"
                    ? [
                        ["Cash and cash equivalents", "₹184.50", "₹142.20"],
                        ["Trade receivables, net", "₹92.40", "₹88.10"],
                        ["Inventories, net", "₹148.20", "₹135.40"],
                        ["Prepaid expenses and other current assets", "₹21.90", "₹18.30"],
                        ["Property, plant and equipment", "₹412.60", "₹398.20"],
                        ["Other non-current assets", "₹67.80", "₹59.10"],
                      ]
                    : [
                        ["Revenue from operations", "₹1,248.60", "₹1,108.40"],
                        ["Other income", "₹32.40", "₹28.70"],
                        ["Total income", "₹1,281.00", "₹1,137.10"],
                        ["Cost of materials consumed", "₹684.20", "₹610.80"],
                        ["Employee benefits expense", "₹188.40", "₹169.20"],
                        ["Profit before tax", "₹142.70", "₹126.50"],
                      ]
                  ).map(([label, current, previous]) => (
                    <tr key={label}>
                      <td>{label}</td><td>{current}</td><td>{previous}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {showPins && (
                <>
                  <div className="audit-pin pin-one">1</div>
                  <div className="audit-pin pin-two">2</div>
                </>
              )}
            </div>
          </div>
        </section>

        <aside className="audit-pane">
          <div className="audit-header">
            <div className="audit-heading">
              <AuditOutlined />
              <div>
                <h2>Compliance & Verification Report</h2>
                <p>Automated financial controls & regulatory evidence log</p>
              </div>
            </div>
            <div className="integrity">
              <span>COMPLIANCE SCORE</span>
              <strong>82 / 100</strong>
              <Progress type="circle" percent={82} size={54} showInfo={false} />
            </div>
          </div>

          <div className="stat-grid">
            <StatCard title="Critical Flags" value={String(counts.fail)} detail="₹14.25 Cr variance" tone="critical" />
            <StatCard title="Warnings" value={String(counts.review)} detail="Requires review" tone="warning" />
            <StatCard title="Verified Checks" value={String(counts.pass)} detail="Math & controls" tone="verified" />
          </div>

          <div className="finding-filters">
            <button className="active">All Items <b>{findings.length}</b></button>
            <button>Critical <b>{counts.fail}</b></button>
            <button>Warnings <b>{counts.review}</b></button>
            <button>Cleared <b>{counts.pass}</b></button>
          </div>

          <div className="finding-list">
            {findings.map((finding) => (
              <button
                key={finding.id}
                className={`finding-select ${selected === finding.id ? "selected" : ""}`}
                onClick={() => setSelected(finding.id)}
              >
                <span className={`mini-status ${finding.status.toLowerCase()}`} />
                <span className="text-left">
                  <strong>{finding.title}</strong>
                  <small>{finding.rule}</small>
                </span>
              </button>
            ))}
          </div>

          <div className="detail-scroll">
            <FindingCard finding={findings.find((item) => item.id === selected) ?? findings[0]} />
          </div>

          <div className="audit-footer">
            <div className="ledger-state"><span /> Regulatory source index: Ready</div>
            <Button icon={<EditOutlinedFallback />}>Add Reviewer Note</Button>
            <Button type="primary" icon={<CheckOutlined />}>Certify</Button>
          </div>
        </aside>
      </main>
    </div>
  );
}

function EditOutlinedFallback() {
  return <span aria-hidden>✎</span>;
}