import { Fragment } from "react";
import { ChatPanel } from "./ChatPanel";
import type { ExceptionExplanation, ReconciliationResult } from "../types";

interface Props {
  jobId: string;
  result: ReconciliationResult;
  explanation?: ExceptionExplanation;
  onClose: () => void;
}

function formatValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (Array.isArray(v)) return v.map(formatValue).join(", ");
  return String(v);
}

export function RecordDetail({ jobId, result, explanation, onClose }: Props) {
  return (
    <div className="detail-panel">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
        <div>
          <h2>{result.record_id}</h2>
          <span className={`status-pill ${result.status}`}>{result.status}</span>
        </div>
        <button className="ghost-button" onClick={onClose}>
          Close
        </button>
      </div>

      <p style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 12 }}>
        Rule applied: <strong>{result.rule_applied}</strong>
      </p>
      {result.reason && <p style={{ fontSize: 13 }}>{result.reason}</p>}

      {result.checks.length > 0 && (
        <>
          <h3 style={{ fontSize: 13, marginBottom: 6 }}>Deterministic checks</h3>
          {result.checks.map((c, i) => (
            <div className="evidence-block" key={i}>
              <dl>
                <dt>field</dt>
                <dd>{c.field}</dd>
                <dt>expected</dt>
                <dd>{formatValue(c.expected)}</dd>
                <dt>actual</dt>
                <dd>{formatValue(c.actual)}</dd>
                <dt>result</dt>
                <dd>{c.result}</dd>
              </dl>
            </div>
          ))}
        </>
      )}

      <h3 style={{ fontSize: 13, marginBottom: 6 }}>Evidence</h3>
      {result.evidence.map((e, i) => (
        <div className="evidence-block" key={i}>
          <strong style={{ fontSize: 12 }}>
            {e.dataset_id} · {e.row_id}
          </strong>
          <dl>
            {Object.entries(e.values).map(([k, v]) => (
              <Fragment key={k}>
                <dt>{k}</dt>
                <dd>{formatValue(v)}</dd>
              </Fragment>
            ))}
          </dl>
        </div>
      ))}

      {explanation && (
        <div className="ai-explanation">
          <strong style={{ fontSize: 12 }}>AI explanation {explanation.resolved ? "" : "(unresolved)"}</strong>
          <p style={{ margin: "6px 0" }}>{explanation.reason}</p>
          {explanation.likely_cause && (
            <p style={{ margin: "4px 0" }}>
              <strong>Likely cause:</strong> {explanation.likely_cause}
            </p>
          )}
          {explanation.recommended_action && (
            <p style={{ margin: "4px 0" }}>
              <strong>Recommended action:</strong> {explanation.recommended_action}
            </p>
          )}
          <p style={{ margin: "4px 0", color: "var(--text-muted)", fontSize: 12 }}>
            confidence: {(explanation.confidence * 100).toFixed(0)}%
          </p>
        </div>
      )}

      <ChatPanel jobId={jobId} recordId={result.record_id} />
    </div>
  );
}
