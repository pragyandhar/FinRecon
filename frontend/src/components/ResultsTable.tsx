import type { ReconciliationResult } from "../types";

interface Props {
  results: ReconciliationResult[];
  onSelect: (result: ReconciliationResult) => void;
}

export function ResultsTable({ results, onSelect }: Props) {
  if (results.length === 0) {
    return <p className="empty-state">No records in this category.</p>;
  }

  return (
    <table className="results-table">
      <thead>
        <tr>
          <th>Record</th>
          <th>Status</th>
          <th>Rule</th>
          <th>Reason</th>
        </tr>
      </thead>
      <tbody>
        {results.map((r) => (
          <tr key={`${r.step_id}-${r.record_id}`} onClick={() => onSelect(r)}>
            <td>{r.record_id}</td>
            <td>
              <span className={`status-pill ${r.status}`}>{r.status}</span>
            </td>
            <td>{r.rule_applied}</td>
            <td style={{ color: "var(--text-muted)" }}>{r.reason ?? "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
