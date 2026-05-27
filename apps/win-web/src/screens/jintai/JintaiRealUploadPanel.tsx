/**
 * Round 5: 真实文档上传区 (backend mode only).
 *
 * 客户拖放/选择文件 → POST /api/win/parse/upload → 渲染 AI 抽取候选字段 +
 * 置信度颜色编码 → 「采纳」走 confirm_writer + 触发主线 (库存扣减 → 缺料 →
 * AI auto-draft PR → ...).
 *
 * mock 模式完全隐藏 — JintaiUploadInbox 老 "📋 模拟" 按钮保留不变.
 *
 * 设计原则:
 *  - 不引依赖 (拖放 native DataTransfer,进度 XHR onprogress)
 *  - DemoMockProvider fallback 时 warning 显示在卡片顶部,让客户清楚区分真 AI 抽取
 *  - 编辑过的字段标 was_edited,confirm_writer 会自动 confidence=None (审计真实)
 *  - 「采纳」后自动 refresh KPI,Backend Reality Check 面板数字会更新
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  confirmUploadedEntity,
  listMaterials,
  postIssueAndConfirm,
  uploadDocument,
  type ParseUploadResponse,
  type UploadEntity,
  type UploadField,
} from "../../api/jintai-backend";
import { useJintai } from "./state/store";


const ACCEPTED_MIMES = [
  ".jpg", ".jpeg", ".png", ".pdf", ".xlsx", ".xls", ".csv",
].join(",");

const SAMPLE_FILES: { label: string; path: string; mime: string }[] = [
  { label: "📷 领料单.jpg", path: "/win/samples/jintai/领料单.jpg", mime: "image/jpeg" },
  { label: "📄 采购合同.pdf", path: "/win/samples/jintai/采购合同.pdf", mime: "application/pdf" },
  { label: "📊 供应商对账.xlsx", path: "/win/samples/jintai/供应商对账.xlsx",
    mime: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" },
];


type LocalState =
  | { kind: "idle" }
  | { kind: "uploading"; pct: number; filename: string }
  | { kind: "candidate"; resp: ParseUploadResponse; edits: Record<string, string> }
  | { kind: "submitting"; message: string }
  | { kind: "submitted"; message: string }
  | { kind: "error"; message: string };


export function JintaiRealUploadPanel() {
  const { state, dispatch, refreshBackendKpi } = useJintai();
  const [s, setS] = useState<LocalState>({ kind: "idle" });
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // 只在 backend mode 显示
  if (state.mode !== "backend") return null;

  // Round 5 debug: ?previewUpload=fields|edited|accepted 让 headless Chrome
  // 自动跑通对应状态后再截图,opt-in,不影响默认 demo UX
  // (生效需 panel 已挂载 → 见 useEffect below)
  // ...rendered via _PreviewDriver inside this fn

  const handleFile = useCallback(async (file: File) => {
    if (file.size > 20 * 1024 * 1024) {
      setS({ kind: "error", message: `文件过大 (${(file.size / 1024 / 1024).toFixed(1)}MB > 20MB)` });
      return;
    }
    setS({ kind: "uploading", pct: 0, filename: file.name });
    try {
      const resp = await uploadDocument(file, {
        onProgress: (pct) => setS({ kind: "uploading", pct, filename: file.name }),
      });
      setS({ kind: "candidate", resp, edits: {} });
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setS({ kind: "error", message: `上传失败: ${msg}` });
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) void handleFile(file);
  }, [handleFile]);

  const handleSample = useCallback(async (sample: typeof SAMPLE_FILES[number]) => {
    try {
      const resp = await fetch(sample.path);
      if (!resp.ok) throw new Error(`fetch sample ${resp.status}`);
      const blob = await resp.blob();
      const filename = sample.path.split("/").pop() || "sample.bin";
      void handleFile(new File([blob], filename, { type: sample.mime }));
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setS({ kind: "error", message: `载入示例失败: ${msg}` });
    }
  }, [handleFile]);


  const accept = async () => {
    if (s.kind !== "candidate") return;
    const ent = s.resp.candidate.entities[0];
    if (!ent) { setS({ kind: "error", message: "无候选实体" }); return; }
    setS({ kind: "submitting", message: "采纳中:写入 confirm_writer + 触发主线..." });
    try {
      // IssueVoucher 路径:需要 material_id (DemoMockProvider 只给 hint name)
      let materialId: string | undefined;
      if (ent.entity_type === "IssueVoucher") {
        const mats = await listMaterials();
        if (mats.length > 0) {
          materialId = state.backendIds.materialId || mats[0].id;
        }
      }
      const confirmResp = await confirmUploadedEntity({
        entity: ent,
        source_type: s.resp.source_type,
        file_ref: `upload://${s.resp.attachment.checksum}`,
        edits: _stringEditsToValues(s.edits, ent),
        materialId,
      });
      const written = confirmResp.written[0];
      if (!written) throw new Error("confirm returned 0 written");

      let triggerMessage = `✓ 已写入 ${written.entity_type} (id=${written.entity_id.slice(0, 8)}…)`;

      // IssueVoucher → 走主线触发
      if (written.entity_type === "IssueVoucher") {
        const issueResp = await postIssueAndConfirm(written.entity_id);
        dispatch({
          type: "SET_BACKEND_IDS",
          ids: {
            voucherId: written.entity_id,
            prId: issueResp.auto_drafted_pr_id ?? undefined,
          },
        });
        triggerMessage += `;主线触发: 库存 ${issueResp.balance_after} kg`;
        if (issueResp.alert_id) triggerMessage += " · 缺料预警";
        if (issueResp.auto_drafted_pr_no) triggerMessage += ` · auto-draft ${issueResp.auto_drafted_pr_no}`;
      }
      await refreshBackendKpi();
      setS({ kind: "submitted", message: triggerMessage });
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setS({ kind: "error", message: `采纳失败: ${msg}` });
    }
  };

  const dismiss = () => setS({ kind: "idle" });

  // ===== Round 5 debug: ?previewUpload=fields|edited|accepted =====
  // Auto-drives the panel for headless-Chrome screenshot capture.
  // Opt-in via URL param; production demo UX unaffected.
  const previewMode = useMemo<string | null>(() => {
    if (typeof window === "undefined") return null;
    return new URLSearchParams(window.location.search).get("previewUpload");
  }, []);
  const previewTriggeredRef = useRef<{ uploaded?: boolean; mutated?: boolean }>({});
  useEffect(() => {
    if (!previewMode || state.mode !== "backend") return;
    if (s.kind === "idle" && !previewTriggeredRef.current.uploaded) {
      previewTriggeredRef.current.uploaded = true;
      void handleSample(SAMPLE_FILES[2]); // xlsx
      return;
    }
    if (s.kind === "candidate" && !previewTriggeredRef.current.mutated) {
      previewTriggeredRef.current.mutated = true;
      if (previewMode === "edited") {
        setS((curr) =>
          curr.kind === "candidate"
            ? { ...curr, edits: { quantity: "1500", workshop: "成型车间" } }
            : curr,
        );
      } else if (previewMode === "accepted") {
        void accept();
      }
      // 'fields' default: leave as-is
    }
  }, [previewMode, state.mode, s.kind, handleSample]);

  return (
    <div
      style={{
        padding: 18,
        marginBottom: 12,
        background: "linear-gradient(180deg, #fafffa 0%, #ffffff 100%)",
        border: "1px solid var(--ok-500)",
        borderRadius: 10,
        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <div style={{ fontWeight: 700, fontSize: 13, color: "var(--ok-700)" }}>
          ✨ 真实文档上传 · backend mode
        </div>
        <span style={{ fontSize: 10, color: "var(--ink-500)" }}>
          走 parse_pipeline · AI 抽字段 + 置信度 · 人审核后落 SQLite
        </span>
      </div>

      {/* === idle: drag-drop + click + 示例 === */}
      {s.kind === "idle" && (
        <>
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            style={{
              padding: "28px 16px",
              border: `2px dashed ${dragOver ? "var(--ok-500)" : "var(--ink-300)"}`,
              background: dragOver ? "var(--ok-100)" : "var(--ink-50)",
              borderRadius: 8,
              textAlign: "center",
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
          >
            <div style={{ fontSize: 28, marginBottom: 6 }}>📥</div>
            <div style={{ fontSize: 13, fontWeight: 600, color: "var(--ink-700)" }}>
              拖放文件到此 或 点击选择
            </div>
            <div style={{ fontSize: 11, color: "var(--ink-500)", marginTop: 4 }}>
              支持 .jpg / .png / .pdf / .xlsx / .xls / .csv,≤ 20 MB
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_MIMES}
              style={{ display: "none" }}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void handleFile(file);
              }}
            />
          </div>
          <div style={{ marginTop: 10, fontSize: 11, color: "var(--ink-500)" }}>
            📎 没有单据? 试试示例文档:
            {SAMPLE_FILES.map((sample, i) => (
              <span key={sample.path}>
                {i > 0 && " ·"}
                {" "}
                <button
                  onClick={() => void handleSample(sample)}
                  style={{
                    background: "none", border: "none", padding: 0,
                    color: "var(--brand-700)", textDecoration: "underline",
                    cursor: "pointer", fontSize: 11, fontFamily: "inherit",
                  }}
                >
                  {sample.label}
                </button>
              </span>
            ))}
          </div>
        </>
      )}

      {/* === uploading: progress === */}
      {s.kind === "uploading" && (
        <div style={{ padding: "20px 8px" }}>
          <div style={{ fontSize: 12, color: "var(--ink-700)", marginBottom: 6 }}>
            上传中: {s.filename}
          </div>
          <div style={{ height: 8, background: "var(--ink-100)", borderRadius: 4, overflow: "hidden" }}>
            <div
              style={{
                height: "100%", background: "var(--ok-500)",
                width: `${s.pct}%`, transition: "width 0.2s ease",
              }}
            />
          </div>
          <div style={{ fontSize: 11, color: "var(--ink-500)", marginTop: 4, textAlign: "right" }}>
            {s.pct}%
          </div>
        </div>
      )}

      {/* === submitting === */}
      {s.kind === "submitting" && (
        <div style={{ padding: "16px 8px", fontSize: 12, color: "var(--brand-700)" }}>
          ⏳ {s.message}
        </div>
      )}

      {/* === submitted === */}
      {s.kind === "submitted" && (
        <div style={{
          padding: 14, background: "var(--ok-100)", borderRadius: 6,
          border: "1px solid var(--ok-500)",
          fontSize: 12, color: "var(--ok-700)", lineHeight: 1.55,
        }}>
          {s.message}
          <div style={{ marginTop: 8 }}>
            <button onClick={dismiss} className="btn btn-secondary"
                    style={{ fontSize: 11, padding: "4px 10px" }}>
              再传一份
            </button>
          </div>
        </div>
      )}

      {/* === error === */}
      {s.kind === "error" && (
        <div style={{
          padding: 14, background: "var(--risk-100)", borderRadius: 6,
          border: "1px solid var(--risk-500)",
          fontSize: 12, color: "var(--risk-700)", lineHeight: 1.55,
        }}>
          ⚠ {s.message}
          <div style={{ marginTop: 8 }}>
            <button onClick={dismiss} className="btn btn-secondary"
                    style={{ fontSize: 11, padding: "4px 10px" }}>
              重试
            </button>
          </div>
        </div>
      )}

      {/* === candidate: fields + accept/edit/reject === */}
      {s.kind === "candidate" && (
        <CandidateCard
          response={s.resp}
          edits={s.edits}
          onEdit={(name, value) => setS({ ...s, edits: { ...s.edits, [name]: value } })}
          onAccept={accept}
          onReject={dismiss}
        />
      )}
    </div>
  );
}


function CandidateCard({
  response, edits, onEdit, onAccept, onReject,
}: {
  response: ParseUploadResponse;
  edits: Record<string, string>;
  onEdit: (name: string, value: string) => void;
  onAccept: () => void;
  onReject: () => void;
}) {
  const ent = response.candidate.entities[0];
  if (!ent) return null;

  const provider = response.provider;
  const overall = response.candidate.overall_confidence;
  const hasMock = (response.candidate.warnings || []).some((w) => w.includes("demo-mock"));

  return (
    <div>
      <div style={{
        padding: 10, background: "var(--brand-100)", borderRadius: 6,
        marginBottom: 10, fontSize: 11, color: "var(--brand-700)",
      }}>
        ✨ AI 抽取了 <b>{ent.fields.length}</b> 个字段(整体置信度 <b>{(overall * 100).toFixed(1)}%</b>)
        · 实体类型: <b>{ent.entity_type}</b>
        · provider: <b style={{ color: hasMock ? "var(--warn-700)" : "var(--ok-700)" }}>
          {provider}
        </b>
        · 文件 <code style={{ fontSize: 10 }}>{response.attachment.filename}</code>
        ({(response.attachment.size_bytes / 1024).toFixed(1)} KB)
      </div>

      {hasMock && (
        <div style={{
          padding: 8, background: "var(--warn-100)", borderRadius: 4,
          fontSize: 11, color: "var(--warn-700)", marginBottom: 10, lineHeight: 1.5,
        }}>
          ⚠ DemoMockProvider — 当前 deployment 没配 <code>ANTHROPIC_API_KEY</code>。
          字段值按文件名 hash 派生 (deterministic),不是真 AI 抽取。
          生产环境设置 key 后自动切到 Claude vision。
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 12 }}>
        {ent.fields.map((f) => (
          <FieldRow
            key={f.name}
            field={f}
            edit={edits[f.name]}
            onChange={(v) => onEdit(f.name, v)}
          />
        ))}
      </div>

      <div style={{ display: "flex", gap: 8 }}>
        <button
          onClick={onAccept}
          className="btn btn-primary"
          style={{ flex: 1, padding: "8px 12px", fontSize: 12, fontWeight: 700 }}
        >
          ✓ 采纳 → 走 confirm_writer + 触发主线
        </button>
        <button
          onClick={onReject}
          className="btn btn-secondary"
          style={{ padding: "8px 12px", fontSize: 12 }}
        >
          驳回
        </button>
      </div>
    </div>
  );
}


function FieldRow({
  field, edit, onChange,
}: {
  field: UploadField;
  edit: string | undefined;
  onChange: (v: string) => void;
}) {
  const confidence = field.confidence;
  const color = confidence >= 0.9 ? "var(--ok-700)" :
                confidence >= 0.7 ? "var(--warn-700)" :
                "var(--risk-700)";
  const bg = confidence >= 0.9 ? "var(--ok-100)" :
             confidence >= 0.7 ? "var(--warn-100)" :
             "var(--risk-100)";
  const displayValue = edit !== undefined ? edit : String(field.value ?? "");
  const edited = edit !== undefined;
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "100px 1fr 70px", gap: 8,
      alignItems: "center", padding: "6px 8px",
      background: edited ? "var(--brand-100)" : "transparent",
      borderRadius: 4,
    }}>
      <div style={{
        fontSize: 11, fontWeight: 600, color: "var(--ink-700)",
      }} title={field.source_span?.text || ""}>
        {field.name}
        {edited && " ✎"}
      </div>
      <input
        value={displayValue}
        onChange={(e) => onChange(e.target.value)}
        style={{
          padding: "4px 8px", fontSize: 12, border: "1px solid var(--ink-200)",
          borderRadius: 4, fontFamily: "inherit",
        }}
      />
      <div style={{
        textAlign: "center", padding: "2px 6px", borderRadius: 3,
        background: bg, color: color, fontSize: 11, fontWeight: 700,
        fontVariantNumeric: "tabular-nums",
      }} title={field.source_span?.text || `confidence ${confidence}`}>
        {(confidence * 100).toFixed(0)}%
      </div>
    </div>
  );
}


function _stringEditsToValues(
  edits: Record<string, string>, entity: UploadEntity,
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [name, sv] of Object.entries(edits)) {
    const field = entity.fields.find((f) => f.name === name);
    if (!field) { out[name] = sv; continue; }
    // 类型 coerce 留给后端 confirm_writer._coerce_value (Decimal/date/int/UUID 等)
    out[name] = sv;
  }
  return out;
}
