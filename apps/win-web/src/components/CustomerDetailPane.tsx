import type { ReactNode } from "react";
import type { CustomerDetail, TimelineEvent } from "../data/types";
import { I } from "../icons";
import { fmtCNYRaw } from "../lib/format";

type Tone = "warn" | "normal" | "mute";

const TIMELINE_ICON: Record<TimelineEvent["kind"], (s?: number) => ReactNode> = {
  upload: (s = 13) => I.cloud(s),
  meet: (s = 13) => I.voice(s),
  wechat: (s = 13) => I.wechat(s),
  invoice: (s = 13) => I.cash(s),
};

export function CustomerDetailPane({
  customer,
  onAsk,
  onEdit,
  rightAction,
  compact = false,
}: {
  customer: CustomerDetail;
  onAsk?: () => void;
  onEdit?: () => void;
  rightAction?: ReactNode;
  compact?: boolean;
}) {
  const pad = compact ? "20px 24px" : "24px 40px";
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
      <div style={{ padding: `${compact ? "20px" : "24px"} ${compact ? "24px" : "40px"} 18px`, borderBottom: "1px solid var(--ink-100)" }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 14 }}>
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: 12,
              flexShrink: 0,
              background: customer.color || "#1F5FA3",
              color: "#fff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: customer.monogram.length > 2 ? 13 : 15,
              fontWeight: 700,
              letterSpacing: "0.02em",
            }}
          >
            {customer.monogram}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                fontSize: 22,
                fontWeight: 700,
                color: "var(--ink-900)",
                letterSpacing: "-0.015em",
                lineHeight: 1.2,
              }}
            >
              {customer.name}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6, flexWrap: "wrap" }}>
              {customer.risk && (
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    padding: "2px 8px",
                    borderRadius: 4,
                    background:
                      customer.risk.level === "high" ? "var(--risk-100)" :
                      customer.risk.level === "med" ? "var(--warn-100)" : "var(--ok-100)",
                    color:
                      customer.risk.level === "high" ? "var(--risk-700)" :
                      customer.risk.level === "med" ? "var(--warn-700)" : "var(--ok-700)",
                  }}
                >
                  {customer.risk.label || riskLabel(customer.risk.level)}
                </span>
              )}
              <span style={{ fontSize: 11.5, color: "var(--ink-500)" }}>
                {(customer.address || "—") + (customer.updated ? ` · ${customer.updated}` : "")}
              </span>
            </div>
          </div>
          {rightAction ?? (
            <div style={{ display: "flex", gap: 8 }}>
              {onAsk && (
                <button
                  onClick={onAsk}
                  style={{
                    height: 36,
                    padding: "0 16px",
                    borderRadius: 8,
                    background: "#fff",
                    color: "var(--ink-800)",
                    border: "1px solid var(--ink-200)",
                    fontSize: 13,
                    fontWeight: 600,
                    cursor: "pointer",
                    fontFamily: "var(--font)",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  <span style={{ color: "var(--ai-500)" }}>{I.spark(13)}</span>
                  问 AI
                </button>
              )}
              {onEdit && (
                <button
                  onClick={onEdit}
                  style={{
                    height: 36,
                    padding: "0 14px",
                    borderRadius: 8,
                    background: "transparent",
                    color: "var(--ink-700)",
                    border: "1px solid var(--ink-100)",
                    fontSize: 13,
                    fontWeight: 600,
                    cursor: "pointer",
                    fontFamily: "var(--font)",
                  }}
                >
                  编辑
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="scroll" style={{ flex: 1, padding: pad }}>
        {/* AI summary */}
        <div className="ai-surface" style={{ padding: "16px 18px", marginBottom: 28 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
            <span style={{ color: "var(--ai-600)" }}>{I.spark(13)}</span>
            <div
              style={{
                fontSize: 10.5,
                fontWeight: 700,
                color: "var(--ai-700)",
                letterSpacing: "0.10em",
                textTransform: "uppercase",
              }}
            >
              AI 客户摘要
            </div>
          </div>
          <div style={{ fontSize: 14, color: "var(--ink-800)", lineHeight: 1.6 }}>
            {customer.aiSummary}
          </div>
        </div>

        {/* Metrics row */}
        <MetricsRow customer={customer} />

        {/* Risks */}
        {customer.risks && customer.risks.length > 0 && (
          <Section title="风险线索" count={customer.risks.length}>
            {customer.risks.map((r) => (
              <div
                key={r.id}
                style={{
                  background:
                    r.level === "high" ? "#FFF6F6" :
                    r.level === "med" ? "#FFFBF0" : "var(--ai-50)",
                  borderRadius: 10,
                  border: "1px solid var(--ink-100)",
                  borderLeft:
                    "3px solid " +
                    (r.level === "high" ? "var(--risk-500)" :
                     r.level === "med" ? "var(--warn-500)" : "var(--ai-500)"),
                  padding: 14,
                  marginBottom: 8,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ color: r.level === "high" ? "var(--risk-500)" : "var(--warn-600)" }}>
                    {I.warn(14)}
                  </span>
                  <div style={{ fontSize: 13.5, fontWeight: 600, color: "var(--ink-900)" }}>{r.title}</div>
                </div>
                <div style={{ fontSize: 12.5, color: "var(--ink-700)", marginTop: 6, lineHeight: 1.55 }}>
                  {r.detail}
                </div>
                {r.sources && r.sources.length > 0 && (
                  <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
                    {r.sources.map((s, i) => (
                      <span
                        key={i}
                        className="pill"
                        style={{
                          background: "#fff",
                          color: "var(--ink-700)",
                          fontSize: 11,
                          border: "1px solid var(--ink-100)",
                          padding: "3px 8px",
                        }}
                      >
                        {s}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </Section>
        )}

        {/* Commitments */}
        {customer.commitments && customer.commitments.length > 0 && (
          <Section title="承诺事项" count={customer.commitments.length}>
            <div
              style={{
                background: "#fff",
                border: "1px solid var(--ink-100)",
                borderRadius: 12,
                overflow: "hidden",
              }}
            >
              {customer.commitments.map((x, i) => (
                <div
                  key={x.id}
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 12,
                    padding: "12px 16px",
                    borderBottom: i < customer.commitments!.length - 1 ? "1px solid var(--ink-100)" : "none",
                  }}
                >
                  <div
                    style={{
                      width: 22,
                      height: 22,
                      borderRadius: 6,
                      background: "var(--warn-100)",
                      color: "var(--warn-700)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                      marginTop: 1,
                    }}
                  >
                    {I.hand(13)}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13.5, color: "var(--ink-900)", fontWeight: 500, lineHeight: 1.55 }}>
                      {x.text}
                    </div>
                    <div style={{ fontSize: 11, color: "var(--ink-500)", marginTop: 4 }}>
                      来源：{x.source}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* Tasks */}
        {customer.tasks && customer.tasks.length > 0 && (
          <Section title="待办事项" count={customer.tasks.length}>
            <div
              style={{
                background: "#fff",
                border: "1px solid var(--ink-100)",
                borderRadius: 12,
                overflow: "hidden",
              }}
            >
              {customer.tasks.map((t, i) => (
                <div
                  key={t.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    padding: "12px 16px",
                    borderBottom: i < customer.tasks!.length - 1 ? "1px solid var(--ink-100)" : "none",
                  }}
                >
                  <div
                    style={{
                      width: 22,
                      height: 22,
                      borderRadius: 6,
                      background: "var(--ai-100)",
                      color: "var(--ai-600)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                    }}
                  >
                    {I.task(13)}
                  </div>
                  <div style={{ flex: 1, fontSize: 13.5, color: "var(--ink-900)" }}>{t.text}</div>
                  <span style={{ fontSize: 11, color: "var(--ink-500)" }}>
                    {t.assignee ?? t.owner ?? "未分配"}
                  </span>
                  <span className="pill pill-ai" style={{ fontSize: 10.5 }}>{t.due}</span>
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* Timeline */}
        {customer.timeline && customer.timeline.length > 0 && (
          <Section title="最近动态">
            <div
              style={{
                background: "#fff",
                border: "1px solid var(--ink-100)",
                borderRadius: 12,
                padding: "14px 16px",
              }}
            >
              {customer.timeline.map((e, i) => {
                const last = i === customer.timeline!.length - 1;
                return (
                  <div key={i} style={{ display: "flex", gap: 12, paddingBottom: last ? 4 : 14 }}>
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
                      <div
                        style={{
                          width: 22,
                          height: 22,
                          borderRadius: 11,
                          background: "var(--ai-50)",
                          color: "var(--ai-600)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          flexShrink: 0,
                        }}
                      >
                        {TIMELINE_ICON[e.kind]?.(13) ?? I.doc(13)}
                      </div>
                      {!last && <div style={{ width: 1.5, flex: 1, background: "var(--ink-100)", marginTop: 4 }} />}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13.5, color: "var(--ink-900)", fontWeight: 500 }}>{e.title}</div>
                      <div style={{ fontSize: 11.5, color: "var(--ink-500)", marginTop: 3 }}>
                        {e.when} · {e.by}
                      </div>
                      <div className="mono-code" style={{ marginTop: 3 }}>{e.src}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </Section>
        )}

        {/* Contacts */}
        {customer.contacts && customer.contacts.length > 0 && (
          <Section title="联系人" count={customer.contacts.length}>
            <div
              style={{
                background: "#fff",
                border: "1px solid var(--ink-100)",
                borderRadius: 12,
                overflow: "hidden",
              }}
            >
              {customer.contacts.map((p, i) => (
                <div
                  key={p.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 14,
                    padding: "12px 16px",
                    borderBottom: i < customer.contacts!.length - 1 ? "1px solid var(--ink-100)" : "none",
                  }}
                >
                  <div
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: 16,
                      flexShrink: 0,
                      background: "#374151",
                      color: "#fff",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 12.5,
                      fontWeight: 700,
                    }}
                  >
                    {p.initial}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                      <span style={{ fontSize: 13.5, fontWeight: 600, color: "var(--ink-900)" }}>{p.name}</span>
                      <span style={{ fontSize: 11, color: "var(--ink-500)" }}>{p.role}</span>
                    </div>
                    <div className="num" style={{ fontSize: 11.5, color: "var(--ink-500)", marginTop: 2 }}>
                      {(p.phone || p.mobile || "—") + (p.last ? ` · 最近 ${p.last}` : "")}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* Docs */}
        {customer.docs && customer.docs.length > 0 && (
          <Section title="来源依据" count={customer.docs.length}>
            <div
              style={{
                background: "#fff",
                border: "1px solid var(--ink-100)",
                borderRadius: 12,
                overflow: "hidden",
              }}
            >
              {customer.docs.map((d, i) => (
                <div
                  key={d.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    padding: "12px 16px",
                    borderBottom: i < customer.docs!.length - 1 ? "1px solid var(--ink-100)" : "none",
                  }}
                >
                  <div
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: 9,
                      background: "var(--surface-3)",
                      color: "var(--ink-600)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                    }}
                  >
                    {I.doc(15)}
                  </div>
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
                      {d.name}
                    </div>
                    <div style={{ fontSize: 11.5, color: "var(--ink-500)", marginTop: 2 }}>
                      {d.kind} · {d.date}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Section>
        )}
      </div>
    </div>
  );
}

function MetricsRow({ customer }: { customer: CustomerDetail }) {
  const items: { label: string; value: string; tone: Tone }[] = [
    {
      label: "未收款",
      value: customer.metrics.receivable > 0 ? fmtCNYRaw(customer.metrics.receivable) : "—",
      tone: customer.metrics.receivable > 0 ? "warn" : "mute",
    },
    {
      label: "合同总额",
      value: customer.metrics.contractTotal > 0 ? fmtCNYRaw(customer.metrics.contractTotal) : "—",
      tone: customer.metrics.contractTotal > 0 ? "normal" : "mute",
    },
    { label: "承诺事项", value: String(customer.commitments?.length ?? 0), tone: "normal" },
    { label: "待办", value: String(customer.metrics.tasks ?? 0), tone: "normal" },
  ];
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(4, 1fr)",
        gap: 0,
        padding: "14px 0",
        marginBottom: 28,
        borderTop: "1px solid var(--ink-100)",
        borderBottom: "1px solid var(--ink-100)",
      }}
    >
      {items.map((m, i) => (
        <div
          key={m.label}
          style={{
            padding: "0 16px",
            borderRight: i < items.length - 1 ? "1px solid var(--ink-100)" : "none",
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
            {m.label}
          </div>
          <div
            className="num"
            style={{
              fontSize: 19,
              fontWeight: 700,
              color:
                m.tone === "warn" ? "var(--warn-700)" :
                m.tone === "mute" ? "var(--ink-300)" : "var(--ink-900)",
              marginTop: 5,
              letterSpacing: "-0.015em",
            }}
          >
            {m.value}
          </div>
        </div>
      ))}
    </div>
  );
}

function Section({ title, count, children }: { title: string; count?: number; children: ReactNode }) {
  return (
    <div style={{ marginBottom: 28 }}>
      <div
        style={{
          fontSize: 10.5,
          fontWeight: 700,
          color: "var(--ink-500)",
          letterSpacing: "0.08em",
          textTransform: "uppercase",
        }}
      >
        {title}
        {count !== undefined && (
          <span
            style={{
              marginLeft: 8,
              fontSize: 10.5,
              color: "var(--ink-400)",
              fontWeight: 500,
              letterSpacing: "normal",
              textTransform: "none",
            }}
          >
            {count}
          </span>
        )}
      </div>
      <div style={{ marginTop: 10 }}>{children}</div>
    </div>
  );
}

function riskLabel(level: string): string {
  return level === "high" ? "高风险" : level === "med" ? "中风险" : "低风险";
}
