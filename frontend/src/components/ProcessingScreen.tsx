import { useEffect, useRef, useState } from "react";
import { getJob } from "../api";
import type { Job, JobStatus } from "../types";

const STAGES: { status: JobStatus; label: string }[] = [
  { status: "UPLOADED", label: "Files received" },
  { status: "EXTRACTING", label: "Extracting datasets" },
  { status: "UNDERSTANDING_SCHEMA", label: "Understanding schema (AI)" },
  { status: "PLANNING", label: "Building reconciliation plan (AI)" },
  { status: "VALIDATING_PLAN", label: "Validating plan" },
  { status: "RECONCILING", label: "Running reconciliation" },
  { status: "INVESTIGATING", label: "Investigating exceptions (AI)" },
  { status: "GENERATING_REPORT", label: "Generating report" },
  { status: "COMPLETED", label: "Complete" },
];

interface Props {
  jobId: string;
  onComplete: () => void;
  onRestart: () => void;
}

export function ProcessingScreen({ jobId, onComplete, onRestart }: Props) {
  const [job, setJob] = useState<Job | null>(null);
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const current = await getJob(jobId);
        if (cancelled) return;
        setJob(current);
        if (current.status === "COMPLETED") {
          onComplete();
          return;
        }
        if (current.status === "FAILED") return;
        pollRef.current = window.setTimeout(poll, 1500);
      } catch {
        pollRef.current = window.setTimeout(poll, 3000);
      }
    }
    poll();

    return () => {
      cancelled = true;
      if (pollRef.current) window.clearTimeout(pollRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  if (job?.status === "FAILED") {
    return (
      <div>
        <div className="error-banner">
          <strong>{job.error_code ?? "FAILED"}</strong>
          <div>{job.error_message ?? "The job failed for an unknown reason."}</div>
        </div>
        <button className="ghost-button" onClick={onRestart}>
          Start a new reconciliation
        </button>
      </div>
    );
  }

  const activeIndex = STAGES.findIndex((s) => s.status === job?.status);

  return (
    <div className="card">
      <p style={{ color: "var(--text-muted)", fontSize: 13 }}>Job {jobId}</p>
      <ul className="stage-list">
        {STAGES.map((stage, i) => {
          const cls = activeIndex < 0 ? "" : i < activeIndex ? "done" : i === activeIndex ? "active" : "";
          return (
            <li key={stage.status} className={cls}>
              <span className="stage-dot" />
              {stage.label}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
