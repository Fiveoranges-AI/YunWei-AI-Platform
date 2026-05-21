// Thin client for /api/win/confirm — P0 task ③ candidate writeback.

import type {
  ConfirmEntitiesRequest,
  ConfirmEntitiesResponse,
} from "../data/candidate";

const API_BASE = "/api/win";

export type ConfirmApiError = Error & { status?: number; detail?: unknown };

export async function confirmEntities(
  payload: ConfirmEntitiesRequest,
): Promise<ConfirmEntitiesResponse> {
  const res = await fetch(`${API_BASE}/confirm/entities`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let detail: unknown;
    try {
      const body = (await res.json()) as { detail?: unknown };
      detail = body?.detail ?? body;
    } catch {
      try {
        detail = await res.text();
      } catch {
        detail = undefined;
      }
    }
    const message =
      typeof detail === "string" ? detail : res.statusText || `HTTP ${res.status}`;
    const err: ConfirmApiError = new Error(message);
    err.status = res.status;
    err.detail = detail;
    throw err;
  }
  return (await res.json()) as ConfirmEntitiesResponse;
}
