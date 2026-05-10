// POST /win/api/ingest/* — entity-first file intake.
//
// Routes per detected kind:
//   合同 (.pdf) → /contract           (returns draft + match candidates)
//   名片 (image) → /business_card     (creates Contact)
//   截图 (image) → /wechat_screenshot (ingests chat screenshot)
//
// Excel / 语音 / other types currently have no entity-first endpoint and
// return { ok: false, unsupported: true } so the UI can flag them without
// blocking the rest of the batch.

const API_BASE = "/win/api/ingest";

export type IngestSuccess = {
  ok: true;
  documentId: string;
  raw: unknown;
};

export type IngestFailure = {
  ok: false;
  error: string;
  unsupported?: boolean;
};

export type IngestResult = IngestSuccess | IngestFailure;

function endpointFor(kind: string): string | null {
  if (kind === "合同") return "/contract";
  if (kind === "名片") return "/business_card";
  if (kind === "截图") return "/wechat_screenshot";
  return null;
}

export async function uploadStagedFile(file: File, kind: string): Promise<IngestResult> {
  const endpoint = endpointFor(kind);
  if (!endpoint) {
    return { ok: false, error: "暂不支持该文件类型", unsupported: true };
  }
  const fd = new FormData();
  fd.append("file", file);
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: "POST",
      body: fd,
      credentials: "include",
    });
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const body = (await res.json()) as { detail?: string };
        if (typeof body?.detail === "string") detail = body.detail;
      } catch {
        /* response wasn't JSON */
      }
      return { ok: false, error: detail };
    }
    const body = (await res.json()) as { document_id?: string };
    return { ok: true, documentId: body.document_id ?? "", raw: body };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : "网络错误" };
  }
}
