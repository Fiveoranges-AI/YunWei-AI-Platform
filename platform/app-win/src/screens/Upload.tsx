import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from "react";
import type { GoFn } from "../App";
import {
  setLastBatch,
  uploadPastedText,
  uploadStagedFile,
  type IngestProgress,
  type IngestResult,
} from "../api/ingest";
import { I } from "../icons";
import { useIsDesktop } from "../lib/breakpoints";
import { markCustomersChanged } from "../lib/customerRefresh";

type StagedStatus = "idle" | "uploading" | "done" | "error" | "unsupported";

type StagedSourceHint = "file" | "camera";

type StagedFile = {
  id: string;
  name: string;
  sourceHint: StagedSourceHint;
  blob: File;
  status: StagedStatus;
  error?: string;
  documentId?: string;
  progressStage?: string;
  progressMessage?: string;
  previewUrl?: string; // object URL for image previews; revoked on remove/unmount
};

type PastedStatus = "idle" | "uploading" | "done" | "error";

export function UploadScreen({ go }: { go: GoFn }) {
  const isDesktop = useIsDesktop();
  const [pasted, setPasted] = useState("");
  const [pastedStatus, setPastedStatus] = useState<PastedStatus>("idle");
  const [pastedProgress, setPastedProgress] = useState<{ stage?: string; message?: string }>({});
  const [pastedError, setPastedError] = useState<string | null>(null);
  const [files, setFiles] = useState<StagedFile[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [lightbox, setLightbox] = useState<string | null>(null);
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
        status: "idle",
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
  function applyProgress(id: string, event: IngestProgress) {
    setFiles((prev) =>
      prev.map((f) =>
        f.id === id
          ? {
              ...f,
              status: "uploading",
              progressStage: event.stage,
              progressMessage: event.message,
              error: undefined,
            }
          : f,
      ),
    );
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

  async function handleSubmit() {
    if (submitting) return;
    const idleFiles = files.filter((f) => f.status === "idle" || f.status === "error");
    const trimmedText = pasted.trim();
    const hasPending = idleFiles.length > 0 || (trimmedText.length > 0 && pastedStatus !== "done");

    if (!hasPending) {
      // Nothing left to upload — if anything's already done, just navigate.
      if (files.some((f) => f.status === "done") || pastedStatus === "done") {
        go("review");
      }
      return;
    }

    setSubmitting(true);
    if (idleFiles.length) {
      setFiles((prev) =>
        prev.map((f) =>
          idleFiles.find((x) => x.id === f.id)
            ? { ...f, status: "uploading", progressStage: "upload", progressMessage: "等待上传", error: undefined }
            : f,
        ),
      );
    }
    if (trimmedText && pastedStatus !== "done") {
      setPastedStatus("uploading");
      setPastedProgress({ stage: "upload", message: "等待上传" });
      setPastedError(null);
    }

    type Outcome = { kind: "file"; id: string; result: IngestResult } | { kind: "text"; result: IngestResult };

    const fileTasks: Promise<Outcome>[] = idleFiles.map(async (f) => ({
      kind: "file" as const,
      id: f.id,
      result: await uploadStagedFile(f.blob, f.sourceHint, (event) => applyProgress(f.id, event)),
    }));

    const textTask: Promise<Outcome>[] = trimmedText && pastedStatus !== "done"
      ? [
          (async () => ({
            kind: "text" as const,
            result: await uploadPastedText(trimmedText, (event) => {
              setPastedProgress({ stage: event.stage, message: event.message });
            }),
          }))(),
        ]
      : [];

    const outcomes = await Promise.all([...fileTasks, ...textTask]);

    setFiles((prev) =>
      prev.map((f) => {
        const r = outcomes.find((o): o is Extract<Outcome, { kind: "file" }> =>
          o.kind === "file" && o.id === f.id,
        );
        if (!r) return f;
        if (r.result.ok) {
          return {
            ...f,
            status: "done",
            documentId: r.result.documentId,
            progressStage: "done",
            progressMessage: "草稿已生成，等待复核",
            error: undefined,
          };
        }
        return {
          ...f,
          status: r.result.unsupported ? "unsupported" : "error",
          progressStage: r.result.unsupported ? undefined : f.progressStage ?? "upload",
          progressMessage: r.result.unsupported ? undefined : r.result.error,
          error: r.result.error,
        };
      }),
    );

    const textOutcome = outcomes.find((o): o is Extract<Outcome, { kind: "text" }> => o.kind === "text");
    if (textOutcome) {
      if (textOutcome.result.ok) {
        setPastedStatus("done");
        setPastedProgress({ stage: "done", message: "草稿已生成，等待复核" });
        setPastedError(null);
      } else {
        setPastedStatus("error");
        setPastedError(textOutcome.result.error);
      }
    }

    setSubmitting(false);

    const anySucceeded = outcomes.some((o) => o.result.ok);
    if (anySucceeded) {
      // Track customer cache invalidation. For the unified pipeline, the
      // customer is only persisted on /confirm — but nudging the cache here
      // means the customer list refreshes after the user finishes the Review
      // archive flow without an extra round-trip.
      markCustomersChanged();

      // Hand the real backend payloads off to the Review screen so it can
      // render the actual unified draft instead of MOCK_REVIEW.
      const entries: { filename: string; result: IngestResult }[] = [];
      for (const o of outcomes) {
        if (o.kind === "file") {
          const src = idleFiles.find((x) => x.id === o.id);
          entries.push({ filename: src?.name ?? "", result: o.result });
        } else {
          entries.push({ filename: "粘贴文本", result: o.result });
        }
      }
      setLastBatch({ entries });
      // Brief pause so the success state is visible before transition.
      window.setTimeout(() => go("review"), 600);
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
            paste area (文字输入) so a freshly captured photo lands right
            next to the camera button instead of below the textarea. */}
        {(files.length > 0 || pasted.trim()) && (
          <div style={{ marginBottom: 12 }}>
            <div className="sec-h">
              <h3>已上传 {total} 项</h3>
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
                      <StatusPill file={f} />
                    </div>
                    {(f.status === "error" || f.status === "unsupported") && f.error && (
                      <div
                        style={{
                          fontSize: 11,
                          color: f.status === "error" ? "var(--risk-700)" : "var(--warn-700)",
                          marginTop: 4,
                          lineHeight: 1.4,
                          wordBreak: "break-word",
                        }}
                      >
                        {f.error}
                      </div>
                    )}
                    {f.progressStage && f.status !== "unsupported" && <ProgressNodes file={f} />}
                  </div>
                  <button
                    onClick={() => removeFile(f.id)}
                    disabled={f.status === "uploading"}
                    style={{
                      background: "transparent",
                      border: "none",
                      cursor: f.status === "uploading" ? "not-allowed" : "pointer",
                      color: "var(--ink-400)",
                      opacity: f.status === "uploading" ? 0.4 : 1,
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
                    <PastedStatusPill status={pastedStatus} error={pastedError} />
                  </div>
                  {pastedStatus === "error" && pastedError && (
                    <div
                      style={{
                        fontSize: 11,
                        color: "var(--risk-700)",
                        marginTop: 4,
                        lineHeight: 1.4,
                        wordBreak: "break-word",
                      }}
                    >
                      {pastedError}
                    </div>
                  )}
                  {pastedStatus !== "idle" && (
                    <PastedProgressNodes status={pastedStatus} progress={pastedProgress} />
                  )}
                </div>
                <button
                  onClick={() => {
                    setPasted("");
                    setPastedStatus("idle");
                    setPastedProgress({});
                    setPastedError(null);
                  }}
                  disabled={pastedStatus === "uploading"}
                  style={{
                    background: "transparent",
                    border: "none",
                    cursor: pastedStatus === "uploading" ? "not-allowed" : "pointer",
                    color: "var(--ink-400)",
                    opacity: pastedStatus === "uploading" ? 0.4 : 1,
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
              {submitting ? "AI 整理中…" : `开始 AI 整理 ${ready ? `（${total} 项）` : ""}`}
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

type ProgressNode = {
  key: string;
  label: string;
};

// Unified pipeline stages — same nodes regardless of document kind.
// Key matches the backend's emit_progress() stage strings; ``extract`` is a
// virtual aggregator across identity/commercial/ops_extract.
const PIPELINE_NODES: ProgressNode[] = [
  { key: "upload", label: "上传" },
  { key: "stored", label: "保存" },
  { key: "ocr", label: "OCR/文本化" },
  { key: "plan", label: "规划" },
  { key: "extract", label: "抽取" },
  { key: "merge", label: "合并" },
  { key: "done", label: "草稿" },
];

const STAGE_TO_NODE: Record<string, string> = {
  upload: "upload",
  uploading: "upload",
  received: "stored",
  evidence: "stored",
  stored: "stored",
  ocr: "ocr",
  plan: "plan",
  plan_done: "plan",
  route: "plan",
  identity_extract: "extract",
  identity_done: "extract",
  commercial_extract: "extract",
  commercial_done: "extract",
  ops_extract: "extract",
  ops_done: "extract",
  extract: "extract",
  merge: "merge",
  auto: "stored",
  auto_done: "done",
  done: "done",
};

function nodeIndexForStage(stage: string | undefined): number {
  if (!stage) return 0;
  const node = STAGE_TO_NODE[stage] ?? stage;
  const idx = PIPELINE_NODES.findIndex((n) => n.key === node);
  return idx >= 0 ? idx : 0;
}

function ProgressNodes({ file }: { file: StagedFile }) {
  const nodes = PIPELINE_NODES;
  const rawIndex = nodeIndexForStage(file.progressStage);
  const activeIndex = file.status === "done" ? nodes.length - 1 : Math.max(rawIndex, 0);

  return (
    <div style={{ marginTop: 9 }}>
      <ProgressStrip
        nodes={nodes}
        activeIndex={activeIndex}
        status={file.status === "done" ? "done" : file.status === "error" ? "error" : "uploading"}
      />
      {file.progressMessage && (
        <div
          style={{
            marginTop: 6,
            fontSize: 11,
            color: file.status === "error" ? "var(--risk-700)" : "var(--ink-500)",
            lineHeight: 1.4,
            wordBreak: "break-word",
          }}
        >
          {file.progressMessage}
        </div>
      )}
    </div>
  );
}

function PastedProgressNodes({
  status,
  progress,
}: {
  status: PastedStatus;
  progress: { stage?: string; message?: string };
}) {
  const nodes = PIPELINE_NODES;
  const rawIndex = nodeIndexForStage(progress.stage);
  const activeIndex = status === "done" ? nodes.length - 1 : Math.max(rawIndex, 0);
  const stripStatus: ProgressStripStatus =
    status === "done" ? "done" : status === "error" ? "error" : status === "uploading" ? "uploading" : "uploading";

  return (
    <div style={{ marginTop: 9 }}>
      <ProgressStrip nodes={nodes} activeIndex={activeIndex} status={stripStatus} />
      {progress.message && status !== "idle" && (
        <div
          style={{
            marginTop: 6,
            fontSize: 11,
            color: status === "error" ? "var(--risk-700)" : "var(--ink-500)",
            lineHeight: 1.4,
            wordBreak: "break-word",
          }}
        >
          {progress.message}
        </div>
      )}
    </div>
  );
}

type ProgressStripStatus = "uploading" | "done" | "error";

function ProgressStrip({
  nodes,
  activeIndex,
  status,
}: {
  nodes: ProgressNode[];
  activeIndex: number;
  status: ProgressStripStatus;
}) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
      {nodes.map((node, index) => {
        const isDone = status === "done" || index < activeIndex;
        const isActive = status === "uploading" && index === activeIndex;
        const isError = status === "error" && index === activeIndex;
        const color = isError
          ? "var(--risk-700)"
          : isDone
            ? "var(--ok-700)"
            : isActive
              ? "var(--ai-500)"
              : "var(--ink-400)";
        const background = isError
          ? "var(--risk-100)"
          : isDone
            ? "var(--ok-100)"
            : isActive
              ? "var(--ai-100)"
              : "var(--surface-3)";
        return (
          <span
            key={node.key}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              minHeight: 22,
              padding: "2px 7px 2px 5px",
              borderRadius: 7,
              background,
              color,
              fontSize: 10,
              fontWeight: 700,
              lineHeight: 1,
              whiteSpace: "nowrap",
            }}
          >
            <span
              style={{
                width: 12,
                height: 12,
                borderRadius: 6,
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                background: isDone || isError ? color : "transparent",
                color: isDone || isError ? "#fff" : color,
                border: isDone || isError ? "none" : `1px solid ${color}`,
                flex: "0 0 auto",
              }}
            >
              {isError ? I.warn(9, "#fff") : isDone ? I.check(9, "#fff") : null}
            </span>
            {node.label}
          </span>
        );
      })}
    </div>
  );
}

function StatusPill({ file }: { file: StagedFile }) {
  if (file.status === "idle") {
    return (
      <span className="pill pill-ai" style={{ fontSize: 10, padding: "1px 6px" }}>
        {I.spark(9)} 待 AI 整理
      </span>
    );
  }
  if (file.status === "uploading") {
    return (
      <span
        className="pill"
        style={{
          fontSize: 10,
          padding: "1px 6px",
          background: "var(--ai-100)",
          color: "var(--ai-500)",
        }}
      >
        上传中…
      </span>
    );
  }
  if (file.status === "done") {
    return (
      <span className="pill pill-ok" style={{ fontSize: 10, padding: "1px 6px" }}>
        ✓ 草稿已生成
      </span>
    );
  }
  if (file.status === "unsupported") {
    return (
      <span
        className="pill pill-warn"
        style={{ fontSize: 10, padding: "1px 6px" }}
        title={file.error}
      >
        暂不支持
      </span>
    );
  }
  return (
    <span
      className="pill pill-risk"
      style={{ fontSize: 10, padding: "1px 6px" }}
      title={file.error}
    >
      上传失败
    </span>
  );
}

function PastedStatusPill({ status, error }: { status: PastedStatus; error: string | null }) {
  if (status === "idle") {
    return (
      <span className="pill pill-ai" style={{ fontSize: 10, padding: "1px 6px" }}>
        {I.spark(9)} 待 AI 整理
      </span>
    );
  }
  if (status === "uploading") {
    return (
      <span
        className="pill"
        style={{
          fontSize: 10,
          padding: "1px 6px",
          background: "var(--ai-100)",
          color: "var(--ai-500)",
        }}
      >
        上传中…
      </span>
    );
  }
  if (status === "done") {
    return (
      <span className="pill pill-ok" style={{ fontSize: 10, padding: "1px 6px" }}>
        ✓ 草稿已生成
      </span>
    );
  }
  return (
    <span
      className="pill pill-risk"
      style={{ fontSize: 10, padding: "1px 6px" }}
      title={error ?? undefined}
    >
      上传失败
    </span>
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
