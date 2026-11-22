import {
  CheckCircleFilled,
  ExclamationCircleFilled,
  InfoCircleOutlined,
  WarningFilled,
} from "@ant-design/icons";
import { Progress, Tag } from "antd";
import type { EvidenceBox, Finding, Status } from "./types";

export const statusMeta: Record<Status, { label: string; className: string }> = {
  PASS: { label: "Verified", className: "status-pass" },
  FAIL: { label: "Critical", className: "status-fail" },
  REVIEW: { label: "Review", className: "status-review" },
};

export function scoreFindings(findings: Finding[]) {
  if (!findings.length) return 0;
  const weighted = findings.reduce((sum, item) => {
    if (item.status === "PASS") return sum + 1;
    if (item.status === "REVIEW") return sum + 0.5;
    return sum;
  }, 0);
  return Math.round((weighted / findings.length) * 100);
}

export function FindingCard({
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
                  {(evidence.page || evidence.source_page) && <small>Page {evidence.page || evidence.source_page}</small>}
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

export function countFindings(findings: Finding[]) {
  return {
    fail: findings.filter((x) => x.status === "FAIL").length,
    review: findings.filter((x) => x.status === "REVIEW").length,
    pass: findings.filter((x) => x.status === "PASS").length,
  };
}

/** A finished report: score, counts and every finding with its evidence. Used by the history modal. */
export function ReportBody({ findings }: { findings: Finding[] }) {
  const counts = countFindings(findings);
  const score = scoreFindings(findings);
  return (
    <div className="report-body">
      <div className="report-score">
        <Progress type="circle" percent={score} size={72} />
        <div>
          <span>CONTROL SCORE</span>
          <strong>{score} / 100</strong>
          <small>Share of checks passed, with warnings counted as half.</small>
        </div>
      </div>
      <div className="stat-grid">
        <div className="stat-card stat-critical"><span>Critical flags</span><strong>{counts.fail}</strong></div>
        <div className="stat-card stat-warning"><span>Warnings</span><strong>{counts.review}</strong></div>
        <div className="stat-card stat-verified"><span>Verified checks</span><strong>{counts.pass}</strong></div>
      </div>
      <div className="report-findings">
        {findings.map((finding, index) => (
          <FindingCard key={`${finding.rule_id}-${index}`} finding={finding} onEvidence={noop} />
        ))}
        {!findings.length && <p className="muted">No findings were recorded for this report.</p>}
      </div>
    </div>
  );
}

const noop = (_evidence: EvidenceBox) => {};
