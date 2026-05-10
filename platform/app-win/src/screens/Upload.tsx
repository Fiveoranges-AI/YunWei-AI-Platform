import { useRef, useState, type ChangeEvent, type DragEvent } from "react";
import type { GoFn } from "../App";
import { setLastBatch, uploadStagedFile, type IngestProgress } from "../api/ingest";
import { I } from "../icons";
import { useIsDesktop } from "../lib/breakpoints";
import { markCustomersChanged } from "../lib/customerRefresh";

type StagedStatus = "idle" | "uploading" | "done" | "error" | "unsupported";

type StagedFile = {
  id: string;
  name: string;
  kind: string;
  blob: File;
  status: StagedStatus;
  error?: string;
  documentId?: string;
  progressStage?: string;
  progressMessage?: string;
};

export function UploadScreen({ go }: { go: GoFn }) {
  const isDesktop = useIsDesktop();
  const [pasted, setPasted] = useState("");
  const [files, setFiles] = useState<StagedFile[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);

  function addFile(blob: File, kind: string) {
    setFiles((f) => [
      ...f,
      {
        id: Math.random().toString(36).slice(2),
        name: blob.name,
        kind,
        blob,
        status: "idle",
      },
    ]);
  }
  function removeFile(id: string) {
    setFiles((f) => f.filter((x) => x.id !== id));
  }
  function setFileKind(id: string, kind: string) {
    setFiles((f) => f.map((x) => (x.id === id ? { ...x, kind } : x)));
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

  function detectKind(name: string): string {
    const lower = name.toLowerCase();
    const ext = name.split(".").pop()?.toLowerCase() ?? "";
    if (["pdf", "doc", "docx"].includes(ext)) return "合同";
    if (["xls", "xlsx", "csv"].includes(ext)) return "Excel";
    if (["mp3", "wav", "m4a", "ogg", "amr"].includes(ext)) return "语音";
    if (/(名片|business[-_ ]?card|name[-_ ]?card|vcard|contact)/i.test(lower)) return "名片";
    return "截图";
  }

  function handlePicked(e: ChangeEvent<HTMLInputElement>, fixedKind?: string) {
    const list = e.target.files;
    if (list) {
      for (const f of Array.from(list)) {
        addFile(f, fixedKind ?? detectKind(f.name));
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
      addFile(f, detectKind(f.name));
    }
  }

  async function handleSubmit() {
    if (submitting) return;
    const idle = files.filter((f) => f.status === "idle" || f.status === "error");
    if (!idle.length) {
      // Nothing to upload (only pasted text, or everything already done).
      // Pasted text has no entity-first endpoint yet — navigate so the user
      // can still see the review step end-to-end.
      if (pasted.trim() || files.some((f) => f.status === "done")) {
        go("review");
      }
      return;
    }
    setSubmitting(true);
    setFiles((prev) =>
      prev.map((f) =>
        idle.find((x) => x.id === f.id)
          ? { ...f, status: "uploading", progressStage: "upload", progressMessage: "等待上传", error: undefined }
          : f,
      ),
    );

    const results = await Promise.all(
      idle.map(async (f) => ({
        id: f.id,
        result: await uploadStagedFile(f.blob, f.kind, (event) => applyProgress(f.id, event)),
      })),
    );

    setFiles((prev) =>
      prev.map((f) => {
        const r = results.find((x) => x.id === f.id);
        if (!r) return f;
        if (r.result.ok) {
          return {
            ...f,
            status: "done",
            documentId: r.result.documentId,
            progressStage: "done",
            progressMessage: f.kind === "合同" ? "草稿已生成，等待复核" : "已完成并写入档案",
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

    setSubmitting(false);

    const anySucceeded = results.some((r) => r.result.ok);
    if (anySucceeded) {
      if (results.some((r) => r.result.ok && Boolean((r.result.raw as { customer_id?: string | null }).customer_id))) {
        markCustomersChanged();
      }
      // Hand the real backend payload off to the Review screen so it can
      // render the actual customer / contacts / fields instead of MOCK_REVIEW.
      setLastBatch({
        entries: results.map((r) => {
          const src = idle.find((x) => x.id === r.id);
          return {
            filename: src?.name ?? "",
            kind: src?.kind ?? "",
            result: r.result,
          };
        }),
      });
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
        onChange={(e) => handlePicked(e)}
        style={{ display: "none" }}
      />
      <input
        ref={cameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        onChange={(e) => handlePicked(e, "名片")}
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

        {/* Mobile: paste area below */}
        {!isDesktop && <PasteArea pasted={pasted} setPasted={setPasted} compact={false} />}

        {/* Staged items */}
        {(files.length > 0 || pasted.trim()) && (
          <div style={{ marginBottom: 12 }}>
            <div className="sec-h">
              <h3>已上传 {total} 项</h3>
            </div>
            {files.map((f) => {
              const icon = f.kind === "语音" ? I.voice(16) : f.kind === "名片" ? I.camera(16) : I.doc(16);
              return (
                <div
                  key={f.id}
                  className="card"
                  style={{ padding: 12, marginBottom: 8, display: "flex", alignItems: "center", gap: 12 }}
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
                    }}
                  >
                    {icon}
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
                      <span>{f.kind}</span>
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
                    {isImageFile(f) && f.status !== "uploading" && (
                      <KindSegment value={f.kind} onChange={(kind) => setFileKind(f.id, kind)} />
                    )}
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
              <div className="card" style={{ padding: 12, display: "flex", alignItems: "center", gap: 12 }}>
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
                  }}
                >
                  {I.chat(16)}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "var(--ink-900)" }}>
                    粘贴文本 · {pasted.length} 字
                  </div>
                  <div style={{ fontSize: 11, color: "var(--ink-500)", marginTop: 2 }}>
                    {pasted.slice(0, 24)}…
                  </div>
                </div>
                <button
                  onClick={() => setPasted("")}
                  style={{
                    background: "transparent",
                    border: "none",
                    cursor: "pointer",
                    color: "var(--ink-400)",
                  }}
                >
                  {I.close(16)}
                </button>
              </div>
            )}
          </div>
        )}
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
    </div>
  );
}

function isImageFile(file: StagedFile): boolean {
  return file.blob.type.startsWith("image/") || /\.(png|jpe?g|webp|gif|bmp)$/i.test(file.name);
}

function KindSegment({ value, onChange }: { value: string; onChange: (kind: string) => void }) {
  return (
    <div
      style={{
        display: "inline-flex",
        marginTop: 8,
        padding: 2,
        borderRadius: 9,
        background: "var(--surface-3)",
        border: "1px solid var(--ink-100)",
      }}
    >
      {["名片", "截图"].map((kind) => {
        const active = value === kind;
        return (
          <button
            key={kind}
            type="button"
            onClick={() => onChange(kind)}
            style={{
              border: "none",
              borderRadius: 7,
              padding: "4px 10px",
              fontSize: 11,
              fontWeight: 600,
              color: active ? "var(--brand-700)" : "var(--ink-500)",
              background: active ? "var(--surface)" : "transparent",
              cursor: "pointer",
              boxShadow: active ? "var(--shadow-card-soft)" : "none",
            }}
          >
            {kind}
          </button>
        );
      })}
    </div>
  );
}

type ProgressNode = {
  key: string;
  label: string;
};

const BASE_PROGRESS_NODES: ProgressNode[] = [
  { key: "upload", label: "上传" },
  { key: "received", label: "接收" },
  { key: "stored", label: "保存" },
  { key: "ocr", label: "OCR" },
  { key: "extract", label: "抽取" },
];

function progressNodesFor(kind: string): ProgressNode[] {
  if (kind === "合同") {
    return [...BASE_PROGRESS_NODES, { key: "match", label: "匹配" }, { key: "done", label: "草稿" }];
  }
  if (kind === "名片") {
    return [
      ...BASE_PROGRESS_NODES,
      { key: "match", label: "匹配" },
      { key: "persist", label: "入库" },
      { key: "done", label: "完成" },
    ];
  }
  return [...BASE_PROGRESS_NODES, { key: "persist", label: "保存" }, { key: "done", label: "完成" }];
}

function ProgressNodes({ file }: { file: StagedFile }) {
  const nodes = progressNodesFor(file.kind);
  const rawIndex = nodes.findIndex((node) => node.key === file.progressStage);
  const activeIndex = file.status === "done" ? nodes.length - 1 : Math.max(rawIndex, 0);

  return (
    <div style={{ marginTop: 9 }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {nodes.map((node, index) => {
          const isDone = file.status === "done" || index < activeIndex;
          const isActive = file.status === "uploading" && index === activeIndex;
          const isError = file.status === "error" && index === activeIndex;
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
    // Contract is a two-phase flow on the backend (draft → confirm); the other
    // kinds commit entities in a single call. Surface the difference so users
    // know contract still needs review/confirm.
    const label = file.kind === "合同" ? "✓ 草稿已生成" : "✓ 已录入";
    return (
      <span
        className="pill pill-ok"
        style={{ fontSize: 10, padding: "1px 6px" }}
      >
        {label}
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
