import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import type { GoFn } from "../App";
import {
  confirmReviewDraft,
  getIngestJob,
  ignoreReviewDraft,
  isReviewDraft,
  type ApiError,
} from "../api/ingest";
import { ReviewTableWorkspace } from "../components/review/ReviewTableWorkspace";
import type {
  ConfirmExtractionInvalidCell,
  ReviewCellPatch,
  ReviewDraft,
} from "../data/types";
import { I } from "../icons";
import { markCustomersChanged } from "../lib/customerRefresh";

export function ReviewScreen({
  go,
  params,
}: {
  go: GoFn;
  params?: Record<string, string>;
}) {
  const jobId = params?.jobId;
  const [draft, setDraft] = useState<ReviewDraft | null>(null);
  const [loading, setLoading] = useState<boolean>(Boolean(jobId));
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [invalidCells, setInvalidCells] = useState<ConfirmExtractionInvalidCell[]>([]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      if (!jobId) {
        setLoading(false);
        setError("没有可复核的上传任务");
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const job = await getIngestJob(jobId);
        if (cancelled) return;
        const nextDraft =
          job.review_draft ??
          (isReviewDraft(job.result_json) ? (job.result_json as ReviewDraft) : null);
        if (nextDraft) {
          setDraft(nextDraft);
          setLoading(false);
          return;
        }
        setError(
          job.status === "failed"
            ? job.error_message ?? "任务失败"
            : job.status === "canceled"
              ? "任务已取消"
              : "任务尚未生成草稿",
        );
      } catch (e) {
        if (!cancelled) {
          const apiErr = e as ApiError;
          setError(apiErr.message || "任务加载失败");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  async function handleSubmit(patches: ReviewCellPatch[]): Promise<void> {
    if (!draft || busy) return;
    setBusy(true);
    setError(null);
    setInvalidCells([]);
    try {
      const res = await confirmReviewDraft(draft.extraction_id, {
        review_draft: draft,
        patches,
      });
      if (res.invalid_cells && res.invalid_cells.length > 0) {
        setInvalidCells(res.invalid_cells);
        setError("部分字段未通过校验，请检查后再次提交");
        return;
      }
      markCustomersChanged();
      setDone(true);
    } catch (e) {
      const apiErr = e as ApiError;
      if (apiErr.detail && typeof apiErr.detail === "object") {
        const d = apiErr.detail as { invalid_cells?: ConfirmExtractionInvalidCell[] };
        if (Array.isArray(d.invalid_cells)) {
          setInvalidCells(d.invalid_cells);
        }
      }
      setError(apiErr.message || "归档失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleIgnore(): Promise<void> {
    if (!draft || busy) return;
    setBusy(true);
    setError(null);
    try {
      await ignoreReviewDraft(draft.extraction_id);
      go("upload");
    } catch (e) {
      const apiErr = e as ApiError;
      setError(apiErr.message || "忽略失败");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <CenteredScreen>
        <div style={{ color: "var(--ink-400)", fontSize: 14 }}>AI 整理中...</div>
      </CenteredScreen>
    );
  }

  if (draft && done) {
    return (
      <CenteredScreen>
        <div style={{ textAlign: "center", padding: 24 }}>
          <div
            style={{
              width: 72,
              height: 72,
              borderRadius: 36,
              margin: "0 auto 16px",
              background: "var(--ok-100)",
              color: "var(--ok-700)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {I.check(36)}
          </div>
          <div style={{ fontSize: 22, fontWeight: 700, color: "var(--ink-900)" }}>
            已确认入库
          </div>
          <div style={{ fontSize: 14, color: "var(--ink-500)", marginTop: 6 }}>
            {draft.document.filename}
          </div>
          <div style={{ display: "flex", gap: 8, justifyContent: "center", marginTop: 24 }}>
            <button className="btn btn-secondary" onClick={() => go("upload")}>
              继续上传
            </button>
            <button className="btn btn-primary" onClick={() => go("list")}>
              返回客户列表
            </button>
          </div>
        </div>
      </CenteredScreen>
    );
  }

  if (draft) {
    return (
      <ReviewTableWorkspace
        draft={draft}
        onSubmit={handleSubmit}
        onIgnore={handleIgnore}
        busy={busy}
        submitError={error}
        invalidCells={invalidCells}
      />
    );
  }

  return (
    <CenteredScreen>
      <div style={{ textAlign: "center", padding: 24 }}>
        <div style={{ fontSize: 18, fontWeight: 700, color: "var(--ink-900)", marginBottom: 8 }}>
          暂无待确认资料
        </div>
        <div style={{ color: "var(--ink-500)", fontSize: 13, marginBottom: 16 }}>
          {error ?? "上传资料后，AI 会生成可复核的表格草稿。"}
        </div>
        <button className="btn btn-primary" onClick={() => go("upload")}>
          {I.cloud(16, "#fff")}
          <span>上传资料</span>
        </button>
      </div>
    </CenteredScreen>
  );
}

function CenteredScreen({ children }: { children: ReactNode }) {
  return (
    <div
      className="screen"
      style={{
        background: "var(--bg)",
        alignItems: "center",
        justifyContent: "center",
        display: "flex",
      }}
    >
      {children}
    </div>
  );
}
