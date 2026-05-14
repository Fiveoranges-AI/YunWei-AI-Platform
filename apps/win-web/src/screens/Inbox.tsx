import { useEffect, useMemo, useState } from "react";
import type { GoFn } from "../App";
import { deleteIngestJob, listIngestJobs, type ApiError } from "../api/ingest";
import type { IngestJob } from "../data/types";
import { I } from "../icons";
import { useIsDesktop } from "../lib/breakpoints";
import { fmtRelative } from "../lib/format";

const ACTIVE_POLL_MS = 2500;
const IDLE_POLL_MS = 6000;
const ERROR_POLL_MS = 5000;

type TabId = "processing" | "pending" | "history";
type InboxJob = IngestJob;

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

export function InboxScreen({ go, params }: { go: GoFn; params: Record<string, string> }) {
  const isDesktop = useIsDesktop();
  const [activeJobs, setActiveJobs] = useState<InboxJob[]>([]);
  const [historyJobs, setHistoryJobs] = useState<InboxJob[]>([]);
  const [tab, setTab] = useState<TabId>("pending");
  const [selectedId, setSelectedId] = useState<string | null>(params.jobId ?? null);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);

  // Active polling while mounted; auto-paces based on whether any job is in flight.
  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    async function tick() {
      try {
        const rows = await listInboxJobs("active", 50);
        if (cancelled) return;
        setActiveJobs(rows);
        const hasInFlight = rows.some((j) => j.status === "queued" || j.status === "running");
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

  // History is lazy — loaded the first time the user opens the tab.
  useEffect(() => {
    if (tab !== "history" || historyLoaded) return;
    let cancelled = false;
    setHistoryError(null);
    listInboxJobs("history", 50)
      .then((rows) => {
        if (!cancelled) {
          setHistoryJobs(rows);
          setHistoryLoaded(true);
        }
      })
      .catch((e) => {
        if (!cancelled) setHistoryError(e instanceof Error ? e.message : "历史加载失败");
      });
    return () => {
      cancelled = true;
    };
  }, [tab, historyLoaded]);

  const processing = useMemo(
    () => activeJobs.filter((j) => j.status === "queued" || j.status === "running"),
    [activeJobs],
  );
  const pending = useMemo(
    () => activeJobs.filter((j) => j.status === "extracted"),
    [activeJobs],
  );

  // If a pending job is selected by id but the list changes, fall back to first.
  const selected = pending.find((j) => j.id === selectedId) ?? pending[0] ?? null;

  async function handleDeletePending(job: InboxJob): Promise<void> {
    // Optimistically drop the row; if the server rejects, refetch will
    // restore it on the next tick.
    setActiveJobs((prev) => prev.filter((j) => j.id !== job.id));
    if (selectedId === job.id) setSelectedId(null);
    await deleteIngestJob(job.id);
  }

  return (
    <div style={{ flex: 1, display: "flex", minHeight: 0 }}>
      {/* Left pane — queue list */}
      <div
        style={{
          width: isDesktop ? 380 : "100%",
          flexShrink: 0,
          borderRight: isDesktop ? "1px solid var(--ink-100)" : "none",
          display: "flex",
          flexDirection: "column",
          background: "#fff",
        }}
      >
        <TabStrip
          tab={tab}
          setTab={setTab}
          counts={{ processing: processing.length, pending: pending.length, history: null }}
        />

        <div className="scroll" style={{ flex: 1 }}>
          {tab === "processing" && (
            <>
              {processing.length === 0 && (
                <EmptyHint text="暂无正在处理的任务" />
              )}
              {processing.map((j) => (
                <ProcessingRow key={j.id} job={j} />
              ))}
            </>
          )}
          {tab === "pending" && (
            <>
              {pending.length === 0 && (
                <EmptyHint text="所有上传都已确认归档" cta={{ label: "上传新资料", onClick: () => go("upload") }} />
              )}
              {pending.map((j) => (
                <PendingRow
                  key={j.id}
                  job={j}
                  active={isDesktop && selected?.id === j.id}
                  onClick={() => {
                    if (isDesktop) {
                      setSelectedId(j.id);
                    } else {
                      go("review", { jobId: j.id });
                    }
                  }}
                />
              ))}
            </>
          )}
          {tab === "history" && (
            <HistoryList
              jobs={historyJobs}
              error={historyError}
              onOpen={(j) => go("review", { jobId: j.id })}
            />
          )}
        </div>
      </div>

      {/* Right pane — preview (desktop only) */}
      {isDesktop && (
        <>
          {tab === "pending" && selected && (
            <PreviewPane
              job={selected}
              onReview={() => go("review", { jobId: selected.id })}
              onDelete={() => handleDeletePending(selected)}
            />
          )}
          {tab === "pending" && !selected && <EmptyPane msg="选择一项待确认资料查看 AI 提取结果" />}
          {tab === "processing" && <EmptyPane msg="处理中的资料无需复核" />}
          {tab === "history" && <EmptyPane msg="点击历史记录查看归档详情" />}
        </>
      )}
    </div>
  );
}

async function listInboxJobs(
  status: "active" | "history" | "all",
  limit: number,
): Promise<InboxJob[]> {
  const jobs = await listIngestJobs(status, limit);
  return jobs
    .sort((a, b) => jobSortTime(b) - jobSortTime(a))
    .slice(0, limit);
}

function jobSortTime(job: InboxJob): number {
  const raw = job.finished_at ?? job.updated_at ?? job.created_at;
  return raw ? new Date(raw).getTime() || 0 : 0;
}

// ──────────────── tab strip ────────────────

function TabStrip({
  tab,
  setTab,
  counts,
}: {
  tab: TabId;
  setTab: (t: TabId) => void;
  counts: { processing: number; pending: number; history: number | null };
}) {
  const items: { id: TabId; label: string; count: number | null; tone?: "ai" | "warn" }[] = [
    { id: "processing", label: "处理中", count: counts.processing, tone: "ai" },
    { id: "pending", label: "待确认", count: counts.pending, tone: "warn" },
    { id: "history", label: "历史", count: counts.history },
  ];
  return (
    <div
      style={{
        display: "flex",
        gap: 22,
        padding: "14px 24px 0",
        borderBottom: "1px solid var(--ink-100)",
      }}
    >
      {items.map((it) => {
        const active = tab === it.id;
        return (
          <button
            key={it.id}
            onClick={() => setTab(it.id)}
            style={{
              padding: "4px 0 12px",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              color: active ? "var(--ink-900)" : "var(--ink-400)",
              fontWeight: active ? 700 : 500,
              fontSize: 13,
              borderBottom: active ? "2px solid var(--ink-900)" : "2px solid transparent",
              marginBottom: -1,
              fontFamily: "var(--font)",
            }}
          >
            {it.label}
            {it.count !== null && (
              <span
                className="num"
                style={{
                  fontSize: 10.5,
                  fontWeight: 600,
                  color: active ? "var(--ink-500)" : "var(--ink-300)",
                }}
              >
                {it.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

// ──────────────── rows ────────────────

function sourceIcon(job: InboxJob): JSX.Element {
  const hint = job.source_hint;
  if (hint === "camera") return I.camera(14);
  if (hint === "pasted_text") return I.chat(14);
  const name = (job.original_filename || "").toLowerCase();
  if (/\.(mp3|wav|m4a|ogg|amr)$/i.test(name)) return I.voice(14);
  if (/\.(png|jpe?g|gif|webp|bmp)$/i.test(name)) return I.camera(14);
  return I.doc(14);
}

function SourceTile({ job, size = 32 }: { job: InboxJob; size?: number }) {
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
      {sourceIcon(job)}
    </div>
  );
}

function ProcessingRow({ job }: { job: InboxJob }) {
  // Backend doesn't expose a 0..1 progress, so approximate from stage order.
  const stages = ["received", "stored", "ocr", "route", "extract", "merge", "draft", "done"];
  const idx = Math.max(0, stages.indexOf(job.stage));
  const pct = Math.round(((idx + 1) / stages.length) * 100);
  return (
    <div style={{ padding: "14px 24px", borderBottom: "1px solid var(--ink-100)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <SourceTile job={job} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontSize: 13.5,
              fontWeight: 600,
              color: "var(--ink-900)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {job.original_filename}
          </div>
          <div style={{ fontSize: 11, color: "var(--ink-500)", marginTop: 2 }}>
            {STAGE_LABEL[job.stage] ?? job.stage} · {job.status === "queued" ? "排队中" : "进行中"}
          </div>
        </div>
        <div className="num" style={{ fontSize: 12, fontWeight: 600, color: "var(--ai-600)" }}>
          {pct}%
        </div>
      </div>
      <div
        style={{
          height: 2,
          background: "var(--ink-50)",
          borderRadius: 99,
          overflow: "hidden",
          marginTop: 10,
          marginLeft: 44,
        }}
      >
        <div style={{ height: "100%", width: pct + "%", background: "var(--ai-500)", transition: "width 240ms ease" }} />
      </div>
    </div>
  );
}

function PendingRow({
  job,
  active,
  onClick,
}: {
  job: InboxJob;
  active: boolean;
  onClick: () => void;
}) {
  const when = job.finished_at ?? job.updated_at ?? job.created_at;
  return (
    <button
      onClick={onClick}
      style={{
        width: "100%",
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "12px 24px",
        background: active ? "var(--brand-50)" : "transparent",
        border: "none",
        borderBottom: "1px solid var(--ink-100)",
        borderLeft: active ? "2px solid var(--brand-500)" : "2px solid transparent",
        paddingLeft: active ? 22 : 24,
        cursor: "pointer",
        textAlign: "left",
        fontFamily: "var(--font)",
      }}
    >
      <SourceTile job={job} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span
            style={{
              fontSize: 13.5,
              fontWeight: 600,
              color: "var(--ink-900)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              flex: 1,
              minWidth: 0,
            }}
          >
            {job.original_filename}
          </span>
          <span
            style={{
              fontSize: 9.5,
              fontWeight: 600,
              padding: "2px 5px",
              borderRadius: 4,
              background: "var(--warn-100)",
              color: "var(--warn-700)",
              flexShrink: 0,
            }}
          >
            待确认
          </span>
        </div>
        <div style={{ fontSize: 11, color: "var(--ink-500)", marginTop: 3 }}>
          AI 草稿就绪 · {when ? fmtRelative(when) : "—"}
        </div>
      </div>
    </button>
  );
}

function HistoryList({
  jobs,
  error,
  onOpen,
}: {
  jobs: InboxJob[];
  error: string | null;
  onOpen: (j: InboxJob) => void;
}) {
  if (error && jobs.length === 0) {
    return (
      <div style={{ padding: 24, fontSize: 13, color: "var(--risk-700)" }}>
        历史加载失败：{error}
      </div>
    );
  }
  if (jobs.length === 0) {
    return <EmptyHint text="暂无历史归档" />;
  }
  // Group by relative day buckets — today / yesterday / earlier.
  const today: InboxJob[] = [];
  const yesterday: InboxJob[] = [];
  const earlier: InboxJob[] = [];
  const now = Date.now();
  for (const j of jobs) {
    const when = j.finished_at ?? j.updated_at ?? j.created_at;
    if (!when) {
      earlier.push(j);
      continue;
    }
    const diffH = (now - new Date(when).getTime()) / 3_600_000;
    if (diffH < 24) today.push(j);
    else if (diffH < 48) yesterday.push(j);
    else earlier.push(j);
  }
  const renderRow = (j: InboxJob) => (
    <HistoryRow key={j.id} job={j} onClick={() => onOpen(j)} />
  );
  return (
    <>
      {today.length > 0 && (
        <>
          <DayHeader label="今天" />
          {today.map(renderRow)}
        </>
      )}
      {yesterday.length > 0 && (
        <>
          <DayHeader label="昨天" />
          {yesterday.map(renderRow)}
        </>
      )}
      {earlier.length > 0 && (
        <>
          <DayHeader label="更早" />
          {earlier.map(renderRow)}
        </>
      )}
    </>
  );
}

function DayHeader({ label }: { label: string }) {
  return (
    <div
      style={{
        padding: "14px 24px 6px",
        fontSize: 10.5,
        fontWeight: 700,
        color: "var(--ink-400)",
        letterSpacing: "0.08em",
        textTransform: "uppercase",
      }}
    >
      {label}
    </div>
  );
}

function HistoryRow({
  job,
  onClick,
}: {
  job: InboxJob;
  onClick: () => void;
}) {
  const when = job.finished_at ?? job.updated_at ?? job.created_at;
  const statusLabel =
    job.status === "confirmed" ? "已归档" :
    job.status === "failed" ? "失败" :
    job.status === "canceled" ? "已取消" : "未知";
  return (
    <button
      onClick={onClick}
      style={{
        width: "100%",
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "11px 24px",
        background: "transparent",
        border: "none",
        borderBottom: "1px solid var(--ink-100)",
        cursor: "pointer",
        textAlign: "left",
        fontFamily: "var(--font)",
      }}
    >
      <SourceTile job={job} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 13.5,
            fontWeight: 500,
            color: "var(--ink-900)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {job.original_filename}
        </div>
        <div style={{ fontSize: 11, color: "var(--ink-500)", marginTop: 3 }}>
          {statusLabel} · {when ? fmtRelative(when) : "—"}
        </div>
      </div>
      <span style={{ color: "var(--ink-400)" }}>{I.chev(13)}</span>
    </button>
  );
}

// ──────────────── right pane ────────────────

function PreviewPane({
  job,
  onReview,
  onDelete,
}: {
  job: InboxJob;
  onReview: () => void;
  onDelete: () => Promise<void>;
}) {
  const when = job.finished_at ?? job.updated_at ?? job.created_at;
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function handleDeleteClick(): Promise<void> {
    if (deleting) return;
    if (!window.confirm("确定删除该待确认任务？删除后不可恢复。")) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await onDelete();
    } catch (e) {
      const err = e as ApiError;
      setDeleteError(
        err.status === 409 ? "当前状态不支持删除" : err.message || "删除失败",
      );
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        minWidth: 0,
        background: "#fff",
      }}
    >
      {/* Header */}
      <div style={{ padding: "24px 40px 16px", borderBottom: "1px solid var(--ink-100)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
          <SourceTile job={job} size={28} />
          <span style={{ fontSize: 11.5, color: "var(--ink-500)", fontWeight: 500 }}>
            AI 草稿就绪 · {when ? fmtRelative(when) : "—"}
          </span>
        </div>
        <div
          style={{
            fontSize: 22,
            fontWeight: 700,
            color: "var(--ink-900)",
            letterSpacing: "-0.015em",
            lineHeight: 1.25,
            wordBreak: "break-word",
          }}
        >
          {job.original_filename}
        </div>
      </div>

      {/* Body — light summary; full review available via CTA below */}
      <div style={{ flex: 1, overflowY: "auto", padding: "24px 40px" }}>
        <FieldLabel>状态</FieldLabel>
        <div style={{ marginTop: 10, marginBottom: 24, display: "flex", alignItems: "center", gap: 10 }}>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              padding: "5px 10px",
              borderRadius: 99,
              background: "var(--warn-100)",
              color: "var(--warn-700)",
              fontSize: 12,
              fontWeight: 600,
            }}
          >
            <span style={{ width: 5, height: 5, borderRadius: 3, background: "currentColor" }} />
            等待你的确认
          </span>
          <span style={{ fontSize: 12, color: "var(--ink-500)" }}>
            打开复核查看 AI 抽取的字段、提取结果与来源依据。
          </span>
        </div>

        <FieldLabel>已知信息</FieldLabel>
        <div
          style={{
            marginTop: 10,
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 12,
          }}
        >
          <SummaryRow label="任务 ID" value={job.id.slice(0, 8) + "…"} mono />
          <SummaryRow label="来源" value={describeSource(job)} />
          <SummaryRow label="阶段" value={STAGE_LABEL[job.stage] ?? job.stage} />
          <SummaryRow label="尝试次数" value={String(job.attempts)} />
        </div>

        {job.progress_message && (
          <>
            <FieldLabel style={{ marginTop: 24 }}>处理备注</FieldLabel>
            <div
              style={{
                marginTop: 10,
                padding: 12,
                background: "var(--surface-2)",
                border: "1px solid var(--ink-100)",
                borderRadius: 10,
                fontSize: 13,
                color: "var(--ink-700)",
                lineHeight: 1.55,
              }}
            >
              {job.progress_message}
            </div>
          </>
        )}
      </div>

      {/* Footer */}
      <div
        style={{
          flexShrink: 0,
          padding: "14px 40px",
          borderTop: "1px solid var(--ink-100)",
          display: "flex",
          flexDirection: "column",
          gap: 6,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button
            onClick={() => void handleDeleteClick()}
            disabled={deleting}
            style={{
              height: 36,
              padding: "0 14px",
              borderRadius: 8,
              background: "transparent",
              color: "var(--risk-700)",
              border: "1px solid var(--ink-100)",
              fontSize: 13,
              fontWeight: 600,
              cursor: deleting ? "not-allowed" : "pointer",
              fontFamily: "var(--font)",
            }}
          >
            {deleting ? "删除中…" : "删除"}
          </button>
          <div style={{ flex: 1 }} />
          <button
            onClick={onReview}
            style={{
              height: 36,
              padding: "0 18px",
              borderRadius: 8,
              background: "var(--ink-900)",
              color: "#fff",
              border: "none",
              fontSize: 13,
              fontWeight: 600,
              cursor: "pointer",
              fontFamily: "var(--font)",
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            {I.spark(13, "#fff")} 打开 AI 复核
          </button>
        </div>
        {deleteError && (
          <div style={{ fontSize: 12, color: "var(--risk-700)", textAlign: "right" }}>
            {deleteError}
          </div>
        )}
      </div>
    </div>
  );
}

function SummaryRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div
      style={{
        padding: 12,
        background: "var(--surface-2)",
        border: "1px solid var(--ink-100)",
        borderRadius: 10,
      }}
    >
      <div
        style={{
          fontSize: 10.5,
          color: "var(--ink-500)",
          fontWeight: 600,
          letterSpacing: "0.06em",
          textTransform: "uppercase",
        }}
      >
        {label}
      </div>
      <div
        className={mono ? "mono-code" : "num"}
        style={{ fontSize: 13.5, color: "var(--ink-900)", marginTop: 4, fontWeight: 500 }}
      >
        {value}
      </div>
    </div>
  );
}

function FieldLabel({
  children,
  style,
}: {
  children: React.ReactNode;
  style?: React.CSSProperties;
}) {
  return (
    <div
      style={{
        fontSize: 10.5,
        fontWeight: 700,
        color: "var(--ink-500)",
        letterSpacing: "0.08em",
        textTransform: "uppercase",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

function EmptyPane({ msg }: { msg: string }) {
  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        color: "var(--ink-400)",
        fontSize: 13.5,
        background: "var(--surface-2)",
      }}
    >
      {msg}
    </div>
  );
}

function EmptyHint({
  text,
  cta,
}: {
  text: string;
  cta?: { label: string; onClick: () => void };
}) {
  return (
    <div
      style={{
        padding: "40px 24px",
        textAlign: "center",
        color: "var(--ink-400)",
        fontSize: 13,
      }}
    >
      <div>{text}</div>
      {cta && (
        <button
          onClick={cta.onClick}
          style={{
            marginTop: 12,
            padding: "8px 14px",
            borderRadius: 10,
            background: "var(--ink-900)",
            color: "#fff",
            border: "none",
            cursor: "pointer",
            fontSize: 13,
            fontWeight: 600,
            fontFamily: "var(--font)",
          }}
        >
          {cta.label}
        </button>
      )}
    </div>
  );
}

function describeSource(job: InboxJob): string {
  if (job.source_hint === "camera") return "拍照";
  if (job.source_hint === "pasted_text") return "粘贴文本";
  const name = (job.original_filename || "").toLowerCase();
  if (/\.(mp3|wav|m4a|ogg|amr)$/i.test(name)) return "语音";
  if (/\.(png|jpe?g|gif|webp|bmp)$/i.test(name)) return "图片";
  return "文件";
}
