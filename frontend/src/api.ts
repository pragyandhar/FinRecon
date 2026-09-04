import type { ApiError, Job, Report, ReconciliationResult } from "./types";

class FinReconApiError extends Error {
  code: string;
  details: Record<string, unknown>;

  constructor(err: ApiError) {
    super(err.message);
    this.code = err.code;
    this.details = err.details;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ApiError | null;
    if (body?.code) throw new FinReconApiError(body);
    throw new Error(`Request to ${path} failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function createJob(files: File[]): Promise<Job> {
  const form = new FormData();
  for (const file of files) form.append("files", file);
  return request<Job>("/reconciliation/jobs", { method: "POST", body: form });
}

export function getJob(jobId: string): Promise<Job> {
  return request<Job>(`/reconciliation/jobs/${jobId}`);
}

export function getResults(jobId: string, status?: string): Promise<ReconciliationResult[]> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : "";
  return request<ReconciliationResult[]>(`/reconciliation/jobs/${jobId}/results${qs}`);
}

export function getReport(jobId: string): Promise<Report> {
  return request<Report>(`/reconciliation/jobs/${jobId}/report`);
}

export function askChat(
  jobId: string,
  message: string,
  recordId?: string,
  sessionId?: string,
): Promise<{ session_id: string; reply: string; context_used: string[] }> {
  return request(`/reconciliation/jobs/${jobId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, record_id: recordId, session_id: sessionId }),
  });
}

export { FinReconApiError };
