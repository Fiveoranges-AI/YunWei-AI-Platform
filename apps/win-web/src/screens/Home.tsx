// 首页 · AI 捕捉台 (AI Capture Desk).
//
// The anti-traditional-SaaS landing: instead of opening onto a CRM table, the
// user lands on a capture surface — drop / photo / paste / speak / ask at the
// top, the AI 待确认 (pending-confirmation) stream in the middle, a 今日老板简报
// (today's owner briefing) on the side, and the structured customer-asset base
// as a secondary entry at the bottom. "用户不填表，只丢资料、说人话、点确认。"

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
} from "react";
import type { GoFn } from "../App";
import { createIngestJobs, listIngestJobs } from "../api/ingest";
import { getMe, listCustomers } from "../api/client";
import type { CustomerDetail, IngestJob } from "../data/types";
import { I } from "../icons";
import { VoiceRecorder } from "../components/VoiceRecorder";
import { useIsDesktop, useIsTablet } from "../lib/breakpoints";
import { onCustomersChanged, markCustomersChanged } from "../lib/customerRefresh";
import { fmtCNY, fmtRelative } from "../lib/format";

const ACTIVE_POLL_MS = 2500;
const IDLE_POLL_MS = 6000;
const ERROR_POLL_MS = 8000;

const STAGE_LABEL: Record<string, string> = {
  received: "接收中",
  stored: "保存中",
  ocr: "识别中",
  route: "路由中",
  extract: "提取中",
  merge: "合并中",
  draft: "生成草稿",
  done: "完成",
};
const STAGES = ["received", "stored", "ocr", "route", "extract", "merge", "draft", "done"];

export function HomeScreen({ go }: { go: GoFn }) {
  const isDesktop = useIsDesktop();
  const isTablet = useIsTablet();
  const isWide = isDesktop || isTablet;

  const [greeting, setGreeting] = useState("你好");
  const [jobs, setJobs] = useState<IngestJob[]>([]);
  const [jobsReady, setJobsReady] = useState(false);
  const [customers, setCustomers] = useState<CustomerDetail[]>([]);

  // Greeting name (best-effort; mock fallback in dev).
  useEffect(() => {
    let cancelled = false;
    getMe()
      .then((u) => {
        if (cancelled) return;
        const name = (u.display_name || u.username || "").trim();
        setGreeting(name ? `你好，${name}` : "你好");
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  // Poll the active ingest queue so the 待确认 stream stays live. Failures
  // (e.g. no backend in dev) degrade to an empty, slow-polling state instead
  // of crashing the landing page.
  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    async function tick() {
      try {
        const rows = await listIngestJobs("active", 30);
        if (cancelled) return;
        setJobs(rows);
        setJobsReady(true);
        const inFlight = rows.some((j) => j.status === "queued" || j.status === "running");
        timer = window.setTimeout(tick, inFlight ? ACTIVE_POLL_MS : IDLE_POLL_MS);
      } catch {
        if (cancelled) return;
        setJobsReady(true);
        timer = window.setTimeout(tick, ERROR_POLL_MS);
      }
    }
    void tick();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, []);

  // Customer roster powers the briefing + asset base. Refresh on the shared
  // change event (fires after a confirm/import elsewhere).
  useEffect(() => {
    let cancelled = false;
    function load() {
      listCustomers()
        .then((rows) => {
          if (!cancelled) setCustomers(rows);
        })
        .catch(() => {});
    }
    load();
    const stop = onCustomersChanged(load);
    return () => {
      cancelled = true;
      stop();
    };
  }, []);

  const processing = useMemo(
    () => jobs.filter((j) => j.status === "queued" || j.status === "running"),
    [jobs],
  );
  const pending = useMemo(() => jobs.filter((j) => j.status === "extracted"), [jobs]);

  const stats = useMemo(() => deriveStats(customers, pending.length), [customers, pending.length]);
  const watchlist = useMemo(() => deriveWatchlist(customers), [customers]);

  function refreshJobsSoon() {
    // After a fresh import, optimistically re-poll so the new job shows up in
    // the stream without waiting for the next tick.
    listIngestJobs("active", 30)
      .then((rows) => setJobs(rows))
      .catch(() => {});
  }

  const capture = (
    <CaptureHero go={go} onSubmitted={refreshJobsSoon} compact={!isWide} />
  );
  const stream = (
    <PendingStream processing={processing} pending={pending} ready={jobsReady} go={go} />
  );
  const briefing = <BossBriefing stats={stats} watchlist={watchlist} go={go} />;
  const assets = <AssetBase stats={stats} go={go} />;

  // ──────────────── Desktop / tablet ────────────────
  if (isWide) {
    return (
      <div className="scroll" style={{ flex: 1, background: "var(--surface-2)" }}>
        <div style={{ maxWidth: 1080, margin: "0 auto", padding: "28px 32px 48px", width: "100%" }}>
          <Greeting greeting={greeting} />
          <div style={{ marginTop: 18 }}>{capture}</div>
          <div
            style={{
              marginTop: 22,
              display: "grid",
              gridTemplateColumns: isTablet ? "1fr" : "minmax(0,1.7fr) minmax(300px,1fr)",
              gap: 22,
              alignItems: "start",
            }}
          >
            <div style={{ minWidth: 0 }}>{stream}</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 22, minWidth: 0 }}>
              {briefing}
              {assets}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ──────────────── Mobile ────────────────
  return (
    <div className="screen" style={{ background: "var(--bg)" }}>
      <div style={{ padding: "14px 16px 6px" }}>
        <div style={{ fontSize: 22, fontWeight: 700, color: "var(--ink-900)", letterSpacing: "-0.01em" }}>
          {greeting}
        </div>
        <div style={{ fontSize: 12.5, color: "var(--ink-500)", marginTop: 3 }}>{todayLabel()}</div>
      </div>
      <div className="scroll" style={{ flex: 1, padding: "8px 16px 110px" }}>
        {capture}
        <div style={{ marginTop: 18 }}>{briefing}</div>
        <div style={{ marginTop: 18 }}>{stream}</div>
        <div style={{ marginTop: 18 }}>{assets}</div>
      </div>
    </div>
  );
}

// ════════════════ greeting ════════════════

function Greeting({ greeting }: { greeting: string }) {
  return (
    <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
      <div style={{ fontSize: 26, fontWeight: 700, color: "var(--ink-900)", letterSpacing: "-0.02em" }}>
        {greeting}
      </div>
      <div style={{ fontSize: 13, color: "var(--ink-400)" }}>{todayLabel()}</div>
    </div>
  );
}

function todayLabel(): string {
  try {
    return new Date().toLocaleDateString("zh-CN", { month: "long", day: "numeric", weekday: "long" });
  } catch {
    return "今天";
  }
}

// ════════════════ capture hero ════════════════

type StagedSourceHint = "file" | "camera" | "voice";
type StagedFile = { id: string; name: string; sourceHint: StagedSourceHint; blob: File; previewUrl?: string };

function CaptureHero({
  go,
  onSubmitted,
  compact,
}: {
  go: GoFn;
  onSubmitted: () => void;
  compact: boolean;
}) {
  const [pasted, setPasted] = useState("");
  const [files, setFiles] = useState<StagedFile[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [recording, setRecording] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const cameraRef = useRef<HTMLInputElement>(null);
  const voiceRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    return () => {
      for (const f of files) if (f.previewUrl) URL.revokeObjectURL(f.previewUrl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function addFile(blob: File, sourceHint: StagedSourceHint) {
    const previewUrl = blob.type.startsWith("image/") ? URL.createObjectURL(blob) : undefined;
    setFiles((f) => [...f, { id: Math.random().toString(36).slice(2), name: blob.name, sourceHint, blob, previewUrl }]);
  }
  function removeFile(id: string) {
    setFiles((f) => {
      const t = f.find((x) => x.id === id);
      if (t?.previewUrl) URL.revokeObjectURL(t.previewUrl);
      return f.filter((x) => x.id !== id);
    });
  }
  function onPicked(e: ChangeEvent<HTMLInputElement>, hint: StagedSourceHint) {
    const list = e.target.files;
    if (list) for (const f of Array.from(list)) addFile(f, hint);
    e.target.value = "";
  }
  function onDragOver(e: DragEvent<HTMLDivElement>) {
    if (!e.dataTransfer.types.includes("Files")) return;
    e.preventDefault();
    if (!dragActive) setDragActive(true);
  }
  function onDragLeave(e: DragEvent<HTMLDivElement>) {
    const next = e.relatedTarget as Node | null;
    if (next && (e.currentTarget as HTMLElement).contains(next)) return;
    setDragActive(false);
  }
  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragActive(false);
    for (const f of Array.from(e.dataTransfer.files ?? [])) addFile(f, "file");
  }

  const total = files.length + (pasted.trim() ? 1 : 0);
  const ready = total > 0;

  async function handleSubmit() {
    if (submitting || !ready) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const text = pasted.trim();
      const hasFiles = files.length > 0;
      const onlyText = !hasFiles && text.length > 0;
      const anyCamera = files.some((f) => f.sourceHint === "camera");
      const sourceHint: "file" | "camera" | "pasted_text" = onlyText
        ? "pasted_text"
        : anyCamera && files.every((f) => f.sourceHint === "camera")
          ? "camera"
          : "file";
      await createIngestJobs(files.map((f) => f.blob), { sourceHint, textContent: text || undefined });
      for (const f of files) if (f.previewUrl) URL.revokeObjectURL(f.previewUrl);
      setFiles([]);
      setPasted("");
      markCustomersChanged();
      onSubmitted();
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "上传失败，请重试");
    } finally {
      setSubmitting(false);
    }
  }

  const sources: { key: string; icon: JSX.Element; label: string; onClick: () => void }[] = [
    { key: "file", icon: I.cloud(18), label: "文件", onClick: () => fileRef.current?.click() },
    { key: "camera", icon: I.camera(18), label: "拍照", onClick: () => cameraRef.current?.click() },
    { key: "voice", icon: I.mic(18), label: "语音", onClick: () => setRecording(true) },
    { key: "ask", icon: I.ask(18), label: "提问", onClick: () => go("ask") },
  ];

  return (
    <div
      className="card"
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      style={{
        padding: compact ? 16 : 22,
        border: dragActive ? "1px solid var(--brand-500)" : "var(--tw-card-border)",
        transition: "border-color 120ms ease",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <input ref={fileRef} type="file" multiple accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,image/*"
        onChange={(e) => onPicked(e, "file")} style={{ display: "none" }} />
      <input ref={cameraRef} type="file" accept="image/*" capture="environment"
        onChange={(e) => onPicked(e, "camera")} style={{ display: "none" }} />
      <input ref={voiceRef} type="file" accept="audio/*"
        onChange={(e) => onPicked(e, "voice")} style={{ display: "none" }} />

      {recording && (
        <VoiceRecorder
          onRecorded={(file) => {
            addFile(file, "voice");
            setRecording(false);
          }}
          onClose={() => setRecording(false)}
          onUseFile={() => {
            setRecording(false);
            voiceRef.current?.click();
          }}
        />
      )}

      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <span className="pill pill-ai" style={{ gap: 5 }}>
          {I.spark(12)} AI 捕捉台
        </span>
        <span style={{ fontSize: 12.5, color: "var(--ink-500)" }}>
          先丢资料，AI 整理成客户资产 — 不用填表
        </span>
      </div>

      <div style={{ fontSize: compact ? 17 : 19, fontWeight: 700, color: "var(--ink-900)", letterSpacing: "-0.01em" }}>
        把客户资料丢给我
      </div>

      {/* Paste / drop zone */}
      <div
        style={{
          marginTop: 12,
          border: "1px solid var(--ink-100)",
          borderRadius: 12,
          background: dragActive ? "var(--brand-50)" : "var(--surface-2)",
          padding: 12,
          position: "relative",
        }}
      >
        <textarea
          rows={compact ? 3 : 3}
          value={pasted}
          disabled={submitting}
          onChange={(e) => setPasted(e.target.value)}
          placeholder="拖入合同 / Excel / 截图，粘贴微信聊天或邮件，或直接说一句话：今天见了万华王总，他想下月采购一批石墨匣钵，预算约 80 万…"
          style={{
            width: "100%",
            minHeight: compact ? 72 : 84,
            border: "none",
            outline: "none",
            resize: "none",
            background: "transparent",
            fontFamily: "var(--font)",
            fontSize: 14,
            lineHeight: 1.6,
            color: "var(--ink-900)",
            padding: 0,
            display: "block",
          }}
        />
        {dragActive && (
          <div
            style={{
              position: "absolute",
              inset: 0,
              borderRadius: 12,
              background: "rgba(45,155,216,0.10)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 14,
              fontWeight: 600,
              color: "var(--brand-700)",
              pointerEvents: "none",
            }}
          >
            松开放下，AI 自动识别
          </div>
        )}
      </div>

      {/* Source buttons */}
      <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
        {sources.map((s) => (
          <button
            key={s.key}
            onClick={s.onClick}
            disabled={submitting}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 7,
              padding: "8px 13px",
              borderRadius: 10,
              border: "1px solid var(--ink-100)",
              background: "var(--surface)",
              color: "var(--ink-700)",
              fontSize: 13,
              fontWeight: 600,
              fontFamily: "var(--font)",
              cursor: submitting ? "not-allowed" : "pointer",
            }}
          >
            <span style={{ color: "var(--ink-500)", display: "flex" }}>{s.icon}</span>
            {s.label}
          </button>
        ))}
      </div>

      {/* Staged items */}
      {ready && (
        <div style={{ marginTop: 12, border: "1px solid var(--ink-100)", borderRadius: 12, overflow: "hidden" }}>
          {files.map((f, i) => (
            <StagedRow
              key={f.id}
              icon={f.previewUrl ? <Thumb src={f.previewUrl} /> : iconForStaged(f)}
              text={f.name}
              last={i === files.length - 1 && !pasted.trim()}
              onRemove={() => removeFile(f.id)}
              disabled={submitting}
            />
          ))}
          {pasted.trim() && (
            <StagedRow
              icon={<span style={{ color: "var(--ink-500)" }}>{I.chat(15)}</span>}
              text={`粘贴文本 · ${pasted.length} 字`}
              last
              onRemove={() => setPasted("")}
              disabled={submitting}
            />
          )}
        </div>
      )}

      {submitError && (
        <div
          style={{
            marginTop: 12,
            padding: "9px 12px",
            borderRadius: 10,
            border: "1px solid var(--risk-100)",
            background: "var(--risk-50)",
            color: "var(--risk-700)",
            fontSize: 12.5,
            lineHeight: 1.5,
          }}
        >
          {submitError}
        </div>
      )}

      {/* Submit row */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 14, flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 160, fontSize: 11.5, color: "var(--ink-400)", display: "flex", alignItems: "center", gap: 5 }}>
          {I.shield(13, "var(--ink-300)")}
          AI 先生成「待确认卡片」，你确认后才入库
        </div>
        <button
          onClick={handleSubmit}
          disabled={!ready || submitting}
          className="btn btn-primary"
          style={{ opacity: ready && !submitting ? 1 : 0.55, cursor: ready && !submitting ? "pointer" : "not-allowed", height: 42 }}
        >
          {I.spark(15, "#fff")}
          <span>{submitting ? "上传中…" : ready ? `AI 识别入库 · ${total} 项` : "AI 识别入库"}</span>
        </button>
      </div>
    </div>
  );
}

function StagedRow({
  icon,
  text,
  last,
  onRemove,
  disabled,
}: {
  icon: JSX.Element;
  text: string;
  last?: boolean;
  onRemove: () => void;
  disabled: boolean;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "10px 13px",
        borderBottom: last ? "none" : "1px solid var(--ink-100)",
        background: "var(--surface)",
      }}
    >
      {icon}
      <div style={{ flex: 1, fontSize: 13, color: "var(--ink-900)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {text}
      </div>
      <button
        onClick={onRemove}
        disabled={disabled}
        aria-label="移除"
        style={{ background: "transparent", border: "none", cursor: disabled ? "not-allowed" : "pointer", color: "var(--ink-400)", padding: 4, display: "flex", opacity: disabled ? 0.4 : 1 }}
      >
        {I.close(15)}
      </button>
    </div>
  );
}

function Thumb({ src }: { src: string }) {
  return (
    <span style={{ width: 30, height: 30, borderRadius: 8, overflow: "hidden", border: "1px solid var(--ink-100)", flexShrink: 0, display: "block" }}>
      <img src={src} alt="" style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
    </span>
  );
}

function iconForStaged(f: StagedFile): JSX.Element {
  const t = f.blob.type || "";
  const name = f.name.toLowerCase();
  if (t.startsWith("image/")) return <span style={{ color: "var(--ink-500)" }}>{I.camera(15)}</span>;
  if (t.startsWith("audio/") || /\.(mp3|wav|m4a|ogg|amr)$/i.test(name)) return <span style={{ color: "var(--ink-500)" }}>{I.voice(15)}</span>;
  return <span style={{ color: "var(--ink-500)" }}>{I.doc(15)}</span>;
}

// ════════════════ AI 待确认 stream ════════════════

function PendingStream({
  processing,
  pending,
  ready,
  go,
}: {
  processing: IngestJob[];
  pending: IngestJob[];
  ready: boolean;
  go: GoFn;
}) {
  const empty = processing.length === 0 && pending.length === 0;
  return (
    <section>
      <div className="sec-h" style={{ alignItems: "center" }}>
        <h3 style={{ display: "inline-flex", alignItems: "center", gap: 7 }}>
          <span style={{ color: "var(--ai-600)", display: "flex" }}>{I.spark(13)}</span>
          AI 待确认
          {pending.length > 0 && (
            <span className="num" style={{ marginLeft: 2, color: "var(--warn-700)", fontWeight: 700 }}>{pending.length}</span>
          )}
        </h3>
        <button
          onClick={() => go("inbox")}
          className="more"
          style={{ background: "transparent", border: "none", cursor: "pointer", fontFamily: "var(--font)" }}
        >
          查看全部
        </button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {processing.map((j) => (
          <ProcessingCard key={j.id} job={j} onClick={() => go("inbox")} />
        ))}
        {pending.map((j) => (
          <PendingCard key={j.id} job={j} onClick={() => go("review", { jobId: j.id })} />
        ))}
        {empty && <StreamEmpty ready={ready} />}
      </div>
    </section>
  );
}

function ProcessingCard({ job, onClick }: { job: IngestJob; onClick: () => void }) {
  const idx = Math.max(0, STAGES.indexOf(job.stage));
  const pct = Math.round(((idx + 1) / STAGES.length) * 100);
  return (
    <button onClick={onClick} className="card" style={cardBtn}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <SourceTile job={job} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={oneLine}>{job.original_filename}</div>
          <div style={{ fontSize: 11.5, color: "var(--ink-500)", marginTop: 2 }}>
            {STAGE_LABEL[job.stage] ?? job.stage} · {job.status === "queued" ? "排队中" : "AI 处理中"}
          </div>
        </div>
        <span className="num" style={{ fontSize: 12, fontWeight: 700, color: "var(--ai-600)" }}>{pct}%</span>
      </div>
      <div style={{ height: 3, background: "var(--ink-50)", borderRadius: 99, overflow: "hidden", marginTop: 10 }}>
        <div style={{ height: "100%", width: pct + "%", background: "var(--ai-500)", transition: "width 240ms ease" }} />
      </div>
    </button>
  );
}

function PendingCard({ job, onClick }: { job: IngestJob; onClick: () => void }) {
  const when = job.finished_at ?? job.updated_at ?? job.created_at;
  return (
    <button onClick={onClick} className="card" style={cardBtn}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <SourceTile job={job} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <span style={{ ...oneLine, flex: 1 }}>{job.original_filename}</span>
            <span className="pill pill-warn" style={{ padding: "2px 7px", fontSize: 10.5, flexShrink: 0 }}>待确认</span>
          </div>
          <div style={{ fontSize: 11.5, color: "var(--ink-500)", marginTop: 3 }}>
            AI 草稿就绪 · {when ? fmtRelative(when) : "—"}
          </div>
        </div>
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "7px 12px",
            borderRadius: 9,
            background: "var(--ink-900)",
            color: "#fff",
            fontSize: 12.5,
            fontWeight: 600,
            flexShrink: 0,
          }}
        >
          {I.spark(12, "#fff")} 复核
        </span>
      </div>
    </button>
  );
}

function StreamEmpty({ ready }: { ready: boolean }) {
  return (
    <div className="card" style={{ padding: "26px 20px", textAlign: "center" }}>
      <div style={{ color: "var(--ai-500)", display: "flex", justifyContent: "center", marginBottom: 8 }}>
        {I.spark(22)}
      </div>
      <div style={{ fontSize: 14, fontWeight: 600, color: "var(--ink-800)" }}>
        {ready ? "暂无待确认资料" : "正在同步…"}
      </div>
      <div style={{ fontSize: 12.5, color: "var(--ink-500)", marginTop: 5, lineHeight: 1.6 }}>
        把合同、Excel、截图、名片或聊天记录丢到上方，<br />AI 识别后会在这里排队等你确认。
      </div>
    </div>
  );
}

function SourceTile({ job, size = 34 }: { job: IngestJob; size?: number }) {
  const hint = job.source_hint;
  const name = (job.original_filename || "").toLowerCase();
  let icon = I.doc(15);
  if (hint === "camera") icon = I.camera(15);
  else if (hint === "pasted_text") icon = I.chat(15);
  else if (/\.(mp3|wav|m4a|ogg|amr)$/i.test(name)) icon = I.voice(15);
  else if (/\.(png|jpe?g|gif|webp|bmp)$/i.test(name)) icon = I.camera(15);
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: 9,
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
  );
}

// ════════════════ 今日老板简报 ════════════════

type HomeStats = {
  customers: number;
  receivable: number;
  pending: number;
  highRisk: number;
  tasks: number;
  contacts: number;
  contracts: number;
};

function deriveStats(customers: CustomerDetail[], pending: number): HomeStats {
  let receivable = 0;
  let highRisk = 0;
  let tasks = 0;
  let contacts = 0;
  let contracts = 0;
  for (const c of customers) {
    receivable += c.metrics?.receivable ?? 0;
    tasks += c.metrics?.tasks ?? 0;
    contacts += c.metrics?.contacts ?? 0;
    contracts += c.metrics?.contracts ?? 0;
    if (c.risk?.level === "high") highRisk += 1;
  }
  return { customers: customers.length, receivable, pending, highRisk, tasks, contacts, contracts };
}

function deriveWatchlist(customers: CustomerDetail[]): CustomerDetail[] {
  const rank = (l?: string) => (l === "high" ? 0 : l === "med" ? 1 : 2);
  return [...customers]
    .filter((c) => c.risk?.level === "high" || c.risk?.level === "med")
    .sort((a, b) => rank(a.risk?.level) - rank(b.risk?.level))
    .slice(0, 4);
}

function BossBriefing({ stats, watchlist, go }: { stats: HomeStats; watchlist: CustomerDetail[]; go: GoFn }) {
  return (
    <section className="card" style={{ padding: 18 }}>
      <div className="sec-h" style={{ paddingBottom: 12 }}>
        <h3 style={{ display: "inline-flex", alignItems: "center", gap: 7 }}>
          <span style={{ color: "var(--warn-600)", display: "flex" }}>{I.bulb(13)}</span>
          今日老板简报
        </h3>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <Stat label="待确认" value={String(stats.pending)} tone={stats.pending > 0 ? "warn" : "ink"} onClick={() => go("inbox")} />
        <Stat label="高风险客户" value={String(stats.highRisk)} tone={stats.highRisk > 0 ? "risk" : "ink"} onClick={() => go("list")} />
        <Stat label="应收合计" value={stats.receivable > 0 ? fmtCNY(stats.receivable) : "¥ 0"} tone="ink" onClick={() => go("list")} />
        <Stat label="待办任务" value={String(stats.tasks)} tone="ink" onClick={() => go("list")} />
      </div>

      <div style={{ marginTop: 14 }}>
        <div style={{ fontSize: 10.5, fontWeight: 700, color: "var(--ink-500)", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 8 }}>
          需要关注
        </div>
        {watchlist.length === 0 ? (
          <div style={{ fontSize: 12.5, color: "var(--ink-400)", padding: "8px 0" }}>暂无风险客户，一切正常。</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            {watchlist.map((c) => (
              <button
                key={c.id}
                onClick={() => go("detail", { id: c.id })}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "8px 6px",
                  background: "transparent",
                  border: "none",
                  borderRadius: 8,
                  cursor: "pointer",
                  textAlign: "left",
                  fontFamily: "var(--font)",
                }}
              >
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: 3,
                    flexShrink: 0,
                    background: c.risk?.level === "high" ? "var(--risk-500)" : "var(--warn-500)",
                  }}
                />
                <span style={{ fontSize: 13, fontWeight: 600, color: "var(--ink-900)", flexShrink: 0 }}>{c.name}</span>
                <span style={{ ...oneLine, fontSize: 11.5, color: "var(--ink-500)" }}>
                  {c.risk?.note || c.risk?.label || ""}
                </span>
                <span style={{ color: "var(--ink-300)", marginLeft: "auto", flexShrink: 0 }}>{I.chev(13)}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function Stat({
  label,
  value,
  tone,
  onClick,
}: {
  label: string;
  value: string;
  tone: "warn" | "risk" | "ink";
  onClick: () => void;
}) {
  const color = tone === "warn" ? "var(--warn-700)" : tone === "risk" ? "var(--risk-700)" : "var(--ink-900)";
  return (
    <button
      onClick={onClick}
      style={{
        textAlign: "left",
        padding: "11px 12px",
        borderRadius: 11,
        border: "1px solid var(--ink-100)",
        background: "var(--surface-2)",
        cursor: "pointer",
        fontFamily: "var(--font)",
      }}
    >
      <div style={{ fontSize: 10.5, color: "var(--ink-500)", fontWeight: 600, letterSpacing: "0.04em" }}>{label}</div>
      <div className="num" style={{ fontSize: 19, fontWeight: 700, color, marginTop: 4, lineHeight: 1.1 }}>{value}</div>
    </button>
  );
}

// ════════════════ 客户资产库入口 ════════════════

function AssetBase({ stats, go }: { stats: HomeStats; go: GoFn }) {
  const tiles: { key: string; label: string; icon: JSX.Element; count?: number }[] = [
    { key: "customers", label: "客户", icon: I.customers(17), count: stats.customers },
    { key: "contacts", label: "联系人", icon: I.profile(17), count: stats.contacts },
    { key: "contracts", label: "合同", icon: I.doc(17), count: stats.contracts },
    { key: "orders", label: "订单", icon: I.task(17) },
    { key: "payments", label: "回款", icon: I.cash(17) },
    { key: "tasks", label: "跟进", icon: I.hand(17), count: stats.tasks },
    { key: "risks", label: "风险", icon: I.warn(17), count: stats.highRisk },
  ];
  return (
    <section className="card" style={{ padding: 18 }}>
      <div className="sec-h" style={{ paddingBottom: 12 }}>
        <h3 style={{ display: "inline-flex", alignItems: "center", gap: 7 }}>
          <span style={{ color: "var(--brand-600)", display: "flex" }}>{I.layers(13)}</span>
          客户资产库
        </h3>
        <button
          onClick={() => go("list")}
          className="more"
          style={{ background: "transparent", border: "none", cursor: "pointer", fontFamily: "var(--font)" }}
        >
          进入
        </button>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(92px, 1fr))", gap: 8 }}>
        {tiles.map((t) => (
          <button
            key={t.key}
            onClick={() => go("list")}
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 6,
              padding: "12px 10px",
              borderRadius: 11,
              border: "1px solid var(--ink-100)",
              background: "var(--surface-2)",
              cursor: "pointer",
              fontFamily: "var(--font)",
            }}
          >
            <span style={{ color: "var(--ink-600)", display: "flex" }}>{t.icon}</span>
            <span style={{ fontSize: 12.5, fontWeight: 600, color: "var(--ink-800)" }}>{t.label}</span>
            <span className="num" style={{ fontSize: 12, color: "var(--ink-400)", fontWeight: 600 }}>
              {t.count === undefined ? "查看" : t.count}
            </span>
          </button>
        ))}
      </div>
      <div style={{ fontSize: 11, color: "var(--ink-400)", marginTop: 12, lineHeight: 1.6 }}>
        表格只是结果视图与批量校对，不是录入入口 — 上面丢资料，这里查资产。
      </div>
    </section>
  );
}

const cardBtn: React.CSSProperties = {
  width: "100%",
  textAlign: "left",
  padding: 14,
  cursor: "pointer",
  fontFamily: "var(--font)",
  border: "var(--tw-card-border)",
  display: "block",
};

const oneLine: React.CSSProperties = {
  fontSize: 13.5,
  fontWeight: 600,
  color: "var(--ink-900)",
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
  minWidth: 0,
};
