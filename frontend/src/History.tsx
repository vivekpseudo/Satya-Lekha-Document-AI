import { DownloadOutlined } from "@ant-design/icons";
import { Alert, Button, Empty, Grid, Modal, Skeleton, Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useState } from "react";
import { downloadComplianceReport, getReport, listReports } from "./api";
import { useAuth } from "./auth";
import { ReportBody } from "./report";
import { navigate } from "./router";
import SiteHeader from "./SiteHeader";
import type { ReportDetail, ReportSummary } from "./types";

const dateFormat = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" });
const formatDate = (iso?: string | null) => (iso && !Number.isNaN(Date.parse(iso)) ? dateFormat.format(new Date(iso)) : "—");
const typeLabel = (t: string) => t.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

export default function History() {
  const { user } = useAuth();
  // Below the "md" breakpoint (768px) a wide table cannot show the Open report button, so use cards.
  const compact = !Grid.useBreakpoint().md;
  const [rows, setRows] = useState<ReportSummary[] | null>(null);
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState<number | null>(null);
  const [detail, setDetail] = useState<ReportDetail | null>(null);
  const [detailError, setDetailError] = useState("");

  useEffect(() => {
    listReports().then(setRows).catch((e) => setError(e instanceof Error ? e.message : "Could not load your history."));
  }, []);

  useEffect(() => {
    if (openId === null) return;
    let cancelled = false;
    setDetail(null);
    setDetailError("");
    getReport(openId)
      .then((d) => { if (!cancelled) setDetail(d); })
      .catch((e) => { if (!cancelled) setDetailError(e instanceof Error ? e.message : "Could not open this report."); });
    return () => { cancelled = true; };
  }, [openId]);

  const exportPdf = async () => {
    if (!detail) return;
    const blob = await downloadComplianceReport(detail, user?.organization);
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${detail.document_name.replace(/\.[^.]+$/, "")}_compliance_report.pdf`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const columns: ColumnsType<ReportSummary> = [
    { title: "Document", dataIndex: "document_name", key: "name", ellipsis: true, sorter: (a, b) => a.document_name.localeCompare(b.document_name) },
    { title: "Type", dataIndex: "document_type", key: "type", render: typeLabel, responsive: ["md"] },
    {
      title: "Checked on", dataIndex: "created_at", key: "date", render: formatDate, defaultSortOrder: "descend",
      sorter: (a, b) => Date.parse(a.created_at) - Date.parse(b.created_at),
    },
    {
      title: "Result", key: "result", responsive: ["sm"],
      render: (_, r) => (
        <span className="result-tags">
          <Tag color="error">{r.counts.FAIL} critical</Tag>
          <Tag color="warning">{r.counts.REVIEW} review</Tag>
          <Tag color="success">{r.counts.PASS} passed</Tag>
        </span>
      ),
    },
    {
      title: "", key: "open", align: "right",
      render: (_, r) => <Button type="primary" ghost onClick={() => setOpenId(r.id)}>Open report</Button>,
    },
  ];

  return (
    <div className="page">
      <SiteHeader />
      <main className="history">
        <div className="history-head">
          <div>
            <h1>History</h1>
            <p className="muted">Your past compliance reports. The documents you uploaded are not stored.</p>
          </div>
          <Button type="primary" onClick={() => navigate("/app")}>Check a document</Button>
        </div>

        {error && <Alert type="error" showIcon message={error} />}
        {!error && rows === null && <Skeleton active />}
        {rows && compact && (
          rows.length === 0 ? (
            <Empty description="No reports yet. Check a document and its report will appear here." />
          ) : (
            <ul className="history-cards">
              {[...rows].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)).map((r) => (
                <li key={r.id} className="history-card">
                  <strong className="history-card-name">{r.document_name}</strong>
                  <small className="muted">{typeLabel(r.document_type)} · {formatDate(r.created_at)}</small>
                  <span className="result-tags">
                    <Tag color="error">{r.counts.FAIL} critical</Tag>
                    <Tag color="warning">{r.counts.REVIEW} review</Tag>
                    <Tag color="success">{r.counts.PASS} passed</Tag>
                  </span>
                  <Button type="primary" ghost block onClick={() => setOpenId(r.id)}>Open report</Button>
                </li>
              ))}
            </ul>
          )
        )}
        {rows && !compact && (
          <Table<ReportSummary>
            rowKey="id"
            columns={columns}
            dataSource={rows}
            pagination={rows.length > 10 ? { pageSize: 10, hideOnSinglePage: true } : false}
            scroll={{ x: "max-content" }}
            locale={{ emptyText: <Empty description="No reports yet. Check a document and its report will appear here." /> }}
          />
        )}
      </main>

      <Modal
        open={openId !== null}
        onCancel={() => setOpenId(null)}
        title={detail ? detail.document_name : "Report"}
        width={820}
        className="report-modal"
        destroyOnClose
        footer={[
          <Button key="pdf" icon={<DownloadOutlined />} disabled={!detail} onClick={() => void exportPdf()}>Export PDF</Button>,
          <Button key="close" type="primary" onClick={() => setOpenId(null)}>Close</Button>,
        ]}
      >
        {detailError && <Alert type="error" showIcon message={detailError} />}
        {!detail && !detailError && <Skeleton active />}
        {detail && (
          <>
            <p className="muted report-meta">
              {typeLabel(detail.document_type)} · Reporting date {detail.reporting_date || "not found"} · Checked on {formatDate(detail.created_at)}
            </p>
            <ReportBody findings={detail.findings} />
          </>
        )}
      </Modal>
    </div>
  );
}
