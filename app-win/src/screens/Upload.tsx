import { useState } from "react";
import type { GoFn } from "../App";
import { I } from "../icons";
import { useIsDesktop } from "../lib/breakpoints";

type StagedFile = { id: string; name: string; kind: string };

export function UploadScreen({ go }: { go: GoFn }) {
  const isDesktop = useIsDesktop();
  const [pasted, setPasted] = useState("");
  const [files, setFiles] = useState<StagedFile[]>([]);

  function addFile(name: string, kind: string) {
    setFiles((f) => [...f, { id: Math.random().toString(36).slice(2), name, kind }]);
  }
  function removeFile(id: string) {
    setFiles((f) => f.filter((x) => x.id !== id));
  }

  const total = files.length + (pasted.trim() ? 1 : 0);
  const ready = total > 0;

  return (
    <div className="screen" style={{ background: "var(--bg)" }}>
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
              background: "var(--surface)",
              border: "2px dashed var(--brand-300)",
              borderRadius: 18,
              padding: "20px 12px",
              minHeight: 156,
            }}
            onClick={() => addFile("终验补充协议_v2.pdf", "合同")}
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
            <div style={{ fontSize: 15, fontWeight: 700, color: "var(--ink-900)" }}>上传文件</div>
            <div style={{ fontSize: 11, color: "var(--ink-500)", marginTop: 4, lineHeight: 1.45 }}>
              合同 · 截图 · Excel
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
            onClick={() => addFile("IMG_2398.jpg", "名片")}
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
                      <span className="pill pill-ai" style={{ fontSize: 10, padding: "1px 6px" }}>
                        {I.spark(9)} 待 AI 整理
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={() => removeFile(f.id)}
                    style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--ink-400)" }}
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
            onClick={() => go("review")}
            disabled={!ready}
            className="btn btn-primary"
            style={{ width: "100%", opacity: ready ? 1 : 0.5, cursor: ready ? "pointer" : "not-allowed" }}
          >
            {I.spark(15, "#fff")}
            <span>开始 AI 整理 {ready && `（${total} 项）`}</span>
          </button>
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
