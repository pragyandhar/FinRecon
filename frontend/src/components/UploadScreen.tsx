import { useRef, useState } from "react";
import { createJob, FinReconApiError } from "../api";

interface Props {
  onJobCreated: (jobId: string) => void;
}

export function UploadScreen({ onJobCreated }: Props) {
  const [files, setFiles] = useState<File[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function addFiles(list: FileList | null) {
    if (!list) return;
    setFiles((prev) => [...prev, ...Array.from(list)]);
  }

  function removeFile(index: number) {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleSubmit() {
    if (files.length === 0) return;
    setSubmitting(true);
    setError(null);
    try {
      const job = await createJob(files);
      onJobCreated(job.job_id);
    } catch (err) {
      setError(err instanceof FinReconApiError ? err.message : "Upload failed. Is the backend running?");
      setSubmitting(false);
    }
  }

  return (
    <div>
      {error && <div className="error-banner">{error}</div>}
      <div
        className={`dropzone ${dragActive ? "active" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragActive(false);
          addFiles(e.dataTransfer.files);
        }}
      >
        <p style={{ margin: "0 0 12px", fontWeight: 600 }}>Drop financial data files here</p>
        <p style={{ margin: "0 0 16px", color: "var(--text-muted)", fontSize: 13 }}>
          CSV or Excel — orders, payments, settlements, or any datasets you want reconciled against each other.
        </p>
        <button className="ghost-button" onClick={() => inputRef.current?.click()}>
          Browse files
        </button>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".csv,.xlsx,.xls"
          style={{ display: "none" }}
          onChange={(e) => addFiles(e.target.files)}
        />
      </div>

      {files.length > 0 && (
        <ul className="file-list">
          {files.map((f, i) => (
            <li key={`${f.name}-${i}`}>
              <span>
                {f.name} <span style={{ color: "var(--text-muted)" }}>({(f.size / 1024).toFixed(1)} KB)</span>
              </span>
              <button className="ghost-button" style={{ padding: "2px 10px" }} onClick={() => removeFile(i)}>
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}

      <button className="primary-button" disabled={files.length === 0 || submitting} onClick={handleSubmit}>
        {submitting ? "Starting..." : "Start reconciliation"}
      </button>
    </div>
  );
}
