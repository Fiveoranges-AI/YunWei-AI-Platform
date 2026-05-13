import { useEffect, useState } from "react";
import type { GoFn } from "../App";
import { getReview, listCustomersBasic } from "../api/client";
import {
  applyDraftEdit,
  archiveBatch,
  batchToReview,
  buildAutoConfirmRequest,
  clearLastBatch,
  confirmIngestJob,
  getIngestJob,
  getLastBatch,
  ignoreBatch,
  jobToBatch,
  parseAmountInput,
  setCustomerOverride,
  setLastBatch,
  type ArchiveResult,
  type Batch,
  type CustomerDecisionOverride,
} from "../api/ingest";
import { EvidenceChip } from "../components/EvidenceChip";
import { Mono } from "../components/Mono";
import { Section } from "../components/Section";
import type {
  CustomerListItem,
  EditableDraftPath,
  EditableFieldMeta,
  Review,
  ReviewExtraction,
  SchemaSummary,
  SchemaSummaryItem,
} from "../data/types";
import { I } from "../icons";
import { useIsDesktop } from "../lib/breakpoints";
import { markCustomersChanged } from "../lib/customerRefresh";

const EXTRACTION_STYLE: Record<
  ReviewExtraction["kind"],
  { icon: (s?: number) => React.ReactNode; bg: string; fg: string }
> = {
  commitment: { icon: (s = 15) => I.hand(s), bg: "var(--warn-100)", fg: "var(--warn-700)" },
  task: { icon: (s = 15) => I.task(s), bg: "var(--ai-100)", fg: "var(--ai-500)" },
  risk: { icon: (s = 15) => I.warn(s), bg: "var(--risk-100)", fg: "var(--risk-500)" },
  contact: { icon: (s = 15) => I.customers(s), bg: "var(--brand-100)", fg: "var(--brand-600)" },
};

export function ReviewScreen({
  go,
  params,
}: {
  go: GoFn;
  params?: Record<string, string>;
}) {
  const jobId = params?.jobId;
  const isDesktop = useIsDesktop();
  const [review, setReview] = useState<Review | null>(null);
  const [batch, setBatch] = useState<Batch | null>(null);
  const [showEvidence, setShowEvidence] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const [archiveError, setArchiveError] = useState<string | null>(null);
  const [archiveResult, setArchiveResult] = useState<ArchiveResult | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  // null = full panel; non-null = single-field editor
  const [singleEditPath, setSingleEditPath] = useState<EditableDraftPath | null>(null);
  const [primaryEntryIndex, setPrimaryEntryIndex] = useState<number>(-1);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [allCustomers, setAllCustomers] = useState<CustomerListItem[] | null>(null);
  const [customersLoading, setCustomersLoading] = useState(false);
  const [customersError, setCustomersError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      // 1) Preferred path: a job_id in the URL — survives refresh and is
      //    how Upload.tsx hands off in job mode.
      if (jobId) {
        try {
          const job = await getIngestJob(jobId);
          if (cancelled) return;
          const fromJob = jobToBatch(job);
          if (!fromJob) {
            setReviewError(
              job.status === "failed"
                ? job.error_message ?? "任务失败"
                : job.status === "canceled"
                  ? "任务已取消"
                  : "任务尚未生成草稿",
            );
            return;
          }
          setBatch(fromJob);
          setReview(batchToReview(fromJob));
          setLastBatch(fromJob);
          return;
        } catch (e) {
          if (cancelled) return;
          setReviewError(e instanceof Error ? e.message : "任务加载失败");
          return;
        }
      }
      // 2) Legacy in-memory batch path (set by older flows / future fallback).
      const inMem = getLastBatch();
      const fromBatch = inMem ? batchToReview(inMem) : null;
      if (fromBatch) {
        if (!cancelled) {
          setBatch(inMem);
          setReview(fromBatch);
        }
        return;
      }
      // 3) Last resort: ask backend for a /review mock so the design preview
      //    still works when /review is opened cold.
      try {
        const r = await getReview("last");
        if (!cancelled) setReview(r);
      } catch (e) {
        if (!cancelled) {
          setReviewError(e instanceof Error ? e.message : "没有可复核的上传批次");
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  // Compute primary entry index whenever batch changes — must match the
  // "first successful entry" logic that batchToReview uses.
  useEffect(() => {
    if (!batch) {
      setPrimaryEntryIndex(-1);
      return;
    }
    const idx = batch.entries.findIndex((e) => e.result.ok);
    setPrimaryEntryIndex(idx);
  }, [batch]);

  function handleFieldSave(path: EditableDraftPath, raw: string | number | null) {
    if (!batch || primaryEntryIndex < 0) return;
    const updated = applyDraftEdit(batch, primaryEntryIndex, path, raw);
    setBatch(updated);
    setLastBatch(updated);
    const fresh = batchToReview(updated);
    if (fresh) setReview(fresh);
  }

  function openPicker() {
    if (!batch || primaryEntryIndex < 0) return;
    setPickerOpen(true);
    if (allCustomers === null && !customersLoading) {
      setCustomersLoading(true);
      setCustomersError(null);
      listCustomersBasic()
        .then((rows) => setAllCustomers(rows))
        .catch((e) =>
          setCustomersError(e instanceof Error ? e.message : "客户列表加载失败"),
        )
        .finally(() => setCustomersLoading(false));
    }
  }

  function handlePickExisting(c: CustomerListItem) {
    if (!batch || primaryEntryIndex < 0) return;
    const override: CustomerDecisionOverride = {
      kind: "bind_existing",
      existing_id: c.id,
      existing_name: c.name,
      updateMaster: false,
    };
    const updated = setCustomerOverride(batch, primaryEntryIndex, override);
    setBatch(updated);
    setLastBatch(updated);
    setPickerOpen(false);
  }

  function handlePickNew() {
    if (!batch || primaryEntryIndex < 0) return;
    const updated = setCustomerOverride(batch, primaryEntryIndex, { kind: "new" });
    setBatch(updated);
    setLastBatch(updated);
    setPickerOpen(false);
  }

  function handleClearOverride() {
    if (!batch || primaryEntryIndex < 0) return;
    const updated = setCustomerOverride(batch, primaryEntryIndex, undefined);
    setBatch(updated);
    setLastBatch(updated);
  }

  function handleToggleUpdateMaster(next: boolean) {
    if (!batch || primaryEntryIndex < 0) return;
    const cur = batch.entries[primaryEntryIndex]?.customerDecisionOverride;
    if (!cur || cur.kind !== "bind_existing") return;
    const updated = setCustomerOverride(batch, primaryEntryIndex, {
      ...cur,
      updateMaster: next,
    });
    setBatch(updated);
    setLastBatch(updated);
  }

  async function handleArchive() {
    if (archiving) return;
    if (editorOpen) return;
    setArchiving(true);
    setArchiveError(null);
    try {
      if (!batch) {
        setDone(true);
        return;
      }
      // Job-mode single-entry path: use the job-aware confirm so the job
      // row flips to `confirmed` alongside the document. Multi-entry
      // batches (legacy /auto flow) keep the per-document archive.
      if (jobId && batch.entries.length === 1) {
        const entry = batch.entries[0]!;
        const customerIds: string[] = [];
        const warnings: string[] = [];
        if (entry.result.ok) {
          const payload = buildAutoConfirmRequest(
            entry.result.raw,
            entry.customerDecisionOverride,
          );
          const confirmed = await confirmIngestJob(jobId, payload);
          const cid = confirmed.created_entities?.customer_id;
          if (cid) customerIds.push(cid);
          if (confirmed.warnings) warnings.push(...confirmed.warnings);
        }
        clearLastBatch();
        setArchiveResult({
          confirmedDocuments: entry.result.ok ? 1 : 0,
          customerIds,
          warnings,
        });
        markCustomersChanged();
        setDone(true);
        return;
      }
      const result = await archiveBatch(batch);
      clearLastBatch();
      setArchiveResult(result);
      markCustomersChanged();
      setDone(true);
    } catch (e) {
      setArchiveError(e instanceof Error ? e.message : "归档失败");
    } finally {
      setArchiving(false);
    }
  }

  async function handleIgnore() {
    if (archiving) return;
    setArchiving(true);
    setArchiveError(null);
    try {
      if (batch) {
        await ignoreBatch(batch);
        clearLastBatch();
      }
      go("upload");
    } catch (e) {
      setArchiveError(e instanceof Error ? e.message : "忽略失败");
    } finally {
      setArchiving(false);
    }
  }

  if (reviewError && !review) {
    return (
      <div
        className="screen"
        style={{ background: "var(--bg)", alignItems: "center", justifyContent: "center", display: "flex" }}
      >
        <div style={{ textAlign: "center", padding: 24 }}>
          <div style={{ fontSize: 18, fontWeight: 700, color: "var(--ink-900)", marginBottom: 8 }}>
            暂无待确认资料
          </div>
          <div style={{ color: "var(--ink-500)", fontSize: 13, marginBottom: 16 }}>{reviewError}</div>
          <button className="btn btn-primary" onClick={() => go("upload")}>
            {I.cloud(16, "#fff")}
            <span>上传资料</span>
          </button>
        </div>
      </div>
    );
  }

  if (!review) {
    return (
      <div
        className="screen"
        style={{ background: "var(--bg)", alignItems: "center", justifyContent: "center", display: "flex" }}
      >
        <div style={{ color: "var(--ink-400)", fontSize: 14 }}>AI 整理中…</div>
      </div>
    );
  }

  if (done) {
    return (
      <div
        className="screen"
        style={{ background: "var(--bg)", alignItems: "center", justifyContent: "center", display: "flex" }}
      >
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
            已归档到 {review.customer.name}
          </div>
          <div style={{ fontSize: 14, color: "var(--ink-500)", marginTop: 6 }}>
            共 {review.extractions.length} 项已写入客户档案
          </div>
          <div style={{ display: "flex", gap: 8, justifyContent: "center", marginTop: 24 }}>
            <button className="btn btn-secondary" onClick={() => go("upload")}>
              继续上传
            </button>
            <button
              className="btn btn-primary"
              onClick={() => {
                const customerId = archiveResult?.customerIds[0];
                if (customerId) go("detail", { id: customerId });
                else go("list");
              }}
            >
              {archiveResult?.customerIds[0] ? "查看客户档案" : "返回客户列表"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="screen" style={{ background: "var(--bg)" }}>
      {/* Top bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: isDesktop ? "16px 32px 8px" : "6px 16px 8px",
          maxWidth: isDesktop ? 1080 : undefined,
          width: "100%",
          margin: "0 auto",
        }}
      >
        <button
          onClick={() => go("upload")}
          style={{
            width: 36,
            height: 36,
            borderRadius: 18,
            background: "transparent",
            border: "none",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--ink-700)",
            cursor: "pointer",
          }}
        >
          {I.close(20)}
        </button>
        <div style={{ fontSize: 15, fontWeight: 600, color: "var(--ink-900)" }}>AI 已整理完成</div>
        <div style={{ width: 36 }} />
      </div>

      <div
        className="scroll"
        style={{
          flex: 1,
          padding: isDesktop ? "0 32px 24px" : "0 16px 16px",
          maxWidth: isDesktop ? 1080 : undefined,
          width: "100%",
          margin: "0 auto",
        }}
      >
        {/* Status banner */}
        <div
          className="ai-surface"
          style={{ padding: "14px 16px", marginBottom: 12, display: "flex", gap: 12, alignItems: "center" }}
        >
          <div
            style={{
              width: 40,
              height: 40,
              borderRadius: 12,
              background: "rgba(255,255,255,0.8)",
              color: "var(--ai-500)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            {I.spark(20)}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: "var(--ink-900)" }}>
              识别完成 · {review.extractions.length} 个对象
            </div>
            <div style={{ fontSize: 12, color: "var(--ink-700)", marginTop: 2 }}>
              请确认 AI 的判断后，点击底部归档
            </div>
          </div>
          <span
            className={`pill ${
              review.confidence >= 0.9 ? "pill-ok" : review.confidence >= 0.7 ? "pill-warn" : "pill-risk"
            }`}
          >
            ● {Math.round(review.confidence * 100)}%
          </span>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: isDesktop ? "1fr 1fr" : "1fr",
            gap: isDesktop ? 16 : 0,
          }}
        >
          {/* Left column on desktop, top on mobile */}
          <div>
            {/* Customer match */}
            <Section title="归属客户">
              <div className="card" style={{ padding: 14 }}>
                <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                  <Mono
                    text={review.customer.name.slice(0, 2)}
                    color="#1f6c8a"
                    size={44}
                    radius={12}
                    fontSize={14}
                  />
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{ fontSize: 16, fontWeight: 700, color: "var(--ink-900)" }}>
                        {review.customer.name}
                      </span>
                      <span className="pill pill-brand" style={{ fontSize: 10 }}>
                        {review.customer.isExisting ? "已存在客户" : "新客户"}
                      </span>
                    </div>
                    <div
                      style={{
                        fontSize: 12,
                        color: "var(--ink-500)",
                        marginTop: 4,
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                      }}
                    >
                      <span style={{ color: "var(--ai-500)" }}>{I.spark(11)}</span>
                      {review.customer.isExisting
                        ? `AI 在数据库中匹配到 "${review.customer.name}"，请确认是否复用`
                        : `AI 从 ${review.docType || "上传内容"} 识别到新客户 "${review.customer.name}"`}
                    </div>
                  </div>
                  <button
                    onClick={openPicker}
                    disabled={!batch}
                    title={!batch ? "复核数据来自示例，无法编辑" : undefined}
                    style={{
                      background: "var(--surface-3)",
                      border: "1px solid var(--ink-100)",
                      borderRadius: 8,
                      padding: "6px 10px",
                      fontSize: 12,
                      color: "var(--ink-700)",
                      fontWeight: 500,
                      cursor: batch ? "pointer" : "not-allowed",
                      opacity: batch ? 1 : 0.5,
                    }}
                  >
                    更换
                  </button>
                </div>
                {(() => {
                  const currentOverride =
                    batch?.entries[primaryEntryIndex]?.customerDecisionOverride;
                  if (!currentOverride) return null;
                  if (currentOverride.kind === "bind_existing") {
                    return (
                      <div
                        style={{
                          marginTop: 8,
                          padding: "8px 10px",
                          background: "var(--ai-100)",
                          borderRadius: 8,
                        }}
                      >
                        <div style={{ fontSize: 12, color: "var(--ink-700)" }}>
                          将归档到：<strong>{currentOverride.existing_name}</strong>
                        </div>
                        <div style={{ fontSize: 11, color: "var(--ink-500)", marginTop: 4 }}>
                          手动选择已有客户 · 客户资料：
                          {currentOverride.updateMaster ? "本次会更新" : "不更新"}
                        </div>
                        <label
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 6,
                            marginTop: 6,
                            fontSize: 11,
                            color: "var(--ink-700)",
                            cursor: "pointer",
                          }}
                        >
                          <input
                            type="checkbox"
                            checked={currentOverride.updateMaster}
                            onChange={(e) => handleToggleUpdateMaster(e.target.checked)}
                          />
                          用本次提取信息更新客户资料
                        </label>
                        <button
                          onClick={handleClearOverride}
                          style={{
                            marginTop: 6,
                            fontSize: 11,
                            color: "var(--ink-500)",
                            background: "transparent",
                            border: "none",
                            cursor: "pointer",
                            padding: 0,
                            textDecoration: "underline",
                          }}
                        >
                          还原 AI 默认匹配
                        </button>
                      </div>
                    );
                  }
                  // currentOverride.kind === "new"
                  return (
                    <div
                      style={{
                        marginTop: 8,
                        padding: "8px 10px",
                        background: "var(--ai-100)",
                        borderRadius: 8,
                      }}
                    >
                      <div style={{ fontSize: 12, color: "var(--ink-700)" }}>
                        将创建为新客户
                      </div>
                      <button
                        onClick={handleClearOverride}
                        style={{
                          marginTop: 6,
                          fontSize: 11,
                          color: "var(--ink-500)",
                          background: "transparent",
                          border: "none",
                          cursor: "pointer",
                          padding: 0,
                          textDecoration: "underline",
                        }}
                      >
                        还原 AI 默认匹配
                      </button>
                    </div>
                  );
                })()}
              </div>
            </Section>

            {/* Identified fields */}
            <Section title="识别信息">
              <div className="card" style={{ padding: "4px 0" }}>
                {review.fields.map((f, i) => {
                  const clickable = Boolean(f.path && batch);
                  const handleClick = () => {
                    if (!f.path || !batch) return;
                    setSingleEditPath(f.path);
                    setEditorOpen(true);
                  };
                  return (
                    <div key={f.key}>
                      {i > 0 && <div style={{ height: 1, background: "var(--ink-100)", marginLeft: 14 }} />}
                      <div
                        role={clickable ? "button" : undefined}
                        tabIndex={clickable ? 0 : undefined}
                        onClick={clickable ? handleClick : undefined}
                        onKeyDown={
                          clickable
                            ? (e) => {
                                if (e.key === "Enter" || e.key === " ") {
                                  e.preventDefault();
                                  handleClick();
                                }
                              }
                            : undefined
                        }
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 10,
                          padding: "12px 14px",
                          cursor: clickable ? "pointer" : "default",
                        }}
                      >
                        <div style={{ width: 80, fontSize: 12, color: "var(--ink-500)" }}>{f.key}</div>
                        <div style={{ flex: 1, fontSize: 14, color: "var(--ink-900)", fontWeight: 500 }}>
                          {f.value}
                        </div>
                        {f.conf === "med" && (
                          <span className="pill pill-warn" style={{ fontSize: 10 }}>
                            需复核
                          </span>
                        )}
                        <span style={{ color: "var(--ink-400)" }}>{I.chev(13)}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </Section>

            {/* Missing fields */}
            {(() => {
              const missingItems: { path?: EditableDraftPath; label: string }[] =
                review.missingFields && review.missingFields.length
                  ? review.missingFields.map((m) => ({ path: m.path, label: m.label }))
                  : review.missing.map((m) => ({ label: m }));
              if (missingItems.length === 0) return null;
              return (
                <Section title="待补充字段">
                  <div
                    className="card"
                    style={{ padding: 12, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}
                  >
                    <span style={{ color: "var(--warn-500)" }}>{I.warn(14)}</span>
                    <span style={{ fontSize: 12, color: "var(--ink-500)" }}>未识别到：</span>
                    {missingItems.map((item) => {
                      const clickable = Boolean(item.path && batch);
                      return (
                        <button
                          key={item.label}
                          className="pill pill-warn"
                          onClick={() => {
                            if (!item.path || !batch) return;
                            setSingleEditPath(item.path);
                            setEditorOpen(true);
                          }}
                          disabled={!clickable}
                          style={{
                            fontSize: 11,
                            cursor: clickable ? "pointer" : "not-allowed",
                            border: "1px dashed #e5b873",
                            background: "#fff7e8",
                            opacity: clickable ? 1 : 0.6,
                          }}
                        >
                          + {item.label}
                        </button>
                      );
                    })}
                  </div>
                </Section>
              );
            })()}

            {review.schemaSummary && (
              <SchemaSummarySection summary={review.schemaSummary} />
            )}
          </div>

          {/* Right column on desktop, below on mobile */}
          <div>
            {/* Extractions */}
            <Section title="AI 提取结论" count={review.extractions.length}>
              {review.extractions.map((e, i) => {
                const style = EXTRACTION_STYLE[e.kind];
                return (
                  <div key={i} className="card" style={{ padding: 12, marginBottom: 8 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                      <div
                        style={{
                          width: 26,
                          height: 26,
                          borderRadius: 8,
                          background: style.bg,
                          color: style.fg,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                        }}
                      >
                        {style.icon(15)}
                      </div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: "var(--ink-700)" }}>{e.title}</div>
                      {e.conf === "med" && (
                        <span className="pill pill-warn" style={{ fontSize: 10, marginLeft: "auto" }}>
                          需复核
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: 14, color: "var(--ink-900)", lineHeight: 1.5 }}>{e.text}</div>
                    <div
                      style={{
                        display: "flex",
                        gap: 6,
                        marginTop: 8,
                        flexWrap: "wrap",
                        alignItems: "center",
                      }}
                    >
                      <span style={{ fontSize: 11, color: "var(--ink-500)" }}>来源：</span>
                      <EvidenceChip
                        type={e.source.type}
                        label={e.source.label}
                        onClick={() => setShowEvidence(e.source.label)}
                      />
                    </div>
                  </div>
                );
              })}
            </Section>

            {/* Source documents */}
            <Section title="来源依据" count={review.evidence.length}>
              <div className="card" style={{ padding: "4px 0" }}>
                {review.evidence.map((e, i) => (
                  <div key={e.id}>
                    {i > 0 && <div style={{ height: 1, background: "var(--ink-100)", marginLeft: 60 }} />}
                    <button
                      onClick={() => setShowEvidence(e.label)}
                      style={{
                        width: "100%",
                        display: "flex",
                        alignItems: "center",
                        gap: 12,
                        padding: "12px 14px",
                        background: "transparent",
                        border: "none",
                        textAlign: "left",
                        cursor: "pointer",
                      }}
                    >
                      <div
                        style={{
                          width: 36,
                          height: 36,
                          borderRadius: 10,
                          background: "var(--surface-3)",
                          color: "var(--ink-600)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                        }}
                      >
                        {e.type.includes("微信") ? I.wechat(16) : e.type.includes("语音") ? I.voice(16) : I.doc(16)}
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 14, fontWeight: 600, color: "var(--ink-900)" }}>{e.label}</div>
                        <div style={{ fontSize: 12, color: "var(--ink-500)", marginTop: 2 }}>{e.preview}</div>
                      </div>
                      <span style={{ color: "var(--ink-400)" }}>{I.chev(14)}</span>
                    </button>
                  </div>
                ))}
              </div>
            </Section>
          </div>
        </div>
      </div>

      {archiveError && (
        <div
          style={{
            margin: isDesktop ? "0 auto 10px" : "0 16px 10px",
            maxWidth: isDesktop ? 1080 : undefined,
            padding: "10px 12px",
            borderRadius: 10,
            border: "1px solid var(--risk-100)",
            background: "#fff1f0",
            color: "var(--risk-500)",
            fontSize: 12,
            lineHeight: 1.5,
          }}
        >
          {archiveError}
        </div>
      )}

      {/* Bottom action bar */}
      <div
        style={{
          flexShrink: 0,
          padding: isDesktop ? "12px 32px 16px" : "12px 16px 14px",
          background: "var(--bg)",
          borderTop: "1px solid var(--ink-100)",
        }}
      >
        <div
          style={{
            display: "flex",
            gap: 8,
            maxWidth: isDesktop ? 1080 : undefined,
            margin: "0 auto",
          }}
        >
          <button
            className="btn btn-secondary"
            style={{ flex: "0 0 auto", padding: "14px 14px" }}
            onClick={handleIgnore}
            disabled={archiving}
          >
            {archiving ? "处理中…" : "忽略"}
          </button>
          <button
            className="btn btn-secondary"
            style={{ flex: 1 }}
            onClick={() => {
              setSingleEditPath(null);
              setEditorOpen(true);
            }}
            disabled={archiving || done || !batch}
            title={!batch ? "复核数据来自示例，无法编辑" : undefined}
          >
            修改
          </button>
          <button className="btn btn-primary" style={{ flex: 1.4 }} onClick={handleArchive} disabled={archiving}>
            {I.check(16, "#fff")} {archiving ? "归档中…" : "确认归档"}
          </button>
        </div>
      </div>

      {/* Evidence sheet */}
      {showEvidence && (
        <EvidenceSheet
          label={showEvidence}
          onClose={() => setShowEvidence(null)}
          isDesktop={isDesktop}
        />
      )}

      {/* Edit panel */}
      {editorOpen && (
        <EditPanel
          batch={batch}
          entryIndex={primaryEntryIndex}
          onlyPath={singleEditPath}
          isDesktop={isDesktop}
          onClose={() => {
            setEditorOpen(false);
            setSingleEditPath(null);
          }}
          onSave={handleFieldSave}
        />
      )}

      {/* Customer picker */}
      {pickerOpen && (
        <CustomerPicker
          customers={allCustomers}
          loading={customersLoading}
          error={customersError}
          onClose={() => setPickerOpen(false)}
          onPickExisting={handlePickExisting}
          onPickNew={handlePickNew}
          isDesktop={isDesktop}
        />
      )}
    </div>
  );
}

// Compact diagnostic block: which schemas the router picked, what each
// schema actually returned, what's missing, and the final draft status.
// Built from raw /auto response — see api/ingest.ts buildSchemaSummary.
function SchemaSummarySection({ summary }: { summary: SchemaSummary }) {
  const {
    selectedSchemas,
    routePlanMissing,
    pipelineResultsMissing,
    finalDraftStatus,
    generalWarnings,
  } = summary;

  const statusChips: Array<{ label: string; ok: boolean }> = [
    { label: "客户", ok: finalDraftStatus.hasCustomer },
    { label: "联系人", ok: finalDraftStatus.hasContacts },
    { label: "合同", ok: finalDraftStatus.hasContract },
    { label: "订单", ok: finalDraftStatus.hasOrder },
    { label: "订单金额", ok: finalDraftStatus.hasOrderAmount },
    { label: "付款节点", ok: finalDraftStatus.hasPaymentMilestones },
  ];

  return (
    <Section title="Schema 路由与抽取摘要">
      <div className="card" style={{ padding: 12 }}>
        {routePlanMissing && (
          <div style={{ fontSize: 12, color: "var(--warn-700)", marginBottom: 8 }}>
            后端未返回 route_plan，无法显示 schema 路由
          </div>
        )}
        {pipelineResultsMissing && !routePlanMissing && (
          <div style={{ fontSize: 12, color: "var(--warn-700)", marginBottom: 8 }}>
            后端未返回 pipeline_results
          </div>
        )}

        {/* Final draft status — always shown so reviewers know what survived merge */}
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 11, color: "var(--ink-500)", fontWeight: 600, marginBottom: 6 }}>
            最终草稿
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {statusChips.map((s) => (
              <span
                key={s.label}
                style={{
                  fontSize: 11,
                  padding: "2px 8px",
                  borderRadius: 10,
                  background: s.ok ? "var(--brand-100)" : "var(--surface-3)",
                  color: s.ok ? "var(--brand-600)" : "var(--ink-500)",
                  border: `1px solid ${s.ok ? "var(--brand-300, #c8dbe9)" : "var(--ink-100)"}`,
                }}
              >
                {s.ok ? "✓" : "·"} {s.label}
              </span>
            ))}
          </div>
        </div>

        {/* Per-schema breakdown */}
        {selectedSchemas.length === 0 && !routePlanMissing && (
          <div style={{ fontSize: 12, color: "var(--ink-500)" }}>
            路由未选择任何 schema
          </div>
        )}
        {selectedSchemas.map((s) => (
          <SchemaSummaryRow key={s.schemaName} item={s} />
        ))}

        {generalWarnings.length > 0 && (
          <div style={{ marginTop: 10 }}>
            <div style={{ fontSize: 11, color: "var(--ink-500)", fontWeight: 600, marginBottom: 4 }}>
              整体警告
            </div>
            {generalWarnings.map((w, i) => (
              <div
                key={i}
                style={{
                  fontSize: 11,
                  color: "var(--warn-700)",
                  background: "#fff7e8",
                  border: "1px solid #f4dfb6",
                  borderRadius: 6,
                  padding: "4px 8px",
                  marginBottom: 4,
                  wordBreak: "break-word",
                  lineHeight: 1.4,
                }}
              >
                {w.length > 200 ? `${w.slice(0, 200)}…` : w}
              </div>
            ))}
          </div>
        )}
      </div>
    </Section>
  );
}

function SchemaSummaryRow({ item }: { item: SchemaSummaryItem }) {
  const confPct = Math.round((item.confidence || 0) * 100);
  const confColor = confPct >= 80 ? "var(--brand-600)" : confPct >= 60 ? "var(--warn-700)" : "var(--ink-500)";
  return (
    <div
      style={{
        padding: "8px 0",
        borderTop: "1px solid var(--ink-100)",
      }}
    >
      <div style={{ display: "flex", alignItems: "baseline", gap: 8, flexWrap: "wrap" }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--ink-900)" }}>
          {item.schemaLabel}
        </span>
        <span
          className="num"
          style={{ fontSize: 11, color: confColor, fontWeight: 600 }}
        >
          {confPct}%
        </span>
        <span
          style={{
            fontSize: 10,
            color: "var(--ink-400)",
            fontFamily: "ui-monospace, SFMono-Regular, monospace",
          }}
        >
          {item.schemaName}
        </span>
        {item.pipelineResultMissing && (
          <span
            style={{
              fontSize: 10,
              color: "var(--risk-500)",
              padding: "1px 6px",
              borderRadius: 4,
              background: "var(--risk-100)",
            }}
          >
            未跑
          </span>
        )}
      </div>
      {item.reason && (
        <div
          style={{
            fontSize: 11,
            color: "var(--ink-500)",
            marginTop: 3,
            lineHeight: 1.4,
            wordBreak: "break-word",
          }}
        >
          {item.reason.length > 140 ? `${item.reason.slice(0, 140)}…` : item.reason}
        </div>
      )}

      {item.extracted.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 6 }}>
          {item.extracted.map((label) => (
            <span
              key={`e-${label}`}
              style={{
                fontSize: 10,
                color: "var(--brand-600)",
                background: "var(--brand-100)",
                borderRadius: 4,
                padding: "1px 6px",
              }}
            >
              ✓ {label}
            </span>
          ))}
        </div>
      )}
      {item.missing.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 4 }}>
          {item.missing.map((label) => (
            <span
              key={`m-${label}`}
              style={{
                fontSize: 10,
                color: "var(--ink-500)",
                background: "var(--surface-3)",
                borderRadius: 4,
                padding: "1px 6px",
                border: "1px dashed var(--ink-100)",
              }}
            >
              · {label}
            </span>
          ))}
        </div>
      )}
      {item.warnings.length > 0 && (
        <div style={{ marginTop: 6 }}>
          {item.warnings.map((w, i) => (
            <div
              key={i}
              style={{
                fontSize: 10,
                color: "var(--warn-700)",
                lineHeight: 1.4,
                wordBreak: "break-word",
              }}
            >
              ⚠ {w.length > 160 ? `${w.slice(0, 160)}…` : w}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function EvidenceSheet({
  label,
  onClose,
  isDesktop,
}: {
  label: string;
  onClose: () => void;
  isDesktop: boolean;
}) {
  return (
    <>
      <div
        onClick={onClose}
        style={{
          position: "absolute",
          inset: 0,
          background: "rgba(0,0,0,0.35)",
          zIndex: 30,
        }}
      />
      <div
        style={{
          position: "absolute",
          zIndex: 40,
          background: "var(--bg)",
          display: "flex",
          flexDirection: "column",
          boxShadow: isDesktop ? "-10px 0 30px rgba(0,0,0,0.18)" : "0 -10px 30px rgba(0,0,0,0.18)",
          ...(isDesktop
            ? { top: 0, right: 0, bottom: 0, width: 480, borderRadius: "16px 0 0 16px" }
            : { left: 0, right: 0, bottom: 0, height: "60%", borderRadius: "20px 20px 0 0" }),
        }}
      >
        {!isDesktop && (
          <div
            style={{
              width: 36,
              height: 5,
              borderRadius: 99,
              background: "var(--ink-300)",
              margin: "8px auto 0",
            }}
          />
        )}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "16px 16px 8px",
          }}
        >
          <div style={{ fontSize: 16, fontWeight: 700 }}>来源原文</div>
          <button
            onClick={onClose}
            style={{ background: "transparent", border: "none", color: "var(--ink-500)", cursor: "pointer" }}
          >
            {I.close(20)}
          </button>
        </div>
        <div className="scroll" style={{ flex: 1, padding: "8px 16px 24px" }}>
          <div className="card" style={{ padding: 14 }}>
            <div style={{ fontSize: 12, color: "var(--ink-500)", marginBottom: 8 }}>{label}</div>
            <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
              <Mono text="王" color="#7a8aa3" size={28} radius={14} />
              <div
                style={{
                  background: "var(--surface-3)",
                  borderRadius: 12,
                  padding: "8px 12px",
                  fontSize: 14,
                  color: "var(--ink-800)",
                  maxWidth: "80%",
                }}
              >
                李总，
                <mark style={{ background: "#fff5b8", padding: "0 2px", borderRadius: 3 }}>
                  10 月底之前我们这边一定能把尾款付掉
                </mark>
                ，您放心。
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, marginBottom: 10, flexDirection: "row-reverse" }}>
              <Mono text="李" color="var(--brand-500)" size={28} radius={14} />
              <div
                style={{
                  background: "var(--brand-100)",
                  color: "var(--brand-700)",
                  borderRadius: 12,
                  padding: "8px 12px",
                  fontSize: 14,
                  maxWidth: "80%",
                }}
              >
                好的王总，到时候我们再对一下。
              </div>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <Mono text="王" color="#7a8aa3" size={28} radius={14} />
              <div
                style={{
                  background: "var(--surface-3)",
                  borderRadius: 12,
                  padding: "8px 12px",
                  fontSize: 14,
                  color: "var(--ink-800)",
                  maxWidth: "80%",
                }}
              >
                不过
                <mark style={{ background: "#fff5b8", padding: "0 2px", borderRadius: 3 }}>
                  我们内部这次审批可能慢一点点
                </mark>
                ，提前同步一下。
              </div>
            </div>
          </div>
          <div
            style={{
              marginTop: 12,
              fontSize: 12,
              color: "var(--ink-500)",
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <span style={{ color: "var(--ai-500)" }}>{I.spark(12)}</span>
            高亮内容由 AI 标注，对应"承诺事项"和"风险线索"
          </div>
        </div>
      </div>
    </>
  );
}

// Editable fields surfaced by the panel. Order matches the unified draft
// shape so reviewers see customer → contract → order top-down.
const ALL_EDITABLE: EditableFieldMeta[] = [
  { path: "customer.full_name", label: "客户名称", kind: "text" },
  { path: "customer.short_name", label: "简称", kind: "text" },
  { path: "customer.address", label: "地址", kind: "text" },
  { path: "customer.tax_id", label: "税号", kind: "text" },
  { path: "contract.contract_no_external", label: "合同号", kind: "text" },
  { path: "contract.signing_date", label: "签订日期", kind: "date" },
  { path: "contract.effective_date", label: "生效日期", kind: "date" },
  { path: "contract.expiry_date", label: "到期日期", kind: "date" },
  { path: "order.amount_total", label: "合同金额", kind: "amount" },
  { path: "order.amount_currency", label: "币种", kind: "text" },
  { path: "order.delivery_promised_date", label: "承诺交期", kind: "date" },
  { path: "order.delivery_address", label: "交付地址", kind: "text" },
  { path: "order.description", label: "订单描述", kind: "text" },
];

function readDraftValue(
  batch: Batch | null,
  entryIndex: number,
  path: EditableDraftPath,
): string {
  if (!batch || entryIndex < 0) return "";
  const entry = batch.entries[entryIndex];
  if (!entry || !entry.result.ok) return "";
  const draft = entry.result.raw.draft as Record<string, unknown>;
  const [section, leaf] = path.split(".") as [string, string];
  const sectionObj = draft[section];
  if (!sectionObj || typeof sectionObj !== "object") return "";
  const v = (sectionObj as Record<string, unknown>)[leaf];
  if (v === null || v === undefined) return "";
  if (typeof v === "number") return String(v);
  if (typeof v === "string") return v;
  return "";
}

function EditPanel({
  batch,
  entryIndex,
  onlyPath,
  onClose,
  onSave,
  isDesktop,
}: {
  batch: Batch | null;
  entryIndex: number;
  onlyPath: EditableDraftPath | null;
  onClose: () => void;
  onSave: (path: EditableDraftPath, value: string | number | null) => void;
  isDesktop: boolean;
}) {
  const visible = onlyPath
    ? ALL_EDITABLE.filter((f) => f.path === onlyPath)
    : ALL_EDITABLE;

  const [values, setValues] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    for (const f of visible) {
      initial[f.path] = readDraftValue(batch, entryIndex, f.path);
    }
    return initial;
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  function handleSave() {
    const nextErrors: Record<string, string> = {};
    const updates: Array<{ path: EditableDraftPath; value: string | number | null }> = [];
    for (const f of visible) {
      const raw = (values[f.path] ?? "").trim();
      if (f.kind === "amount") {
        const parsed = parseAmountInput(raw);
        if (!parsed.ok) {
          nextErrors[f.path] = parsed.error;
          continue;
        }
        updates.push({ path: f.path, value: parsed.value });
      } else {
        updates.push({ path: f.path, value: raw === "" ? null : raw });
      }
    }
    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors);
      return;
    }
    setErrors({});
    for (const u of updates) onSave(u.path, u.value);
    onClose();
  }

  return (
    <>
      <div
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(0,0,0,0.35)",
          zIndex: 100,
        }}
      />
      <div
        style={{
          position: "fixed",
          left: isDesktop ? "50%" : 16,
          top: isDesktop ? "50%" : "auto",
          bottom: isDesktop ? "auto" : 16,
          right: isDesktop ? "auto" : 16,
          transform: isDesktop ? "translate(-50%, -50%)" : undefined,
          width: isDesktop ? 520 : undefined,
          maxHeight: "85vh",
          background: "var(--surface)",
          border: "1px solid var(--ink-100)",
          borderRadius: 14,
          boxShadow: "0 10px 30px rgba(0,0,0,0.2)",
          zIndex: 101,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        <div style={{ padding: "14px 18px 8px", borderBottom: "1px solid var(--ink-100)" }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: "var(--ink-900)" }}>
            {onlyPath ? "修改字段" : "修改提取结果"}
          </div>
          <div style={{ fontSize: 12, color: "var(--ink-500)", marginTop: 4 }}>
            {onlyPath ? "改完点保存写回当前草稿" : "改完点保存，未填写的字段保持原值"}
          </div>
        </div>

        <div style={{ flex: 1, overflowY: "auto", padding: "12px 18px" }}>
          {visible.map((f) => (
            <div key={f.path} style={{ marginBottom: 12 }}>
              <label
                style={{
                  display: "block",
                  fontSize: 11,
                  fontWeight: 600,
                  color: "var(--ink-500)",
                  marginBottom: 4,
                }}
              >
                {f.label}
              </label>
              <input
                type={f.kind === "date" ? "date" : "text"}
                inputMode={f.kind === "amount" ? "decimal" : undefined}
                value={values[f.path] ?? ""}
                onChange={(e) =>
                  setValues((v) => ({ ...v, [f.path]: e.target.value }))
                }
                placeholder={f.kind === "amount" ? "数字，可空" : ""}
                style={{
                  width: "100%",
                  fontSize: 14,
                  padding: "8px 10px",
                  border: `1px solid ${errors[f.path] ? "var(--risk-500)" : "var(--ink-100)"}`,
                  borderRadius: 8,
                  background: "var(--surface)",
                  color: "var(--ink-900)",
                  boxSizing: "border-box",
                }}
              />
              {errors[f.path] && (
                <div style={{ fontSize: 11, color: "var(--risk-500)", marginTop: 4 }}>
                  {errors[f.path]}
                </div>
              )}
            </div>
          ))}
        </div>

        <div
          style={{
            display: "flex",
            gap: 8,
            padding: "12px 18px",
            borderTop: "1px solid var(--ink-100)",
          }}
        >
          <button className="btn btn-secondary" style={{ flex: 1 }} onClick={onClose}>
            取消
          </button>
          <button className="btn btn-primary" style={{ flex: 1 }} onClick={handleSave}>
            保存
          </button>
        </div>
      </div>
    </>
  );
}

function CustomerPicker({
  customers,
  loading,
  error,
  onClose,
  onPickExisting,
  onPickNew,
  isDesktop,
}: {
  customers: CustomerListItem[] | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
  onPickExisting: (c: CustomerListItem) => void;
  onPickNew: () => void;
  isDesktop: boolean;
}) {
  const [q, setQ] = useState("");
  const filtered = (customers ?? []).filter((c) => {
    if (!q.trim()) return true;
    const haystack = [c.name, c.shortName ?? "", c.taxId ?? "", c.address ?? ""]
      .join(" ")
      .toLowerCase();
    return haystack.includes(q.toLowerCase());
  });

  return (
    <>
      <div
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(0,0,0,0.35)",
          zIndex: 100,
        }}
      />
      <div
        style={{
          position: "fixed",
          left: isDesktop ? "50%" : 16,
          top: isDesktop ? "50%" : "auto",
          bottom: isDesktop ? "auto" : 16,
          right: isDesktop ? "auto" : 16,
          transform: isDesktop ? "translate(-50%, -50%)" : undefined,
          width: isDesktop ? 540 : undefined,
          maxHeight: "85vh",
          background: "var(--surface)",
          border: "1px solid var(--ink-100)",
          borderRadius: 14,
          boxShadow: "0 10px 30px rgba(0,0,0,0.2)",
          zIndex: 101,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        <div style={{ padding: "14px 18px 10px", borderBottom: "1px solid var(--ink-100)" }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: "var(--ink-900)" }}>
            选择归属客户
          </div>
          <div style={{ fontSize: 12, color: "var(--ink-500)", marginTop: 4 }}>
            从已有客户里挑选，或创建为新客户。选已有客户后默认只绑定，不会覆盖客户主档。
          </div>
        </div>

        <div style={{ padding: "10px 18px", borderBottom: "1px solid var(--ink-100)" }}>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="搜索客户名称、简称、税号、地址"
            style={{
              width: "100%",
              padding: "8px 10px",
              fontSize: 14,
              border: "1px solid var(--ink-100)",
              borderRadius: 8,
              background: "var(--surface)",
              color: "var(--ink-900)",
              boxSizing: "border-box",
            }}
          />
        </div>

        <div style={{ flex: 1, overflowY: "auto" }}>
          {loading && (
            <div
              style={{
                padding: 24,
                textAlign: "center",
                color: "var(--ink-500)",
                fontSize: 13,
              }}
            >
              正在加载客户…
            </div>
          )}
          {error && (
            <div style={{ padding: 12, color: "var(--risk-500)", fontSize: 13 }}>
              {error}
            </div>
          )}
          {!loading && !error && filtered.length === 0 && (
            <div
              style={{
                padding: 24,
                textAlign: "center",
                color: "var(--ink-400)",
                fontSize: 13,
              }}
            >
              {customers && customers.length === 0 ? "暂无客户档案" : "没有匹配的客户"}
            </div>
          )}
          {!loading &&
            filtered.map((c) => (
              <button
                key={c.id}
                onClick={() => onPickExisting(c)}
                style={{
                  display: "block",
                  width: "100%",
                  textAlign: "left",
                  padding: "10px 18px",
                  background: "transparent",
                  border: "none",
                  borderBottom: "1px solid var(--ink-100)",
                  cursor: "pointer",
                  color: "var(--ink-900)",
                }}
              >
                <div style={{ fontSize: 14, fontWeight: 600 }}>{c.name}</div>
                <div style={{ fontSize: 11, color: "var(--ink-500)", marginTop: 2 }}>
                  {[c.shortName, c.taxId, c.address].filter(Boolean).join(" · ") || "—"}
                </div>
              </button>
            ))}
        </div>

        <div
          style={{
            display: "flex",
            gap: 8,
            padding: "12px 18px",
            borderTop: "1px solid var(--ink-100)",
          }}
        >
          <button className="btn btn-secondary" style={{ flex: 1 }} onClick={onClose}>
            取消
          </button>
          <button className="btn btn-primary" style={{ flex: 1 }} onClick={onPickNew}>
            + 创建为新客户
          </button>
        </div>
      </div>
    </>
  );
}
