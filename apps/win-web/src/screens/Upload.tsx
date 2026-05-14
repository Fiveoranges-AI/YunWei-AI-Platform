import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from "react";
import type { GoFn } from "../App";
import { createIngestV2Jobs } from "../api/ingestV2";
import { I } from "../icons";
import { useIsDesktop, useIsTablet } from "../lib/breakpoints";
import { markCustomersChanged } from "../lib/customerRefresh";

type StagedSourceHint = "file" | "camera";

type StagedFile = {
  id: string;
  name: string;
  sourceHint: StagedSourceHint;
  blob: File;
  previewUrl?: string;
};

export function UploadScreen({ go }: { go: GoFn }) {
  const isDesktop = useIsDesktop();
  const isTablet = useIsTablet();
  const isWide = isDesktop || isTablet;
  const [pasted, setPasted] = useState("");
  const [files, setFiles] = useState<StagedFile[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [lightbox, setLightbox] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);

  function addFile(blob: File, sourceHint: StagedSourceHint) {
    const previewUrl = blob.type.startsWith("image/") ? URL.createObjectURL(blob) : undefined;
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
      for (const f of Array.from(list)) addFile(f, sourceHint);
    }
    e.target.value = "";
  }

  function onDragOver(e: DragEvent<HTMLDivElement>) {
    if (!e.dataTransfer.types.includes("Files")) return;
    e.preventDefault();
    e.stopPropagation();
    if (!dragActive) setDragActive(true);
  }
  function onDragLeave(e: DragEvent<HTMLDivElement>) {
    const next = e.relatedTarget as Node | null;
    if (next && (e.currentTarget as HTMLElement).contains(next)) return;
    setDragActive(false);
  }
  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const dropped = Array.from(e.dataTransfer.files ?? []);
    for (const f of dropped) addFile(f, "file");
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
      const anyCamera = files.some((f) => f.sourceHint === "camera");
      const onlyText = !hasFiles && hasText;
      const sourceHint: "file" | "camera" | "pasted_text" = onlyText
        ? "pasted_text"
        : anyCamera && !files.some((f) => f.sourceHint !== "camera")
          ? "camera"
          : "file";

      await createIngestV2Jobs(files.map((f) => f.blob), {
        sourceHint,
        textContent: hasText ? trimmedText : undefined,
      });

      for (const f of files) if (f.previewUrl) URL.revokeObjectURL(f.previewUrl);
      setFiles([]);
      setPasted("");
      markCustomersChanged();
      // Land in Inbox so the user can watch the job process and confirm.
      go("inbox");
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "上传失败");
    } finally {
      setSubmitting(false);
    }
  }

  const total = files.length + (pasted.trim() ? 1 : 0);
  const ready = total > 0;

  // ──────────────── Wide (desktop/tablet) — centered card ────────────────
  if (isWide) {
    return (
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          background: "var(--surface-2)",
          overflowY: "auto",
        }}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
      >
        <HiddenInputs
          fileRef={fileInputRef}
          cameraRef={cameraInputRef}
          onPicked={handlePicked}
        />

        <div
          style={{
            maxWidth: 640,
            margin: "0 auto",
            padding: "40px 32px 40px",
            width: "100%",
          }}
        >
          <div style={{ paddingBottom: 24 }}>
            <div
              style={{
                fontSize: 30,
                fontWeight: 700,
                color: "var(--ink-900)",
                letterSpacing: "-0.02em",
                lineHeight: 1.15,
              }}
            >
              添加资料
            </div>
            <div style={{ fontSize: 14, color: "var(--ink-500)", marginTop: 8, lineHeight: 1.5 }}>
              选择来源，AI 会自动归类并匹配到对应客户。处理进度可在「上传记录」中查看。
            </div>
          </div>

          <SourceGrid
            onFile={() => fileInputRef.current?.click()}
            onCamera={() => cameraInputRef.current?.click()}
            dragActive={dragActive}
          />

          <Divider />

          <PasteCard pasted={pasted} setPasted={setPasted} disabled={submitting} />

          {(files.length > 0 || pasted.trim()) && (
            <StagedList
              files={files}
              pasted={pasted}
              setPasted={setPasted}
              onRemove={removeFile}
              onOpenLightbox={setLightbox}
              submitting={submitting}
            />
          )}

          {submitError && <ErrorBox text={submitError} />}

          <button
            onClick={handleSubmit}
            disabled={!ready || submitting}
            style={{
              width: "100%",
              marginTop: 16,
              height: 44,
              borderRadius: 10,
              border: "none",
              background: ready ? "var(--ink-900)" : "var(--ink-300)",
              color: "#fff",
              fontSize: 14,
              fontWeight: 600,
              cursor: ready && !submitting ? "pointer" : "not-allowed",
              fontFamily: "var(--font)",
              opacity: ready && !submitting ? 1 : 0.6,
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
            }}
          >
            {ready ? <>{I.spark(15, "#fff")}<span>{submitting ? "提交中…" : `导入 · ${total} 项`}</span></> : "请选择资料来源"}
          </button>
        </div>

        <Lightbox src={lightbox} onClose={() => setLightbox(null)} />
      </div>
    );
  }

  // ──────────────── Mobile ────────────────
  return (
    <div
      className="screen"
      style={{ background: "var(--bg)" }}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
      <HiddenInputs
        fileRef={fileInputRef}
        cameraRef={cameraInputRef}
        onPicked={handlePicked}
      />

      <div
        style={{
          padding: "12px 16px 8px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ fontSize: 22, fontWeight: 700, color: "var(--ink-900)" }}>添加资料</div>
        <button
          onClick={() => go("inbox")}
          aria-label="上传记录"
          style={{
            height: 32,
            padding: "0 12px",
            borderRadius: 16,
            background: "transparent",
            border: "1px solid var(--ink-100)",
            color: "var(--ink-700)",
            fontSize: 12,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          上传记录
        </button>
      </div>

      <div className="scroll" style={{ flex: 1, padding: "8px 16px 16px" }}>
        <SourceGrid
          onFile={() => fileInputRef.current?.click()}
          onCamera={() => cameraInputRef.current?.click()}
          dragActive={dragActive}
        />
        <Divider />
        <PasteCard pasted={pasted} setPasted={setPasted} disabled={submitting} />

        {(files.length > 0 || pasted.trim()) && (
          <StagedList
            files={files}
            pasted={pasted}
            setPasted={setPasted}
            onRemove={removeFile}
            onOpenLightbox={setLightbox}
            submitting={submitting}
          />
        )}

        {submitError && <ErrorBox text={submitError} />}
      </div>

      <div
        style={{
          flexShrink: 0,
          padding: "12px 16px 14px",
          background: "var(--bg)",
          borderTop: "1px solid var(--ink-100)",
        }}
      >
        <button
          onClick={handleSubmit}
          disabled={!ready || submitting}
          className="btn btn-primary"
          style={{
            width: "100%",
            opacity: ready && !submitting ? 1 : 0.6,
            cursor: ready && !submitting ? "pointer" : "not-allowed",
          }}
        >
          {I.spark(15, "#fff")}
          <span>
            {submitting ? "提交中…" : `加入处理队列 ${ready ? `（${total} 项）` : ""}`}
          </span>
        </button>
      </div>

      <Lightbox src={lightbox} onClose={() => setLightbox(null)} />
    </div>
  );
}

// ──────────────── pieces ────────────────

function HiddenInputs({
  fileRef,
  cameraRef,
  onPicked,
}: {
  fileRef: React.RefObject<HTMLInputElement>;
  cameraRef: React.RefObject<HTMLInputElement>;
  onPicked: (e: ChangeEvent<HTMLInputElement>, h: StagedSourceHint) => void;
}) {
  return (
    <>
      <input
        ref={fileRef}
        type="file"
        multiple
        accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,image/*"
        onChange={(e) => onPicked(e, "file")}
        style={{ display: "none" }}
      />
      <input
        ref={cameraRef}
        type="file"
        accept="image/*"
        capture="environment"
        onChange={(e) => onPicked(e, "camera")}
        style={{ display: "none" }}
      />
    </>
  );
}

function SourceGrid({
  onFile,
  onCamera,
  dragActive,
}: {
  onFile: () => void;
  onCamera: () => void;
  dragActive: boolean;
}) {
  const sources = [
    {
      key: "file",
      icon: I.cloud(22),
      label: dragActive ? "松开放下" : "文件",
      hint: dragActive ? "拖到这里直接添加" : "合同 · PDF · Excel · 邮件",
      onClick: onFile,
    },
    {
      key: "camera",
      icon: I.camera(22),
      label: "拍照",
      hint: "合同 · 名片 · 送货单",
      onClick: onCamera,
    },
    {
      key: "voice",
      icon: I.mic(22),
      label: "录音",
      hint: "通话 · 会议 · 语音备忘",
      onClick: onFile,
    },
  ];
  return (
    <div
      style={{
        background: "#fff",
        border: dragActive ? "1px solid var(--brand-500)" : "1px solid var(--ink-100)",
        borderRadius: 14,
        overflow: "hidden",
        marginBottom: 18,
        transition: "border-color 120ms ease",
      }}
    >
      {sources.map((s, i) => (
        <button
          key={s.key}
          onClick={s.onClick}
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            gap: 16,
            padding: "16px 20px",
            background: "transparent",
            border: "none",
            borderBottom: i < sources.length - 1 ? "1px solid var(--ink-100)" : "none",
            cursor: "pointer",
            textAlign: "left",
            fontFamily: "var(--font)",
          }}
        >
          <div
            style={{
              width: 42,
              height: 42,
              borderRadius: 11,
              background: "var(--surface-3)",
              color: "var(--ink-700)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            {s.icon}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 15.5, fontWeight: 600, color: "var(--ink-900)" }}>{s.label}</div>
            <div style={{ fontSize: 12, color: "var(--ink-500)", marginTop: 3 }}>{s.hint}</div>
          </div>
          <span style={{ color: "var(--ink-300)" }}>{I.chev(16)}</span>
        </button>
      ))}
    </div>
  );
}

function Divider() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
      <div style={{ flex: 1, height: 1, background: "var(--ink-100)" }} />
      <span
        style={{
          fontSize: 11,
          color: "var(--ink-400)",
          fontWeight: 500,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
        }}
      >
        或文字粘贴
      </span>
      <div style={{ flex: 1, height: 1, background: "var(--ink-100)" }} />
    </div>
  );
}

function PasteCard({
  pasted,
  setPasted,
  disabled,
}: {
  pasted: string;
  setPasted: (s: string) => void;
  disabled: boolean;
}) {
  return (
    <div
      style={{
        background: "#fff",
        border: "1px solid var(--ink-100)",
        borderRadius: 14,
        padding: "14px 16px",
        marginBottom: 16,
      }}
    >
      <textarea
        rows={6}
        placeholder="粘贴微信聊天、邮件、对话记录，或直接手动输入备注…"
        value={pasted}
        disabled={disabled}
        onChange={(e) => setPasted(e.target.value)}
        style={{
          width: "100%",
          minHeight: 140,
          border: "none",
          outline: "none",
          resize: "none",
          fontFamily: "var(--font)",
          fontSize: 14.5,
          lineHeight: 1.6,
          color: "var(--ink-900)",
          background: "transparent",
          padding: 0,
          display: "block",
        }}
      />
      {pasted.trim() && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginTop: 10,
            paddingTop: 10,
            borderTop: "1px solid var(--ink-100)",
            fontSize: 11.5,
            color: "var(--ink-400)",
          }}
        >
          <span>{pasted.length} 字</span>
          <button
            onClick={() => setPasted("")}
            style={{
              background: "transparent",
              border: "none",
              cursor: "pointer",
              color: "var(--ink-400)",
              fontSize: 11.5,
              fontFamily: "var(--font)",
            }}
          >
            清空
          </button>
        </div>
      )}
    </div>
  );
}

function StagedList({
  files,
  pasted,
  setPasted,
  onRemove,
  onOpenLightbox,
  submitting,
}: {
  files: StagedFile[];
  pasted: string;
  setPasted: (s: string) => void;
  onRemove: (id: string) => void;
  onOpenLightbox: (src: string) => void;
  submitting: boolean;
}) {
  return (
    <div style={{ marginBottom: 4 }}>
      <div
        style={{
          fontSize: 11,
          fontWeight: 700,
          color: "var(--ink-500)",
          letterSpacing: "0.06em",
          textTransform: "uppercase",
          padding: "0 4px 8px",
        }}
      >
        已添加 · {files.length + (pasted.trim() ? 1 : 0)}
      </div>
      <div
        style={{
          background: "#fff",
          border: "1px solid var(--ink-100)",
          borderRadius: 12,
          overflow: "hidden",
        }}
      >
        {files.map((f, i) => {
          const last = i === files.length - 1 && !pasted.trim();
          return (
            <div
              key={f.id}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: "12px 16px",
                borderBottom: last ? "none" : "1px solid var(--ink-100)",
              }}
            >
              {f.previewUrl ? (
                <button
                  onClick={() => f.previewUrl && onOpenLightbox(f.previewUrl)}
                  aria-label={`查看 ${f.name}`}
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: 9,
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
                <span style={{ color: "var(--ink-500)" }}>{iconForFile(f)}</span>
              )}
              <div
                style={{
                  flex: 1,
                  fontSize: 13.5,
                  color: "var(--ink-900)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {f.name}
              </div>
              <button
                onClick={() => onRemove(f.id)}
                disabled={submitting}
                style={{
                  background: "transparent",
                  border: "none",
                  cursor: submitting ? "not-allowed" : "pointer",
                  color: "var(--ink-400)",
                  padding: 4,
                  display: "flex",
                  opacity: submitting ? 0.4 : 1,
                }}
              >
                {I.close(15)}
              </button>
            </div>
          );
        })}
        {pasted.trim() && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              padding: "12px 16px",
            }}
          >
            <span style={{ color: "var(--ink-500)" }}>{I.chat(15)}</span>
            <div
              style={{
                flex: 1,
                fontSize: 13.5,
                color: "var(--ink-900)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              粘贴文本 · {pasted.length} 字
            </div>
            <button
              onClick={() => setPasted("")}
              disabled={submitting}
              style={{
                background: "transparent",
                border: "none",
                cursor: submitting ? "not-allowed" : "pointer",
                color: "var(--ink-400)",
                padding: 4,
                display: "flex",
                opacity: submitting ? 0.4 : 1,
              }}
            >
              {I.close(15)}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function ErrorBox({ text }: { text: string }) {
  return (
    <div
      style={{
        marginTop: 12,
        padding: "10px 12px",
        borderRadius: 10,
        border: "1px solid var(--risk-100)",
        background: "#fff1f0",
        color: "var(--risk-500)",
        fontSize: 12,
        lineHeight: 1.5,
      }}
    >
      {text}
    </div>
  );
}

function Lightbox({ src, onClose }: { src: string | null; onClose: () => void }) {
  if (!src) return null;
  return (
    <div
      onClick={onClose}
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
        src={src}
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
          onClose();
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
  );
}

function iconForFile(f: StagedFile): JSX.Element {
  const t = f.blob.type || "";
  const name = f.name.toLowerCase();
  if (t.startsWith("image/")) return I.camera(15);
  if (t.startsWith("audio/") || /\.(mp3|wav|m4a|ogg|amr)$/i.test(name)) return I.voice(15);
  return I.doc(15);
}
