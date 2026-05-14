// V2 schema-first ingest client.
//
// Talks to /api/win/ingest/v2/* and /api/win/company-schema. Mirrors the
// V1 (api/ingest.ts) request style — `credentials: "include"`, FormData
// for uploads, JSON for everything else, structured errors with status
// + parsed detail.

import type {
  CompanySchema,
  ConfirmExtractionResponse,
  IngestV2Job,
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

export async function createIngestV2Jobs(
  files: File[],
  opts: { sourceHint?: string; uploader?: string; textContent?: string } = {},
): Promise<{ batch_id: string; jobs: IngestV2Job[] }> {
  const form = new FormData();
  for (const f of files) form.append("files", f);
  if (opts.sourceHint) form.append("source_hint", opts.sourceHint);
  if (opts.uploader) form.append("uploader", opts.uploader);
  if (opts.textContent) form.append("text", opts.textContent);
  const res = await fetch(`${API_BASE}/ingest/v2/jobs`, {
    method: "POST",
    body: form,
    credentials: "include",
  });
  return jsonOrThrow(res);
}

export async function listIngestV2Jobs(
  status: "active" | "history" | "all" = "active",
  limit = 50,
): Promise<IngestV2Job[]> {
  const res = await fetch(`${API_BASE}/ingest/v2/jobs?status=${status}&limit=${limit}`, {
    credentials: "include",
    cache: "no-store",
  });
  return jsonOrThrow(res);
}

export async function getIngestV2Job(jobId: string): Promise<IngestV2Job> {
  const res = await fetch(`${API_BASE}/ingest/v2/jobs/${jobId}`, {
    credentials: "include",
    cache: "no-store",
  });
  return jsonOrThrow(res);
}

export async function getReviewDraft(extractionId: string): Promise<ReviewDraft> {
  const res = await fetch(`${API_BASE}/ingest/v2/extractions/${extractionId}`, {
    credentials: "include",
    cache: "no-store",
  });
  return jsonOrThrow(res);
}

export async function patchReviewDraft(
  extractionId: string,
  draft: ReviewDraft,
): Promise<ReviewDraft> {
  const res = await fetch(`${API_BASE}/ingest/v2/extractions/${extractionId}`, {
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
  const res = await fetch(`${API_BASE}/ingest/v2/extractions/${extractionId}/confirm`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return jsonOrThrow(res);
}

export async function ignoreReviewDraft(extractionId: string): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/ingest/v2/extractions/${extractionId}/ignore`, {
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

export async function retryIngestV2Job(jobId: string): Promise<IngestV2Job> {
  const res = await fetch(`${API_BASE}/ingest/v2/jobs/${jobId}/retry`, {
    method: "POST",
    credentials: "include",
  });
  return jsonOrThrow(res);
}

export async function cancelIngestV2Job(jobId: string): Promise<IngestV2Job> {
  const res = await fetch(`${API_BASE}/ingest/v2/jobs/${jobId}/cancel`, {
    method: "POST",
    credentials: "include",
  });
  return jsonOrThrow(res);
}

/** Narrow check used by Review.tsx to branch on V1 vs V2 result_json. */
export function isReviewDraft(value: unknown): value is ReviewDraft {
  return (
    typeof value === "object" &&
    value !== null &&
    Array.isArray((value as { tables?: unknown }).tables)
  );
}
