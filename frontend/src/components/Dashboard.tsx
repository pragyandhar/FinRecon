import { useEffect, useState } from "react";
import { getReport, FinReconApiError } from "../api";
import type { Report, ReconciliationResult, RecordStatus, StepMetrics } from "../types";
import { ResultsTable } from "./ResultsTable";
import { RecordDetail } from "./RecordDetail";
import { ChatPanel } from "./ChatPanel";

interface Props {
  jobId: string;
  onRestart: () => void;
}

type Filter = "ALL" | RecordStatus;

const FILTERS: Filter[] = ["ALL", "MATCHED", "MISMATCHED", "EXCEPTION", "UNRESOLVED"];

function breakdownText(s: StepMetrics): string {
  const parts = [`${s.matched} matched`, `${s.mismatched} mismatched`];
  if (s.exceptions > 0) parts.push(`${s.exceptions} exceptions`);
  if (s.unresolved > 0) parts.push(`${s.unresolved} unresolved`);
  return parts.join(" · ");
}

export function Dashboard({ jobId, onRestart }: Props) {
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("ALL");
  const [selected, setSelected] = useState<ReconciliationResult | null>(null);
  const [chatOpen, setChatOpen] = useState(false);

  useEffect(() => {
    getReport(jobId)
      .then(setReport)
      .catch((err) => setError(err instanceof FinReconApiError ? err.message : "Could not load report."));
  }, [jobId]);

  if (error) {
    return (
      <div>
        <div className="error-banner">{error}</div>
        <button className="ghost-button" onClick={onRestart}>
          Start a new reconciliation
        </button>
      </div>
    );
  }

  if (!report) {
    return <p className="empty-state">Loading report...</p>;
  }

  const filtered = filter === "ALL" ? report.results : report.results.filter((r) => r.status === filter);
  const explanationFor = (recordId: string) =>
    report.exception_explanations.find((e) => e.record_id === recordId);

  const { metrics } = report;

  return (
    <div>
      <div className="metrics-grid">
        <div className="metric-tile highlight">
          <div className="value">{(metrics.match_rate * 100).toFixed(0)}%</div>
          <div className="label">Match rate</div>
        </div>
        <div className="metric-tile">
          <div className="value">{metrics.total_records}</div>
          <div className="label">Total records</div>
        </div>
        <div className="metric-tile">
          <div className="value">{metrics.matched}</div>
          <div className="label">Matched</div>
        </div>
        <div className="metric-tile">
          <div className="value">{metrics.mismatched}</div>
          <div className="label">Mismatched</div>
        </div>
        <div className="metric-tile">
          <div className="value">{metrics.exceptions}</div>
          <div className="label">Exceptions</div>
        </div>
        <div className="metric-tile">
          <div className="value">{metrics.unresolved}</div>
          <div className="label">Unresolved</div>
        </div>
      </div>

      {report.by_step.length > 1 && (
        <div style={{ marginBottom: 20 }}>
          <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "0 0 12px" }}>
            Overall match rate combines all reconciliation checks. View each relationship below for the
            detailed breakdown.
          </p>
          <div className="relationship-grid">
            {report.by_step.map((s) => (
              <div key={s.step_id} className="relationship-card">
                <div className="relationship-name">{s.relationship}</div>
                <div className="relationship-row">
                  <span className="relationship-count">{s.total_records} records</span>
                  <span className={`relationship-rate ${s.match_rate < 0.9 ? "low" : ""}`}>
                    {(s.match_rate * 100).toFixed(0)}% match
                  </span>
                </div>
                <div className="relationship-breakdown">{breakdownText(s)}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <div className="status-tabs">
          {FILTERS.map((f) => (
            <button
              key={f}
              className={`status-tab ${filter === f ? "selected" : ""}`}
              onClick={() => setFilter(f)}
            >
              {f === "ALL" ? "All" : f.charAt(0) + f.slice(1).toLowerCase()}
            </button>
          ))}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <a className="ghost-button" href={`/reconciliation/jobs/${jobId}/report?format=csv`} download>
            Export CSV
          </a>
          <button className={`ghost-button ${chatOpen ? "selected" : ""}`} onClick={() => setChatOpen((v) => !v)}>
            Chat
          </button>
        </div>
      </div>

      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        <ResultsTable results={filtered} onSelect={setSelected} />
      </div>

      {chatOpen && (
        <div className="chat-popup">
          <button className="chat-popup-close" onClick={() => setChatOpen(false)} aria-label="Close chat">
            ×
          </button>
          <ChatPanel jobId={jobId} />
        </div>
      )}

      <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 16 }}>
        {metrics.total_records} records processed · {metrics.total_variance_amount} total variance ·{" "}
        {report.ai_calls_made} AI calls made ·{" "}
        <button className="ghost-button" style={{ padding: "2px 8px" }} onClick={onRestart}>
          New reconciliation
        </button>
      </p>

      {selected && (
        <RecordDetail
          jobId={jobId}
          result={selected}
          explanation={explanationFor(selected.record_id)}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
