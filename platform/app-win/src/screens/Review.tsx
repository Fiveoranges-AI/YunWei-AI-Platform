import { useEffect, useState } from "react";
import type { GoFn } from "../App";
import { getReview } from "../api/client";
import {
  archiveBatch,
  batchToReview,
  clearLastBatch,
  getLastBatch,
  ignoreBatch,
  type ArchiveResult,
  type Batch,
} from "../api/ingest";
import { EvidenceChip } from "../components/EvidenceChip";
import { Mono } from "../components/Mono";
import { Section } from "../components/Section";
import type { Review, ReviewExtraction } from "../data/types";
import { I } from "../icons";
import { useIsDesktop } from "../lib/breakpoints";

const EXTRACTION_STYLE: Record<
  ReviewExtraction["kind"],
  { icon: (s?: number) => React.ReactNode; bg: string; fg: string }
> = {
  commitment: { icon: (s = 15) => I.hand(s), bg: "var(--warn-100)", fg: "var(--warn-700)" },
  task: { icon: (s = 15) => I.task(s), bg: "var(--ai-100)", fg: "var(--ai-500)" },
  risk: { icon: (s = 15) => I.warn(s), bg: "var(--risk-100)", fg: "var(--risk-500)" },
  contact: { icon: (s = 15) => I.customers(s), bg: "var(--brand-100)", fg: "var(--brand-600)" },
};

export function ReviewScreen({ go }: { go: GoFn }) {
  const isDesktop = useIsDesktop();
  const [review, setReview] = useState<Review | null>(null);
  const [batch, setBatch] = useState<Batch | null>(null);
  const [showEvidence, setShowEvidence] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const [archiveError, setArchiveError] = useState<string | null>(null);
  const [archiveResult, setArchiveResult] = useState<ArchiveResult | null>(null);

  useEffect(() => {
    // Prefer a real ingest batch when the user just came from Upload.
    // Fall back to mock only when /review was opened without an upload
    // (e.g. directly tapping the tab) — keeps the design preview usable.
    const batch = getLastBatch();
    const fromBatch = batch ? batchToReview(batch) : null;
    if (fromBatch) {
      setBatch(batch);
      setReview(fromBatch);
      return;
    }
    getReview("last").then(setReview);
  }, []);

  async function handleArchive() {
    if (archiving) return;
    setArchiving(true);
    setArchiveError(null);
    try {
      if (!batch) {
        setDone(true);
        return;
      }
      const result = await archiveBatch(batch);
      clearLastBatch();
      setArchiveResult(result);
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
              <div className="card" style={{ padding: 14, display: "flex", gap: 12, alignItems: "center" }}>
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
                  style={{
                    background: "var(--surface-3)",
                    border: "1px solid var(--ink-100)",
                    borderRadius: 8,
                    padding: "6px 10px",
                    fontSize: 12,
                    color: "var(--ink-700)",
                    fontWeight: 500,
                    cursor: "pointer",
                  }}
                >
                  更换
                </button>
              </div>
            </Section>

            {/* Identified fields */}
            <Section title="识别信息">
              <div className="card" style={{ padding: "4px 0" }}>
                {review.fields.map((f, i) => (
                  <div key={f.key}>
                    {i > 0 && <div style={{ height: 1, background: "var(--ink-100)", marginLeft: 14 }} />}
                    <div
                      style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 14px" }}
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
                ))}
              </div>
            </Section>

            {/* Missing fields */}
            {review.missing.length > 0 && (
              <Section title="待补充字段">
                <div
                  className="card"
                  style={{ padding: 12, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}
                >
                  <span style={{ color: "var(--warn-500)" }}>{I.warn(14)}</span>
                  <span style={{ fontSize: 12, color: "var(--ink-500)" }}>未识别到：</span>
                  {review.missing.map((m) => (
                    <button
                      key={m}
                      className="pill pill-warn"
                      style={{
                        fontSize: 11,
                        cursor: "pointer",
                        border: "1px dashed #e5b873",
                        background: "#fff7e8",
                      }}
                    >
                      + {m}
                    </button>
                  ))}
                </div>
              </Section>
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
          <button className="btn btn-secondary" style={{ flex: 1 }} onClick={() => go("upload")} disabled={archiving}>
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
