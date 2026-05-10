import { useEffect, useState, type ReactNode } from "react";
import type { GoFn } from "../App";
import { getCustomer } from "../api/client";
import { AISummary } from "../components/AISummary";
import { EvidenceChip } from "../components/EvidenceChip";
import { Mono } from "../components/Mono";
import { RowCard } from "../components/RowCard";
import { Section } from "../components/Section";
import { SmallStat } from "../components/SmallStat";
import type { CustomerDetail, TimelineEvent } from "../data/types";
import { I } from "../icons";
import { useIsDesktop } from "../lib/breakpoints";
import { fmtCNYRaw } from "../lib/format";

const TIMELINE_ICON: Record<TimelineEvent["kind"], (s?: number) => ReactNode> = {
  upload: (s = 13) => I.cloud(s),
  meet: (s = 13) => I.voice(s),
  wechat: (s = 13) => I.wechat(s),
  invoice: (s = 13) => I.cash(s),
};

export function CustomerDetailScreen({
  go,
  params,
}: {
  go: GoFn;
  params: Record<string, string>;
}) {
  const isDesktop = useIsDesktop();
  const [customer, setCustomer] = useState<CustomerDetail | null>(null);

  useEffect(() => {
    if (params.id) {
      getCustomer(params.id).then((c) => setCustomer(c ?? null));
    }
  }, [params.id]);

  if (!customer) {
    return (
      <div
        className="screen"
        style={{ background: "var(--bg)", alignItems: "center", justifyContent: "center", display: "flex" }}
      >
        <div style={{ color: "var(--ink-400)", fontSize: 14 }}>加载中…</div>
      </div>
    );
  }

  return (
    <div className="screen" style={{ background: "var(--bg)" }}>
      {/* Top nav */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: isDesktop ? "12px 32px 8px" : "6px 8px 8px",
          maxWidth: isDesktop ? 1280 : undefined,
          width: "100%",
          margin: "0 auto",
        }}
      >
        <button
          onClick={() => go("list")}
          style={{
            width: 40,
            height: 40,
            borderRadius: 20,
            background: "transparent",
            border: "none",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--ink-700)",
            cursor: "pointer",
          }}
        >
          {I.back(22)}
        </button>
        <div style={{ fontSize: 15, fontWeight: 600, color: "var(--ink-700)" }}>客户档案</div>
        <button
          style={{
            width: 40,
            height: 40,
            borderRadius: 20,
            background: "transparent",
            border: "none",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--ink-700)",
            cursor: "pointer",
          }}
        >
          {I.bookmark(20)}
        </button>
      </div>

      <div
        className="scroll"
        style={{
          flex: 1,
          padding: isDesktop ? "0 32px 40px" : "0 16px 120px",
          maxWidth: isDesktop ? 1280 : undefined,
          width: "100%",
          margin: "0 auto",
        }}
      >
        {isDesktop ? (
          <DesktopLayout customer={customer} go={go} />
        ) : (
          <MobileLayout customer={customer} go={go} />
        )}
      </div>
    </div>
  );
}

function MobileLayout({ customer, go }: { customer: CustomerDetail; go: GoFn }) {
  return (
    <>
      <Header customer={customer} />
      <AISummary style={{ marginBottom: 12 }}>{customer.aiSummary}</AISummary>
      <KeyMetricsRow customer={customer} />
      <SmallMetricsRow customer={customer} />
      <AskCustomerCTA customer={customer} go={go} />
      <RisksSection customer={customer} />
      <CommitmentsSection customer={customer} />
      <TasksSection customer={customer} />
      <TimelineSection customer={customer} />
      <ContactsSection customer={customer} />
      <DocsSection customer={customer} />
    </>
  );
}

function DesktopLayout({ customer, go }: { customer: CustomerDetail; go: GoFn }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 320px", gap: 24, alignItems: "flex-start" }}>
      {/* Main column */}
      <div>
        <Header customer={customer} />
        <AISummary style={{ marginBottom: 16 }}>{customer.aiSummary}</AISummary>
        <RisksSection customer={customer} />
        <CommitmentsSection customer={customer} />
        <TasksSection customer={customer} />
        <TimelineSection customer={customer} />
        <DocsSection customer={customer} />
      </div>

      {/* Sticky right rail */}
      <aside style={{ position: "sticky", top: 12, display: "flex", flexDirection: "column", gap: 12 }}>
        <KeyMetricsRow customer={customer} />
        <SmallMetricsRow customer={customer} />
        <AskCustomerCTA customer={customer} go={go} />
        <ContactsSection customer={customer} />
      </aside>
    </div>
  );
}

function Header({ customer }: { customer: CustomerDetail }) {
  return (
    <div style={{ display: "flex", gap: 14, alignItems: "flex-start", marginBottom: 12 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 24,
            fontWeight: 700,
            color: "var(--ink-900)",
            letterSpacing: "-0.01em",
            lineHeight: 1.2,
          }}
        >
          {customer.name}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 6, flexWrap: "wrap" }}>
          <span className="pill pill-brand" style={{ fontSize: 11 }}>
            {customer.tag}
          </span>
          <span style={{ fontSize: 12, color: "var(--ink-500)" }}>· 最近更新 {customer.updated}</span>
        </div>
      </div>
    </div>
  );
}

function KeyMetricsRow({ customer }: { customer: CustomerDetail }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 10 }}>
      <div className="card" style={{ padding: 12 }}>
        <div style={{ fontSize: 11, color: "var(--ink-500)", fontWeight: 600, letterSpacing: "0.02em" }}>
          合同总额
        </div>
        <div className="num" style={{ fontSize: 19, fontWeight: 700, color: "var(--ink-900)", marginTop: 4 }}>
          {fmtCNYRaw(customer.metrics.contractTotal)}
        </div>
      </div>
      <div
        className="card"
        style={{ padding: 12, background: "var(--warn-100)", border: "1px solid #f4dfb6" }}
      >
        <div style={{ fontSize: 11, color: "var(--warn-700)", fontWeight: 600, letterSpacing: "0.02em" }}>
          未收款
        </div>
        <div className="num" style={{ fontSize: 19, fontWeight: 700, color: "var(--warn-700)", marginTop: 4 }}>
          {fmtCNYRaw(customer.metrics.receivable)}
        </div>
      </div>
    </div>
  );
}

function SmallMetricsRow({ customer }: { customer: CustomerDetail }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 16 }}>
      <SmallStat icon={I.doc(15)} label="合同" value={customer.metrics.contracts} />
      <SmallStat icon={I.task(15)} label="待办" value={customer.metrics.tasks} tone="ai" />
      <SmallStat icon={I.customers(15)} label="联系人" value={customer.metrics.contacts} />
    </div>
  );
}

function AskCustomerCTA({ customer, go }: { customer: CustomerDetail; go: GoFn }) {
  return (
    <button
      onClick={() => go("ask", { id: customer.id })}
      style={{
        width: "100%",
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "12px 14px",
        borderRadius: 14,
        marginBottom: 16,
        background: "var(--surface)",
        border: "1px solid var(--ink-100)",
        boxShadow: "var(--shadow-card-soft)",
        cursor: "pointer",
        textAlign: "left",
      }}
    >
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: 16,
          background: "var(--ai-100)",
          color: "var(--ai-500)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {I.spark(14)}
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: "var(--ink-900)" }}>问问这个客户</div>
        <div style={{ fontSize: 12, color: "var(--ink-500)" }}>例：还有多少钱没收？最近沟通说了什么？</div>
      </div>
      <span style={{ color: "var(--ink-400)" }}>{I.chev(14)}</span>
    </button>
  );
}

function RisksSection({ customer }: { customer: CustomerDetail }) {
  if (!customer.risks?.length) return null;
  return (
    <Section title="风险线索">
      {customer.risks.map((r) => (
        <div
          key={r.id}
          style={{
            background: "var(--surface)",
            borderRadius: 14,
            border: "1px solid var(--ink-100)",
            borderLeft: "3px solid var(--warn-500)",
            padding: 12,
            marginBottom: 8,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ color: "var(--warn-500)" }}>{I.warn(15)}</span>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--ink-900)" }}>{r.title}</div>
          </div>
          <div style={{ fontSize: 13, color: "var(--ink-700)", marginTop: 6, lineHeight: 1.5 }}>{r.detail}</div>
          <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
            {r.sources.map((s, i) => (
              <EvidenceChip key={i} type={s.startsWith("微信") ? "微信" : "文件"} label={s} />
            ))}
          </div>
        </div>
      ))}
    </Section>
  );
}

function CommitmentsSection({ customer }: { customer: CustomerDetail }) {
  if (!customer.commitments?.length) return null;
  return (
    <Section title="承诺事项" count={customer.commitments.length}>
      {customer.commitments.map((x) => (
        <RowCard key={x.id} icon={I.hand(16)} iconBg="var(--warn-100)" iconColor="var(--warn-700)">
          <div style={{ fontSize: 14, color: "var(--ink-900)", fontWeight: 500 }}>{x.text}</div>
          <div style={{ display: "flex", gap: 6, marginTop: 6, flexWrap: "wrap" }}>
            <EvidenceChip type={x.source.includes("微信") ? "微信" : "文件"} label={x.source} />
          </div>
        </RowCard>
      ))}
    </Section>
  );
}

function TasksSection({ customer }: { customer: CustomerDetail }) {
  if (!customer.tasks?.length) return null;
  return (
    <Section title="待办事项" count={customer.tasks.length}>
      {customer.tasks.map((t) => (
        <RowCard key={t.id} icon={I.task(16)} iconBg="var(--ai-100)" iconColor="var(--ai-500)">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
            <div style={{ fontSize: 14, color: "var(--ink-900)", fontWeight: 500 }}>{t.text}</div>
            <span className="pill pill-ai" style={{ fontSize: 11, flexShrink: 0 }}>
              {t.due}
            </span>
          </div>
          <div style={{ fontSize: 12, color: "var(--ink-500)", marginTop: 4 }}>负责人 · {t.owner}</div>
        </RowCard>
      ))}
    </Section>
  );
}

function TimelineSection({ customer }: { customer: CustomerDetail }) {
  if (!customer.timeline?.length) return null;
  return (
    <Section title="最近动态" trailing={<span className="more">查看全部</span>}>
      <div
        style={{
          background: "var(--surface)",
          borderRadius: 14,
          padding: "14px 16px 8px",
          border: "1px solid var(--ink-100)",
        }}
      >
        {customer.timeline.map((e, i) => {
          const last = i === customer.timeline!.length - 1;
          return (
            <div key={i} style={{ display: "flex", gap: 12, paddingBottom: last ? 6 : 14 }}>
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
                <div
                  style={{
                    width: 22,
                    height: 22,
                    borderRadius: 11,
                    background: "var(--brand-50)",
                    color: "var(--brand-500)",
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
                <div style={{ fontSize: 14, color: "var(--ink-900)", fontWeight: 500 }}>{e.title}</div>
                <div style={{ fontSize: 12, color: "var(--ink-500)", marginTop: 3 }}>
                  {e.when} · {e.by}
                </div>
                <div
                  style={{
                    fontSize: 11,
                    color: "var(--ink-400)",
                    marginTop: 3,
                    fontFamily: "ui-monospace, SFMono-Regular, monospace",
                  }}
                >
                  {e.src}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </Section>
  );
}

function ContactsSection({ customer }: { customer: CustomerDetail }) {
  if (!customer.contacts?.length) return null;
  return (
    <Section title="联系人" count={customer.contacts.length} trailing={<span className="more">+ 添加</span>}>
      <div className="card" style={{ padding: "4px 0" }}>
        {customer.contacts.map((p, i) => (
          <div key={p.id}>
            {i > 0 && <div style={{ height: 1, background: "var(--ink-100)", marginLeft: 60 }} />}
            <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 14px" }}>
              <Mono text={p.initial} color="#7a8aa3" size={36} radius={18} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
                  <span style={{ fontSize: 14, fontWeight: 600, color: "var(--ink-900)" }}>{p.name}</span>
                  <span style={{ fontSize: 11, color: "var(--ink-500)" }}>{p.role}</span>
                </div>
                <div className="num" style={{ fontSize: 12, color: "var(--ink-500)", marginTop: 2 }}>
                  {p.phone} · 最近 {p.last}
                </div>
              </div>
              <span style={{ color: "var(--ink-400)" }}>{I.chev(14)}</span>
            </div>
          </div>
        ))}
      </div>
    </Section>
  );
}

function DocsSection({ customer }: { customer: CustomerDetail }) {
  if (!customer.docs?.length) return null;
  return (
    <Section title="来源依据" count={customer.docs.length}>
      <div className="card" style={{ padding: "4px 0" }}>
        {customer.docs.map((d, i) => (
          <div key={d.id}>
            {i > 0 && <div style={{ height: 1, background: "var(--ink-100)", marginLeft: 60 }} />}
            <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 14px" }}>
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
                {I.doc(16)}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontSize: 14,
                    fontWeight: 500,
                    color: "var(--ink-900)",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {d.name}
                </div>
                <div style={{ fontSize: 12, color: "var(--ink-500)", marginTop: 2 }}>
                  {d.kind} · {d.date}
                </div>
              </div>
              <span style={{ color: "var(--ink-400)" }}>{I.chev(14)}</span>
            </div>
          </div>
        ))}
      </div>
    </Section>
  );
}
