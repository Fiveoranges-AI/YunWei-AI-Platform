import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import type { GoFn } from "../App";
import {
  acquireReviewLock,
  autosaveReview,
  confirmReviewDraft,
  deleteIngestJob,
  getIngestJob,
  getReview,
  type ApiError,
} from "../api/ingest";
import { ReviewWizard } from "../components/review/ReviewWizard";
import type {
  ConfirmExtractionInvalidCell,
  IngestJobStatus,
  ReviewCellPatch,
  ReviewDraft,
  ReviewLockMode,
  ReviewRowDecisionPatch,
} from "../data/types";
import { I } from "../icons";
import { markCustomersChanged } from "../lib/customerRefresh";

type LockState = {
  mode: ReviewLockMode;
  token: string | null;
  expiresAt: string | null;
  lockedBy: string | null;
};

const LOCK_REFRESH_INTERVAL_MS = 5 * 60 * 1000;

export function ReviewScreen({
  go,
  params,
}: {
  go: GoFn;
  params?: Record<string, string>;
}) {
  const jobId = params?.jobId;
  const [draft, setDraft] = useState<ReviewDraft | null>(null);
  const [extractionId, setExtractionId] = useState<string | null>(null);
  const [reviewVersion, setReviewVersion] = useState<number>(0);
  const [lock, setLock] = useState<LockState | null>(null);
  const [jobStatus, setJobStatus] = useState<IngestJobStatus | null>(null);
  const [jobContentType, setJobContentType] = useState<string | null>(null);
  const [hasFile, setHasFile] = useState<boolean>(false);
  const [confirmedBy, setConfirmedBy] = useState<string | null>(null);
  const [confirmedAt, setConfirmedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(Boolean(jobId));
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lockBanner, setLockBanner] = useState<string | null>(null);
  const [invalidCells, setInvalidCells] = useState<ConfirmExtractionInvalidCell[]>([]);
  const [fallbackDeleting, setFallbackDeleting] = useState(false);
  const [fallbackDeleteError, setFallbackDeleteError] = useState<string | null>(null);

  const draftRef = useRef<ReviewDraft | null>(null);
  draftRef.current = draft;
  const reviewVersionRef = useRef<number>(0);
  reviewVersionRef.current = reviewVersion;
  const lockRef = useRef<LockState | null>(null);
  lockRef.current = lock;
  const autosaveQueueRef = useRef<Promise<void>>(Promise.resolve());

  const reload = useCallback(
    async (extId: string): Promise<number | null> => {
      const env = await getReview(extId);
      if (env.review_draft) {
        setDraft(env.review_draft);
        const nextVersion = env.review_version ?? env.review_draft.review_version ?? 0;
        setReviewVersion(nextVersion);
        reviewVersionRef.current = nextVersion;
        return nextVersion;
      }
      return null;
    },
    [],
  );

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
        setJobStatus(job.status);
        setJobContentType(job.content_type ?? null);
        setHasFile(job.source_hint !== "pasted_text");

        const extId = job.extraction_id ?? null;
        if (!extId) {
          setError(
            job.status === "failed"
              ? displayJobError(job.error_message)
              : job.status === "canceled"
                ? "任务已取消"
                : "任务尚未生成草稿",
          );
          setLoading(false);
          return;
        }

        setExtractionId(extId);

        const envelope = await getReview(extId);
        if (cancelled) return;
        const nextDraft = envelope.review_draft;
        if (!nextDraft) {
          setError("草稿未就绪");
          setLoading(false);
          return;
        }
        setDraft(nextDraft);
        setReviewVersion(envelope.review_version ?? nextDraft.review_version ?? 0);
        setConfirmedBy(envelope.confirmed_by ?? null);
        setConfirmedAt(envelope.confirmed_at ?? null);

        // Acquire lock (best-effort). If draft is no longer pending or
        // someone else holds the lock we'll fall through to read-only.
        if (envelope.status === "pending_review" && job.status === "extracted") {
          try {
            const lockRes = await acquireReviewLock(extId);
            if (cancelled) return;
            setLock({
              mode: lockRes.mode,
              token: lockRes.lock_token ?? null,
              expiresAt: lockRes.lock_expires_at ?? null,
              lockedBy: lockRes.locked_by ?? null,
            });
            setReviewVersion(lockRes.review_version);
            if (lockRes.mode === "read_only") {
              setLockBanner(
                `${lockRes.locked_by ?? "他人"} 正在编辑，当前只读。`,
              );
            }
          } catch (e) {
            const apiErr = e as ApiError;
            setLockBanner(`获取锁失败：${apiErr.message ?? "未知错误"}，进入只读。`);
            setLock({
              mode: "read_only",
              token: null,
              expiresAt: null,
              lockedBy: null,
            });
          }
        } else {
          setLock({
            mode: "read_only",
            token: null,
            expiresAt: null,
            lockedBy: envelope.locked_by ?? null,
          });
        }
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

  const isReadOnly =
    !lock ||
    lock.mode !== "edit" ||
    !lock.token ||
    (jobStatus !== null && jobStatus !== "extracted") ||
    (draft !== null && draft.status !== "pending_review");

  useEffect(() => {
    if (!extractionId || !lock || lock.mode !== "edit" || !lock.token) return;

    const timer = window.setInterval(() => {
      void (async () => {
        try {
          const lockRes = await acquireReviewLock(extractionId);
          if (lockRes.mode !== "edit" || !lockRes.lock_token) {
            setLock({
              mode: "read_only",
              token: null,
              expiresAt: lockRes.lock_expires_at ?? null,
              lockedBy: lockRes.locked_by ?? null,
            });
            setLockBanner(
              `${lockRes.locked_by ?? "他人"} 正在编辑，当前只读。`,
            );
            return;
          }
          setLock({
            mode: "edit",
            token: lockRes.lock_token,
            expiresAt: lockRes.lock_expires_at ?? null,
            lockedBy: lockRes.locked_by ?? null,
          });
          setReviewVersion((prev) => Math.max(prev, lockRes.review_version));
        } catch (e) {
          const apiErr = e as ApiError;
          if (apiErr.status === 409) {
            setLock({
              mode: "read_only",
              token: null,
              expiresAt: null,
              lockedBy: lock.lockedBy,
            });
            setLockBanner("复核锁已失效，已切换为只读视图。");
            try {
              await reload(extractionId);
            } catch {
              // The lock banner already explains why editing stopped.
            }
          } else {
            setLockBanner(`锁续期失败：${apiErr.message || "网络异常"}`);
          }
        }
      })();
    }, LOCK_REFRESH_INTERVAL_MS);

    return () => window.clearInterval(timer);
  }, [extractionId, lock?.mode, lock?.token, lock?.lockedBy, reload]);

  const runAutosave = useCallback(
    async (payload: {
      cell?: ReviewCellPatch;
      row?: ReviewRowDecisionPatch;
    }) => {
      const currentLock = lockRef.current;
      const extId = extractionId;
      if (!extId || !currentLock || currentLock.mode !== "edit" || !currentLock.token) {
        return;
      }
      const lockToken = currentLock.token;
      const request = (baseVersion: number) => ({
        lock_token: lockToken,
        base_version: baseVersion,
        cell_patches: payload.cell ? [payload.cell] : [],
        row_patches: payload.row ? [payload.row] : [],
      });
      const applyResponse = (res: Awaited<ReturnType<typeof autosaveReview>>) => {
        if (res.review_draft) {
          setDraft(res.review_draft);
        }
        setReviewVersion(res.review_version);
        // Sync the ref now — the next queued autosave runs in a microtask
        // and would otherwise read the stale value before React re-renders.
        reviewVersionRef.current = res.review_version;
        setLock((prev) =>
          prev
            ? {
                ...prev,
                expiresAt: res.lock_expires_at ?? prev.expiresAt,
              }
            : prev,
        );
      };
      try {
        const res = await autosaveReview(extId, request(reviewVersionRef.current));
        applyResponse(res);
      } catch (e) {
        const apiErr = e as ApiError;
        if (apiErr.status === 409 && isReviewVersionMismatch(apiErr)) {
          try {
            const nextVersion = await reload(extId);
            if (nextVersion !== null) {
              const retryRes = await autosaveReview(extId, request(nextVersion));
              applyResponse(retryRes);
              return;
            }
          } catch {
            // Fall through to conservative read-only handling below.
          }
        }
        if (apiErr.status === 409) {
          setLockBanner(
            "草稿被他人改动或锁已失效，已刷新为只读视图。",
          );
          setLock({
            mode: "read_only",
            token: null,
            expiresAt: null,
            lockedBy: currentLock.lockedBy,
          });
          if (extId) {
            try {
              await reload(extId);
            } catch {
              // swallowed — banner already explains the conflict.
            }
          }
        } else {
          setError(apiErr.message || "保存失败");
        }
      }
    },
    [extractionId, reload],
  );

  const enqueueAutosave = useCallback(
    (payload: { cell?: ReviewCellPatch; row?: ReviewRowDecisionPatch }) => {
      autosaveQueueRef.current = autosaveQueueRef.current
        .catch(() => undefined)
        .then(() => runAutosave(payload));
      void autosaveQueueRef.current;
    },
    [runAutosave],
  );

  function handleCellPatch(patch: ReviewCellPatch) {
    enqueueAutosave({ cell: patch });
  }
  function handleRowPatch(patch: ReviewRowDecisionPatch) {
    enqueueAutosave({ row: patch });
  }

  async function handleConfirm(): Promise<void> {
    if (!draft || !extractionId || busy) return;
    if (!lock || lock.mode !== "edit" || !lock.token) {
      setError("当前为只读，无法提交。");
      return;
    }
    setBusy(true);
    setError(null);
    setInvalidCells([]);
    try {
      await autosaveQueueRef.current.catch(() => undefined);
      const currentLock = lockRef.current;
      if (!currentLock || currentLock.mode !== "edit" || !currentLock.token) {
        setError("当前为只读，无法提交。");
        return;
      }
      const res = await confirmReviewDraft(extractionId, {
        lock_token: currentLock.token,
        base_version: reviewVersionRef.current,
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
      if (
        apiErr.detail &&
        typeof apiErr.detail === "object" &&
        "invalid_cells" in (apiErr.detail as Record<string, unknown>)
      ) {
        const cells = (apiErr.detail as { invalid_cells?: unknown }).invalid_cells;
        if (Array.isArray(cells)) {
          setInvalidCells(cells as ConfirmExtractionInvalidCell[]);
        }
      }
      if (apiErr.status === 409) {
        setLockBanner("锁或版本不匹配，已刷新为只读视图。");
        setLock({
          mode: "read_only",
          token: null,
          expiresAt: null,
          lockedBy: lock.lockedBy,
        });
        if (extractionId) {
          try {
            await reload(extractionId);
          } catch {
            // swallow
          }
        }
      }
      setError(apiErr.message || "归档失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(): Promise<void> {
    if (!jobId) throw new Error("no job id");
    await deleteIngestJob(jobId);
    go("inbox");
  }

  async function handleFallbackDelete(): Promise<void> {
    if (!jobId || fallbackDeleting) return;
    if (!window.confirm("确定删除？删除后不可恢复。")) return;
    setFallbackDeleting(true);
    setFallbackDeleteError(null);
    try {
      await deleteIngestJob(jobId);
      go("inbox");
    } catch (e) {
      const apiErr = e as ApiError;
      if (apiErr.status === 409) {
        setFallbackDeleteError("当前状态不支持删除");
      } else {
        setFallbackDeleteError(apiErr.message || "删除失败");
      }
    } finally {
      setFallbackDeleting(false);
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
    const originalFileUrl = hasFile && jobId ? `/api/win/ingest/jobs/${jobId}/file` : null;
    const finalizedKind: "confirmed" | "failed" | "canceled" | null =
      jobStatus === "confirmed"
        ? "confirmed"
        : jobStatus === "failed"
          ? "failed"
          : jobStatus === "canceled"
            ? "canceled"
            : null;
    const finalized = finalizedKind !== null;
    return (
      <ReviewWizard
        draft={draft}
        readOnly={isReadOnly}
        finalized={finalized}
        finalizedKind={finalizedKind}
        finalizedAt={confirmedAt}
        finalizedBy={confirmedBy}
        busy={busy}
        error={error}
        invalidCells={invalidCells}
        onCellPatch={handleCellPatch}
        onRowPatch={handleRowPatch}
        onConfirm={handleConfirm}
        onDelete={finalized ? undefined : handleDelete}
        sourceText={draft.document.source_text ?? null}
        originalFileUrl={originalFileUrl}
        originalFileContentType={jobContentType}
        lockBanner={lockBanner}
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
        <div style={{ display: "flex", gap: 8, justifyContent: "center", flexWrap: "wrap" }}>
          <button className="btn btn-primary" onClick={() => go("upload")}>
            {I.cloud(16, "#fff")}
            <span>上传资料</span>
          </button>
          {jobId ? (
            <button
              className="btn btn-secondary"
              onClick={handleFallbackDelete}
              disabled={fallbackDeleting}
              style={{ color: "var(--risk-700)" }}
            >
              <span>{fallbackDeleting ? "删除中…" : "删除此任务"}</span>
            </button>
          ) : null}
        </div>
        {fallbackDeleteError ? (
          <div style={{ color: "var(--risk-700)", fontSize: 12, marginTop: 12 }}>
            {fallbackDeleteError}
          </div>
        ) : null}
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

function isReviewVersionMismatch(err: ApiError): boolean {
  const detail =
    typeof err.detail === "string"
      ? err.detail
      : typeof err.message === "string"
        ? err.message
        : "";
  return detail.startsWith("review_version mismatch");
}

function displayJobError(message: string | null | undefined): string {
  if (!message) return "任务失败";
  return message.replace(
    /\b[A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*\b/g,
    "凭证",
  );
}
