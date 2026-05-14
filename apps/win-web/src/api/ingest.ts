// Schema-first ingest client.
//
// Talks to /api/win/ingest/* and /api/win/company-schema. Uploads create
// schema-first ReviewDraft jobs; Review confirms table/cell payloads into
// company data tables.

import type {
  CompanySchema,
  ConfirmExtractionResponse,
  IngestJob,
  ReviewCellPatch,
  ReviewDraft,
} from "../data/types";

const API_BASE = "/api/win";

export type ApiError = Error & { status?: number; detail?: unknown };

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail: unknown = undefined;
    try {
      detail = await res.json();
    } catch {
      try {
        detail = await res.text();
      } catch {
        detail = undefined;
      }
    }
    const messageFromDetail =
      typeof detail === "string"
        ? detail
        : detail && typeof detail === "object" && "detail" in (detail as Record<string, unknown>)
          ? String((detail as Record<string, unknown>).detail)
          : res.statusText;
    const err: ApiError = new Error(messageFromDetail || `HTTP ${res.status}`);
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

export async function getReviewDraft(extractionId: string): Promise<ReviewDraft> {
  const res = await fetch(`${API_BASE}/ingest/extractions/${extractionId}`, {
    credentials: "include",
    cache: "no-store",
  });
  return jsonOrThrow(res);
}

export async function patchReviewDraft(
  extractionId: string,
  draft: ReviewDraft,
): Promise<ReviewDraft> {
  const res = await fetch(`${API_BASE}/ingest/extractions/${extractionId}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ review_draft: draft }),
  });
  return jsonOrThrow(res);
}

export async function confirmReviewDraft(
  extractionId: string,
  payload: { review_draft: ReviewDraft; patches: ReviewCellPatch[] },
): Promise<ConfirmExtractionResponse> {
  const res = await fetch(`${API_BASE}/ingest/extractions/${extractionId}/confirm`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return jsonOrThrow(res);
}

export async function ignoreReviewDraft(extractionId: string): Promise<{ status: string }> {
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
  status: "confirmed" | "failed" | "canceled";
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
