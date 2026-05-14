// Schema-first ingest client.
//
// Talks to /api/win/ingest/* and /api/win/company-schema. Uploads create
// schema-first ReviewDraft jobs; Review confirms table/cell payloads into
// company data tables.

import type {
  AcquireReviewLockResponse,
  AutosaveReviewRequest,
  AutosaveReviewResponse,
  CompanySchema,
  ConfirmExtractionRequest,
  ConfirmExtractionResponse,
  ExtractionEnvelope,
  IngestJob,
  ReviewCellPatch,
  ReviewDraft,
} from "../data/types";

const API_BASE = "/api/win";

export type ApiError = Error & { status?: number; detail?: unknown };

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let body: unknown = undefined;
    try {
      body = await res.json();
    } catch {
      try {
        body = await res.text();
      } catch {
        body = undefined;
      }
    }
    // FastAPI wraps error payloads in {"detail": ...}. Unwrap so callers can
    // read err.detail directly (it may be a string, object, or array).
    let detail: unknown = body;
    if (
      body !== null &&
      typeof body === "object" &&
      "detail" in (body as Record<string, unknown>)
    ) {
      detail = (body as Record<string, unknown>).detail;
    }
    let message: string;
    if (typeof detail === "string") {
      message = detail;
    } else if (
      detail &&
      typeof detail === "object" &&
      "message" in (detail as Record<string, unknown>) &&
      typeof (detail as Record<string, unknown>).message === "string"
    ) {
      message = String((detail as Record<string, unknown>).message);
    } else {
      message = res.statusText || `HTTP ${res.status}`;
    }
    const err: ApiError = new Error(message);
    err.status = res.status;
    err.detail = detail;
    throw err;
  }
  return (await res.json()) as T;
}

export async function createIngestJobs(
  files: File[],
  opts: { sourceHint?: string; uploader?: string; textContent?: string } = {},
): Promise<{ batch_id: string; jobs: IngestJob[] }> {
  const form = new FormData();
  for (const f of files) form.append("files", f);
  if (opts.sourceHint) form.append("source_hint", opts.sourceHint);
  if (opts.uploader) form.append("uploader", opts.uploader);
  if (opts.textContent) form.append("text", opts.textContent);
  const res = await fetch(`${API_BASE}/ingest/jobs`, {
    method: "POST",
    body: form,
    credentials: "include",
  });
  return jsonOrThrow(res);
}

export async function listIngestJobs(
  status: "active" | "history" | "all" = "active",
  limit = 50,
): Promise<IngestJob[]> {
  const res = await fetch(`${API_BASE}/ingest/jobs?status=${status}&limit=${limit}`, {
    credentials: "include",
    cache: "no-store",
  });
  return jsonOrThrow(res);
}

export async function getIngestJob(jobId: string): Promise<IngestJob> {
  const res = await fetch(`${API_BASE}/ingest/jobs/${jobId}`, {
    credentials: "include",
    cache: "no-store",
  });
  return jsonOrThrow(res);
}

// vNext review surface ------------------------------------------------------

export async function getReview(extractionId: string): Promise<ExtractionEnvelope> {
  const res = await fetch(
    `${API_BASE}/ingest/extractions/${extractionId}/review`,
    { credentials: "include", cache: "no-store" },
  );
  return jsonOrThrow(res);
}

export async function acquireReviewLock(
  extractionId: string,
): Promise<AcquireReviewLockResponse> {
  const res = await fetch(
    `${API_BASE}/ingest/extractions/${extractionId}/review/lock`,
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
    },
  );
  return jsonOrThrow(res);
}

export async function autosaveReview(
  extractionId: string,
  payload: AutosaveReviewRequest,
): Promise<AutosaveReviewResponse> {
  const res = await fetch(
    `${API_BASE}/ingest/extractions/${extractionId}/review`,
    {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  return jsonOrThrow(res);
}

export async function confirmReviewDraft(
  extractionId: string,
  payload: ConfirmExtractionRequest,
): Promise<ConfirmExtractionResponse> {
  const res = await fetch(`${API_BASE}/ingest/extractions/${extractionId}/confirm`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return jsonOrThrow(res);
}

// Legacy aliases — older callers (old Review.tsx, dev tools) may still
// import these. They hit the same generic GET / PATCH /extractions/{id}
// path the backend keeps around as a compat alias. Prefer ``getReview``
// + autosaveReview for vNext flows.

export async function getReviewDraft(extractionId: string): Promise<ExtractionEnvelope> {
  const res = await fetch(`${API_BASE}/ingest/extractions/${extractionId}`, {
    credentials: "include",
    cache: "no-store",
  });
  return jsonOrThrow(res);
}

export async function patchReviewDraft(
  extractionId: string,
  draft: ReviewDraft,
): Promise<ExtractionEnvelope> {
  const res = await fetch(`${API_BASE}/ingest/extractions/${extractionId}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ review_draft: draft }),
  });
  return jsonOrThrow(res);
}

// Re-export ReviewCellPatch so consumers that import { ReviewCellPatch }
// from this module continue to compile.
export type { ReviewCellPatch };

export async function ignoreReviewDraft(extractionId: string): Promise<ExtractionEnvelope> {
  const res = await fetch(`${API_BASE}/ingest/extractions/${extractionId}/ignore`, {
    method: "POST",
    credentials: "include",
  });
  return jsonOrThrow(res);
}

export async function getCompanySchema(): Promise<CompanySchema> {
  const res = await fetch(`${API_BASE}/company-schema`, {
    credentials: "include",
    cache: "no-store",
  });
  return jsonOrThrow(res);
}

export async function retryIngestJob(jobId: string): Promise<IngestJob> {
  const res = await fetch(`${API_BASE}/ingest/jobs/${jobId}/retry`, {
    method: "POST",
    credentials: "include",
  });
  return jsonOrThrow(res);
}

export async function cancelIngestJob(jobId: string): Promise<IngestJob> {
  const res = await fetch(`${API_BASE}/ingest/jobs/${jobId}/cancel`, {
    method: "POST",
    credentials: "include",
  });
  return jsonOrThrow(res);
}

export type DeleteIngestJobResult = {
  deleted: number;
  job_id: string;
  status: "confirmed" | "failed" | "canceled" | "extracted";
};

export async function deleteIngestJob(jobId: string): Promise<DeleteIngestJobResult> {
  const res = await fetch(`${API_BASE}/ingest/jobs/${jobId}`, {
    method: "DELETE",
    credentials: "include",
  });
  return jsonOrThrow(res);
}

export function isReviewDraft(value: unknown): value is ReviewDraft {
  return (
    typeof value === "object" &&
    value !== null &&
    Array.isArray((value as { tables?: unknown }).tables)
  );
}
