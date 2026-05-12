import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from "react";
import type { GoFn } from "../App";
import {
  cancelIngestJob,
  clearIngestHistory,
  createIngestJobs,
  listIngestJobs,
  retryIngestJob,
  type IngestJob,
  type IngestJobStage,
  type IngestJobStatus,
} from "../api/ingest";
import { I } from "../icons";
import { useIsDesktop } from "../lib/breakpoints";
import { fmtRelative } from "../lib/format";
import { markCustomersChanged } from "../lib/customerRefresh";

type StagedSourceHint = "file" | "camera";

type StagedFile = {
  id: string;
  name: string;
  sourceHint: StagedSourceHint;
  blob: File;
  previewUrl?: string; // object URL for image previews; revoked on remove/unmount
};

const ACTIVE_POLL_MS = 2500;
const IDLE_POLL_MS = 6000;
const ERROR_POLL_MS = 5000;

export function UploadScreen({ go }: { go: GoFn }) {
  const isDesktop = useIsDesktop();
  const [pasted, setPasted] = useState("");
  const [files, setFiles] = useState<StagedFile[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [lightbox, setLightbox] = useState<string | null>(null);
  const [activeJobs, setActiveJobs] = useState<IngestJob[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [historyJobs, setHistoryJobs] = useState<IngestJob[]>([]);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [clearingHistory, setClearingHistory] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);

  function addFile(blob: File, sourceHint: StagedSourceHint) {
    const previewUrl = blob.type.startsWith("image/")
      ? URL.createObjectURL(blob)
      : undefined;
    setFiles((f) => [
      ...f,
      {
        id: Math.random().toString(36).slice(2),
        name: blob.name,
        sourceHint,
        blob,
        previewUrl,
      },
    ]);
  }
  function removeFile(id: string) {
    setFiles((f) => {
      const target = f.find((x) => x.id === id);
      if (target?.previewUrl) URL.revokeObjectURL(target.previewUrl);
      return f.filter((x) => x.id !== id);
    });
  }

  // Free any unrevoked object URLs when the screen unmounts (tab switch, etc.).
  useEffect(() => {
    return () => {
      setFiles((current) => {
        for (const f of current) if (f.previewUrl) URL.revokeObjectURL(f.previewUrl);
        return current;
      });
    };
  }, []);

  // Poll active jobs while mounted. Cadence speeds up while anything is
  // queued/running and slows when the queue is idle. Stops on unmount.
  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    async function tick() {
      try {
        const rows = await listIngestJobs("active", 50);
        if (cancelled) return;
        setActiveJobs(rows);
        const hasInFlight = rows.some(
          (j) => j.status === "queued" || j.status === "running",
        );
        timer = window.setTimeout(tick, hasInFlight ? ACTIVE_POLL_MS : IDLE_POLL_MS);
      } catch {
        if (cancelled) return;
        timer = window.setTimeout(tick, ERROR_POLL_MS);
      }
    }
    void tick();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, []);

  // History is lazy — only fetched once the user opens the panel.
  useEffect(() => {
    if (!showHistory) return;
    let cancelled = false;
    setHistoryError(null);
    listIngestJobs("history", 50)
      .then((rows) => {
        if (!cancelled) setHistoryJobs(rows);
      })
      .catch((e) => {
        if (!cancelled) {
          setHistoryError(e instanceof Error ? e.message : "历史加载失败");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [showHistory]);

  function handlePicked(e: ChangeEvent<HTMLInputElement>, sourceHint: StagedSourceHint) {
    const list = e.target.files;
    if (list) {
      for (const f of Array.from(list)) {
        addFile(f, sourceHint);
      }
    }
    // Reset so picking the same file twice in a row still fires onChange.
    e.target.value = "";
  }

  function onDragOver(e: DragEvent<HTMLDivElement>) {
    if (!e.dataTransfer.types.includes("Files")) return;
    e.preventDefault();
    e.stopPropagation();
    if (!dragActive) setDragActive(true);
  }
  function onDragLeave(e: DragEvent<HTMLDivElement>) {
    // Only reset when leaving the drop-zone container — child element drags
    // would otherwise toggle dragActive on every hover transition.
    const next = e.relatedTarget as Node | null;
    if (next && (e.currentTarget as HTMLElement).contains(next)) return;
    setDragActive(false);
  }
  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const dropped = Array.from(e.dataTransfer.files ?? []);
    for (const f of dropped) {
      addFile(f, "file");
    }
  }

  async function refreshActive() {
    try {
      const rows = await listIngestJobs("active", 50);
      setActiveJobs(rows);
    } catch {
      /* swallow — next poll tick will recover */
    }
  }

  async function refreshHistory() {
    if (!showHistory) return;
    try {
      const rows = await listIngestJobs("history", 50);
      setHistoryJobs(rows);
    } catch {
      /* swallow */
    }
  }

  async function handleSubmit() {
    if (submitting) return;
    const trimmedText = pasted.trim();
    const hasFiles = files.length > 0;
    const hasText = trimmedText.length > 0;
    if (!hasFiles && !hasText) return;

    setSubmitting(true);
    setSubmitError(null);
    try {
      // Source hint is per-batch in the job API. When a camera capture is
      // mixed in with regular files we still tag the batch as "file" — the
      // backend uses source_hint loosely for routing/storage.
      const anyCamera = files.some((f) => f.sourceHint === "camera");
      const onlyText = !hasFiles && hasText;
      const sourceHint: "file" | "camera" | "pasted_text" = onlyText
        ? "pasted_text"
        : anyCamera && !files.some((f) => f.sourceHint !== "camera")
          ? "camera"
          : "file";

      await createIngestJobs({
        files: files.map((f) => f.blob),
        text: hasText ? trimmedText : undefined,
        sourceHint,
      });

      // Clear staged inputs — the jobs now live in activeJobs / polling.
      for (const f of files) if (f.previewUrl) URL.revokeObjectURL(f.previewUrl);
      setFiles([]);
      setPasted("");

      // Nudge the customer cache so the list refreshes once the user finishes
      // the Review archive flow without an extra round-trip.
      markCustomersChanged();

      // Pull the latest active list immediately so the new cards appear
      // without waiting for the next poll tick.
      await refreshActive();
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "上传失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function onJobView(j: IngestJob) {
    go("review", { jobId: j.id });
  }

  async function onJobRetry(j: IngestJob) {
    try {
      await retryIngestJob(j.id);
      await refreshActive();
      await refreshHistory();
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "重试失败");
    }
  }

  async function onJobCancel(j: IngestJob) {
    try {
      await cancelIngestJob(j.id);
      await refreshActive();
      await refreshHistory();
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "取消失败");
    }
  }

  async function onClearFailedHistory() {
    if (clearingHistory) return;
    if (!window.confirm("确定要清空所有失败的历史任务吗？该操作不可撤销。已成功归档的任务不会被删除。")) return;
    setClearingHistory(true);
    setHistoryError(null);
    try {
      await clearIngestHistory("failed");
      await refreshHistory();
    } catch (e) {
      setHistoryError(e instanceof Error ? e.message : "清空失败");
    } finally {
      setClearingHistory(false);
    }
  }

  const total = files.length + (pasted.trim() ? 1 : 0);
  const ready = total > 0;

  return (
    <div
      className="screen"
      style={{ background: "var(--bg)" }}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,image/*"
        onChange={(e) => handlePicked(e, "file")}
        style={{ display: "none" }}
      />
      <input
        ref={cameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        onChange={(e) => handlePicked(e, "camera")}
        style={{ display: "none" }}
      />
      {/* Top bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: isDesktop ? "16px 32px 8px" : "6px 16px 8px",
          maxWidth: isDesktop ? 920 : undefined,
          width: "100%",
          margin: "0 auto",
        }}
      >
        <div style={{ fontSize: 15, fontWeight: 600, color: "var(--ink-700)" }}>添加客户资料</div>
        <button
          onClick={() => go("list")}
          style={{
            width: 36,
            height: 36,
            borderRadius: 18,
            background: "transparent",
            border: "none",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--ink-500)",
            cursor: "pointer",
          }}
        >
          {I.close(20)}
        </button>
      </div>

      <div
        className="scroll"
        style={{
          flex: 1,
          padding: isDesktop ? "0 32px 24px" : "0 16px 16px",
          maxWidth: isDesktop ? 920 : undefined,
          width: "100%",
          margin: "0 auto",
        }}
      >
        {/* Intro */}
        <div style={{ padding: "6px 0 14px" }}>
          <div
            style={{
              fontSize: isDesktop ? 32 : 26,
              fontWeight: 700,
              color: "var(--ink-900)",
              letterSpacing: "-0.01em",
              lineHeight: 1.2,
            }}
          >
            把客户资料丢进来
          </div>
          <div style={{ fontSize: 14, color: "var(--ink-600)", marginTop: 6, lineHeight: 1.5 }}>
            合同、名片、微信截图、聊天记录、送货单、语音备注……
            <span style={{ color: "var(--ai-500)", fontWeight: 600 }}> AI 会自动分类、整理</span>
            ，再由你确认归档。
          </div>
        </div>

        {/* Primary actions */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: isDesktop ? "1fr 1fr 2fr" : "1fr 1fr",
            gap: 10,
            marginBottom: 12,
          }}
        >
          <button
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              textAlign: "center",
              cursor: "pointer",
              background: dragActive ? "var(--brand-50)" : "var(--surface)",
              border: dragActive ? "2px solid var(--brand-500)" : "2px dashed var(--brand-300)",
              borderRadius: 18,
              padding: "20px 12px",
              minHeight: 156,
              transition: "background 120ms ease, border-color 120ms ease",
            }}
            onClick={() => fileInputRef.current?.click()}
          >
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: 14,
                background: "var(--brand-50)",
                color: "var(--brand-500)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                marginBottom: 10,
              }}
            >
              {I.cloud(24)}
            </div>
            <div style={{ fontSize: 15, fontWeight: 700, color: "var(--ink-900)" }}>
              {dragActive ? "松开放下" : "上传文件"}
            </div>
            <div style={{ fontSize: 11, color: "var(--ink-500)", marginTop: 4, lineHeight: 1.45 }}>
              {dragActive ? "拖到这里直接添加" : "合同 · 截图 · Excel · 拖拽"}
            </div>
          </button>

          <button
            className="card"
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              textAlign: "center",
              cursor: "pointer",
              padding: "20px 12px",
              minHeight: 156,
            }}
            onClick={() => cameraInputRef.current?.click()}
          >
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: 14,
                background: "var(--surface-3)",
                color: "var(--ink-700)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                marginBottom: 10,
              }}
            >
              {I.camera(22)}
            </div>
            <div style={{ fontSize: 15, fontWeight: 700, color: "var(--ink-900)" }}>拍照</div>
            <div style={{ fontSize: 11, color: "var(--ink-500)", marginTop: 4, lineHeight: 1.45 }}>合同 · 名片</div>
          </button>

          {/* Desktop: paste area inline as third column */}
          {isDesktop && <PasteArea pasted={pasted} setPasted={setPasted} compact />}
        </div>

        {/* Staged items — sit between the action buttons (上传/拍照) and the
            paste area (文字输入). After submit they move into the task panel
            below. */}
        {(files.length > 0 || pasted.trim()) && (
          <div style={{ marginBottom: 12 }}>
            <div className="sec-h">
              <h3>待提交 {total} 项</h3>
            </div>
            {files.map((f) => {
              const icon = iconForFile(f);
              return (
                <div
                  key={f.id}
                  className="card"
                  style={{ padding: 12, marginBottom: 8, display: "flex", alignItems: "center", gap: 12 }}
                >
                  {f.previewUrl ? (
                    <button
                      onClick={() => f.previewUrl && setLightbox(f.previewUrl)}
                      aria-label={`查看 ${f.name}`}
                      style={{
                        width: 48,
                        height: 48,
                        borderRadius: 10,
                        overflow: "hidden",
                        padding: 0,
                        border: "1px solid var(--ink-100)",
                        background: "var(--surface-3)",
                        flexShrink: 0,
                        cursor: "zoom-in",
                      }}
                    >
                      <img
                        src={f.previewUrl}
                        alt=""
                        style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
                      />
                    </button>
                  ) : (
                    <div
                      style={{
                        width: 32,
                        height: 32,
                        borderRadius: 10,
                        background: "var(--surface-3)",
                        color: "var(--ink-600)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        flexShrink: 0,
                      }}
                    >
                      {icon}
                    </div>
                  )}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: 13,
                        fontWeight: 600,
                        color: "var(--ink-900)",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {f.name}
                    </div>
                    <div
                      style={{
                        fontSize: 11,
                        color: "var(--ink-500)",
                        marginTop: 2,
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                      }}
                    >
                      <span>{describeSourceHint(f.sourceHint, f.blob)}</span>
                      <span className="pill pill-ai" style={{ fontSize: 10, padding: "1px 6px" }}>
                        {I.spark(9)} 待 AI 整理
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={() => removeFile(f.id)}
                    disabled={submitting}
                    style={{
                      background: "transparent",
                      border: "none",
                      cursor: submitting ? "not-allowed" : "pointer",
                      color: "var(--ink-400)",
                      opacity: submitting ? 0.4 : 1,
                    }}
                  >
                    {I.close(16)}
                  </button>
                </div>
              );
            })}
            {pasted.trim() && (
              <div className="card" style={{ padding: 12, display: "flex", alignItems: "flex-start", gap: 12 }}>
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 10,
                    background: "var(--surface-3)",
                    color: "var(--ink-600)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  {I.chat(16)}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "var(--ink-900)" }}>
                    粘贴文本 · {pasted.length} 字
                  </div>
                  <div
                    style={{
                      fontSize: 11,
                      color: "var(--ink-500)",
                      marginTop: 2,
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                    }}
                  >
                    <span>{pasted.slice(0, 24)}…</span>
                    <span className="pill pill-ai" style={{ fontSize: 10, padding: "1px 6px" }}>
                      {I.spark(9)} 待 AI 整理
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => setPasted("")}
                  disabled={submitting}
                  style={{
                    background: "transparent",
                    border: "none",
                    cursor: submitting ? "not-allowed" : "pointer",
                    color: "var(--ink-400)",
                    opacity: submitting ? 0.4 : 1,
                  }}
                >
                  {I.close(16)}
                </button>
              </div>
            )}
          </div>
        )}

        {/* Mobile: paste area below */}
        {!isDesktop && <PasteArea pasted={pasted} setPasted={setPasted} compact={false} />}

        {submitError && (
          <div
            style={{
              marginBottom: 12,
              padding: "10px 12px",
              borderRadius: 10,
              border: "1px solid var(--risk-100)",
              background: "#fff1f0",
              color: "var(--risk-500)",
              fontSize: 12,
              lineHeight: 1.5,
            }}
          >
            {submitError}
          </div>
        )}

        {/* Job list — active + (optional) history */}
        <div style={{ marginTop: 16 }}>
          <div
            style={{
              display: "flex",
              alignItems: "baseline",
              justifyContent: "space-between",
              marginBottom: 8,
            }}
          >
            <h3 style={{ fontSize: 13, fontWeight: 700, color: "var(--ink-700)", margin: 0 }}>
              正在处理{activeJobs.length > 0 ? ` (${activeJobs.length})` : ""}
            </h3>
            <button
              onClick={() => setShowHistory((v) => !v)}
              style={{
                fontSize: 11,
                color: "var(--ink-500)",
                background: "transparent",
                border: "none",
                cursor: "pointer",
                textDecoration: "underline",
                padding: 0,
              }}
            >
              {showHistory ? "隐藏历史" : "查看历史"}
            </button>
          </div>

          {activeJobs.length === 0 && (
            <div
              className="card"
              style={{
                padding: 14,
                fontSize: 12,
                color: "var(--ink-500)",
                textAlign: "center",
              }}
            >
              暂无正在处理的任务
            </div>
          )}
          {activeJobs.map((j) => (
            <JobCard
              key={j.id}
              job={j}
              onView={onJobView}
              onRetry={onJobRetry}
              onCancel={onJobCancel}
            />
          ))}

          {showHistory && (
            <div style={{ marginTop: 12 }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  margin: "0 0 8px",
                }}
              >
                <h3
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    color: "var(--ink-500)",
                    margin: 0,
                  }}
                >
                  历史任务
                </h3>
                {historyJobs.length > 0 && (
                  <button
                    onClick={onClearFailedHistory}
                    disabled={clearingHistory}
                    style={{
                      fontSize: 11,
                      color: clearingHistory ? "var(--ink-400)" : "var(--risk-500)",
                      background: "transparent",
                      border: "none",
                      cursor: clearingHistory ? "wait" : "pointer",
                      textDecoration: "underline",
                      padding: 0,
                    }}
                  >
                    {clearingHistory ? "正在清空…" : "清空失败任务"}
                  </button>
                )}
              </div>
              {historyError && (
                <div style={{ fontSize: 11, color: "var(--risk-500)", marginBottom: 8 }}>
                  {historyError}
                </div>
              )}
              {!historyError && historyJobs.length === 0 && (
                <div
                  className="card"
                  style={{
                    padding: 14,
                    fontSize: 12,
                    color: "var(--ink-500)",
                    textAlign: "center",
                  }}
                >
                  暂无历史任务
                </div>
              )}
              {historyJobs.map((j) => (
                <JobCard
                  key={j.id}
                  job={j}
                  onView={onJobView}
                  onRetry={onJobRetry}
                  onCancel={onJobCancel}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Bottom CTA */}
      <div
        style={{
          flexShrink: 0,
          padding: isDesktop ? "16px 32px 20px" : "12px 16px 14px",
          background: "var(--bg)",
          borderTop: "1px solid var(--ink-100)",
        }}
      >
        <div style={{ maxWidth: isDesktop ? 920 : undefined, margin: "0 auto" }}>
          <button
            onClick={handleSubmit}
            disabled={!ready || submitting}
            className="btn btn-primary"
            style={{
              width: "100%",
              opacity: ready && !submitting ? 1 : 0.5,
              cursor: ready && !submitting ? "pointer" : "not-allowed",
            }}
          >
            {I.spark(15, "#fff")}
            <span>
              {submitting ? "提交中…" : `加入处理队列 ${ready ? `（${total} 项）` : ""}`}
            </span>
          </button>
        </div>
      </div>

      {lightbox && (
        <div
          onClick={() => setLightbox(null)}
          role="dialog"
          aria-modal="true"
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 1000,
            background: "rgba(0,0,0,0.85)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 16,
            cursor: "zoom-out",
          }}
        >
          <img
            src={lightbox}
            alt="预览"
            style={{
              maxWidth: "100%",
              maxHeight: "100%",
              objectFit: "contain",
              borderRadius: 8,
              boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
            }}
          />
          <button
            onClick={(e) => {
              e.stopPropagation();
              setLightbox(null);
            }}
            aria-label="关闭"
            style={{
              position: "absolute",
              top: 16,
              right: 16,
              width: 40,
              height: 40,
              borderRadius: 20,
              background: "rgba(255,255,255,0.15)",
              border: "none",
              color: "#fff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
              backdropFilter: "blur(8px)",
            }}
          >
            {I.close(20, "#fff")}
          </button>
        </div>
      )}
    </div>
  );
}

function iconForFile(f: StagedFile) {
  const t = f.blob.type || "";
  const name = f.name.toLowerCase();
  if (t.startsWith("image/")) return I.camera(16);
  if (t.startsWith("audio/") || /\.(mp3|wav|m4a|ogg|amr)$/i.test(name)) return I.voice(16);
  return I.doc(16);
}

function describeSourceHint(hint: StagedSourceHint, blob: File): string {
  if (hint === "camera") return "拍照";
  if (blob.type.startsWith("image/")) return "图片";
  if (blob.type.startsWith("audio/")) return "语音";
  return "文件";
}

// ───────────── Job card ─────────────

const STATUS_PILL: Record<
  IngestJobStatus,
  { className: string; label: string }
> = {
  queued: { className: "pill pill-ai", label: "排队中" },
  running: { className: "pill pill-ai", label: "处理中" },
  extracted: { className: "pill pill-ok", label: "草稿就绪" },
  confirmed: { className: "pill pill-ok", label: "已归档" },
  failed: { className: "pill pill-risk", label: "失败" },
  canceled: { className: "pill pill-warn", label: "已取消" },
};

const STAGE_LABEL: Record<IngestJobStage, string> = {
  received: "接收",
  stored: "保存",
  ocr: "OCR/文本化",
  route: "Schema 路由",
  extract: "字段抽取",
  merge: "结果合并",
  draft: "生成草稿",
  done: "完成",
};

function JobCard({
  job,
  onView,
  onRetry,
  onCancel,
}: {
  job: IngestJob;
  onView: (j: IngestJob) => void;
  onRetry: (j: IngestJob) => void;
  onCancel: (j: IngestJob) => void;
}) {
  const status = STATUS_PILL[job.status];
  const isActive = job.status === "queued" || job.status === "running";
  const canCancel = isActive || job.status === "extracted";
  const canRetry = job.status === "failed" || job.status === "canceled";
  const canView = job.status === "extracted" || job.status === "confirmed";

  const when = job.finished_at ?? job.updated_at ?? job.created_at;

  return (
    <div
      className="card"
      style={{ padding: 12, marginBottom: 8, display: "flex", gap: 12, alignItems: "flex-start" }}
    >
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: 10,
          background: "var(--surface-3)",
          color: "var(--ink-600)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        {job.source_hint === "pasted_text"
          ? I.chat(16)
          : job.source_hint === "camera"
            ? I.camera(16)
            : I.doc(16)}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: "var(--ink-900)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {job.original_filename}
        </div>
        <div
          style={{
            fontSize: 11,
            color: "var(--ink-500)",
            marginTop: 4,
            display: "flex",
            alignItems: "center",
            gap: 6,
            flexWrap: "wrap",
          }}
        >
          <span className={status.className} style={{ fontSize: 10, padding: "1px 6px" }}>
            {status.label}
          </span>
          {(isActive || job.status === "extracted") && (
            <span
              style={{
                fontSize: 10,
                padding: "1px 6px",
                borderRadius: 6,
                background: "var(--surface-3)",
                color: "var(--ink-600)",
              }}
            >
              {STAGE_LABEL[job.stage] ?? job.stage}
            </span>
          )}
          {job.attempts > 1 && (
            <span style={{ fontSize: 10, color: "var(--ink-500)" }}>第 {job.attempts} 次</span>
          )}
          {when && <span style={{ fontSize: 10, color: "var(--ink-400)" }}>{fmtRelative(when)}</span>}
        </div>
        {job.progress_message && job.status !== "failed" && (
          <div
            style={{
              fontSize: 11,
              color: "var(--ink-500)",
              marginTop: 4,
              lineHeight: 1.4,
              wordBreak: "break-word",
            }}
          >
            {job.progress_message}
          </div>
        )}
        {job.error_message && (
          <div
            style={{
              fontSize: 11,
              color: "var(--risk-700)",
              marginTop: 4,
              lineHeight: 1.4,
              wordBreak: "break-word",
            }}
          >
            {job.error_message}
          </div>
        )}
        <div style={{ marginTop: 8, display: "flex", gap: 6, flexWrap: "wrap" }}>
          {canView && (
            <button
              onClick={() => onView(job)}
              className="btn btn-primary"
              style={{ padding: "4px 10px", fontSize: 12 }}
            >
              {job.status === "confirmed" ? "查看" : "查看结果"}
            </button>
          )}
          {canRetry && (
            <button
              onClick={() => onRetry(job)}
              className="btn btn-secondary"
              style={{ padding: "4px 10px", fontSize: 12 }}
            >
              重试
            </button>
          )}
          {canCancel && (
            <button
              onClick={() => onCancel(job)}
              className="btn btn-secondary"
              style={{ padding: "4px 10px", fontSize: 12 }}
            >
              取消
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function PasteArea({
  pasted,
  setPasted,
  compact,
}: {
  pasted: string;
  setPasted: (s: string) => void;
  compact: boolean;
}) {
  return (
    <div
      className="card"
      style={{
        padding: 12,
        marginBottom: compact ? 0 : 12,
        display: "flex",
        flexDirection: "column",
        minHeight: compact ? 156 : undefined,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          fontSize: 12,
          fontWeight: 600,
          color: "var(--ink-500)",
          marginBottom: 8,
          letterSpacing: "0.02em",
        }}
      >
        <span>文字输入</span>
        <span className="pill pill-ai" style={{ fontSize: 10, padding: "1px 6px" }}>
          {I.spark(10)} AI 自动识别字段
        </span>
      </div>
      <textarea
        rows={compact ? 5 : 9}
        placeholder="粘贴微信聊天、邮件、对话记录，或直接手动输入备注…"
        value={pasted}
        onChange={(e) => setPasted(e.target.value)}
        style={{
          width: "100%",
          flex: compact ? 1 : undefined,
          minHeight: compact ? undefined : 200,
          border: "none",
          outline: "none",
          resize: "none",
          fontFamily: "var(--font)",
          fontSize: 14,
          lineHeight: 1.55,
          color: "var(--ink-800)",
          background: "transparent",
        }}
      />
    </div>
  );
}
