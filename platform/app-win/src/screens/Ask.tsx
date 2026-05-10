import { useEffect, useRef, useState } from "react";
import type { GoFn } from "../App";
import { askAI, getAskSeed, listCustomersBasic } from "../api/client";
import { EvidenceChip } from "../components/EvidenceChip";
import type { AskAIBlock, AskMessage, CustomerDetail } from "../data/types";
import { I } from "../icons";
import { useIsDesktop } from "../lib/breakpoints";
import { fmtCNYRaw } from "../lib/format";

const ALL = "all" as const;

export function AskScreen({ go, params }: { go: GoFn; params: Record<string, string> }) {
  const isDesktop = useIsDesktop();
  const [customers, setCustomers] = useState<CustomerDetail[]>([]);
  const [loading, setLoading] = useState(true);
  // Default to "all" when no specific customer requested. Lets new users
  // (zero customers) still chat in cross-customer mode rather than getting
  // stuck on a "no customer selected" empty state.
  const [activeId, setActiveId] = useState<string>(params.id ?? ALL);
  const [msgs, setMsgs] = useState<AskMessage[]>([]);
  const [pending, setPending] = useState(false);
  const [draft, setDraft] = useState("");
  const [pickerOpen, setPickerOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);

  const isAll = activeId === ALL;
  const customer = customers.find((c) => c.id === activeId) ?? customers[0];

  useEffect(() => {
    // Picker only needs id+name+tag; skip the per-customer summary/metrics
    // enrichment to avoid the 1+2N round-trip pattern. ~10x faster mount.
    listCustomersBasic()
      .then((all) => setCustomers(all))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!customer && !isAll) return;
    getAskSeed(isAll ? "all" : activeId).then((seed) => {
      setMsgs(seed.messages);
      setSuggestions(seed.suggestions);
    });
  }, [activeId, isAll, customer]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [msgs.length, pending]);

  async function ask(text: string) {
    if (!text.trim()) return;
    setMsgs((m) => [...m, { role: "user", text, when: "现在" }]);
    setDraft("");
    setPending(true);
    try {
      const blocks = await askAI(isAll ? ALL : activeId, text);
      setMsgs((m) => [...m, { role: "ai", blocks }]);
    } catch (e) {
      const message = e instanceof Error ? e.message : "请求失败";
      setMsgs((m) => [
        ...m,
        {
          role: "ai",
          blocks: {
            verdict: `问答失败：${message}`,
            evidence: [],
            next: ["稍后重试；如果刚上传资料，请先确认归档完成。"],
            related: [],
          },
        },
      ]);
    } finally {
      setPending(false);
    }
  }

  if (loading) {
    return (
      <div
        className="screen"
        style={{ background: "var(--bg)", alignItems: "center", justifyContent: "center", display: "flex" }}
      >
        <div style={{ color: "var(--ink-400)", fontSize: 14 }}>加载中…</div>
      </div>
    );
  }

  // Empty state: trial user just registered, no customers yet. Still allow
  // them to chat (cross-customer mode = "all"), but offer a primary CTA to
  // upload their first document.
  if (!customers.length) {
    return (
      <div className="screen" style={{ background: "var(--bg)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 12px 8px" }}>
          <button
            onClick={() => go("list")}
            style={{
              width: 36, height: 36, borderRadius: 18,
              background: "transparent", border: "none",
              display: "flex", alignItems: "center", justifyContent: "center",
              color: "var(--ink-700)", cursor: "pointer",
            }}
          >
            {I.back(20)}
          </button>
          <div style={{ fontSize: 15, fontWeight: 600, color: "var(--ink-900)" }}>问 AI</div>
        </div>
        <div
          style={{
            flex: 1, display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center",
            padding: "0 24px", textAlign: "center",
          }}
        >
          <div
            style={{
              width: 64, height: 64, borderRadius: 16,
              background: "linear-gradient(135deg, var(--ai-100), #d6deff)",
              color: "var(--ai-500)",
              display: "flex", alignItems: "center", justifyContent: "center",
              marginBottom: 16,
            }}
          >
            {I.spark(28)}
          </div>
          <div style={{ fontSize: 18, fontWeight: 700, color: "var(--ink-900)", marginBottom: 8 }}>
            还没有客户档案
          </div>
          <div
            style={{
              fontSize: 14, color: "var(--ink-500)",
              lineHeight: 1.6, maxWidth: 320, marginBottom: 24,
            }}
          >
            上传一份合同 / 名片 / 微信记录,AI 自动整理成档案后,你就可以来这里问关于这个客户的任何问题。
          </div>
          <button
            className="btn btn-primary"
            onClick={() => go("upload")}
            style={{ minWidth: 200 }}
          >
            {I.cloud(16, "#fff")}
            <span>上传第一份资料</span>
          </button>
        </div>
      </div>
    );
  }

  const totalReceivable = customers.reduce((s, c) => s + (c.metrics?.receivable ?? 0), 0);

  return (
    <div className="screen" style={{ background: "var(--bg)" }}>
      {isDesktop ? (
        <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", height: "100%" }}>
          {/* Customer rail */}
          <aside
            style={{
              borderRight: "1px solid var(--ink-100)",
              background: "var(--surface)",
              display: "flex",
              flexDirection: "column",
            }}
          >
            <div
              style={{
                padding: "16px 16px 8px",
                fontSize: 13,
                fontWeight: 600,
                color: "var(--ink-500)",
                letterSpacing: "0.04em",
                textTransform: "uppercase",
              }}
            >
              选择客户
            </div>
            <div className="scroll" style={{ flex: 1, padding: "0 8px 16px" }}>
              <CustomerRailItem
                active={isAll}
                onClick={() => {
                  setActiveId(ALL);
                  setMsgs([]);
                }}
                title="全部客户"
                sub={`跨客户汇总提问 · ${customers.length} 个`}
                ai
              />
              {customers.map((c) => (
                <CustomerRailItem
                  key={c.id}
                  active={c.id === activeId}
                  onClick={() => {
                    setActiveId(c.id);
                    setMsgs([]);
                  }}
                  title={c.name}
                  sub={c.tag}
                />
              ))}
            </div>
          </aside>

          {/* Chat main */}
          <div style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
            <ChatHeader
              isAll={isAll}
              customer={customer}
              onPickerOpen={() => setPickerOpen(true)}
              onBack={() => go("list")}
              hidePicker
            />
            {isAll ? (
              <ContextStripAll customers={customers.length} totalReceivable={totalReceivable} />
            ) : (
              customer && <ContextStripOne customer={customer} />
            )}
            <ChatBody
              msgs={msgs}
              pending={pending}
              suggestions={suggestions}
              isAll={isAll}
              onAsk={ask}
              scrollRef={scrollRef}
            />
            <Composer draft={draft} setDraft={setDraft} onSend={() => ask(draft)} />
          </div>
        </div>
      ) : (
        <>
          <ChatHeader
            isAll={isAll}
            customer={customer}
            onPickerOpen={() => setPickerOpen(true)}
            onBack={() => go("list")}
          />
          {isAll ? (
            <ContextStripAll customers={customers.length} totalReceivable={totalReceivable} />
          ) : (
            customer && <ContextStripOne customer={customer} />
          )}
          <ChatBody
            msgs={msgs}
            pending={pending}
            suggestions={suggestions}
            isAll={isAll}
            onAsk={ask}
            scrollRef={scrollRef}
          />
          <Composer draft={draft} setDraft={setDraft} onSend={() => ask(draft)} />

          {pickerOpen && (
            <CustomerPickerSheet
              customers={customers}
              activeId={activeId}
              onSelect={(id) => {
                setActiveId(id);
                setPickerOpen(false);
                setMsgs([]);
              }}
              onClose={() => setPickerOpen(false)}
            />
          )}
        </>
      )}
    </div>
  );
}

function CustomerRailItem({
  active,
  onClick,
  title,
  sub,
  ai,
}: {
  active: boolean;
  onClick: () => void;
  title: string;
  sub?: string;
  ai?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        width: "100%",
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "10px 10px",
        background: active ? (ai ? "var(--ai-50)" : "var(--brand-50)") : "transparent",
        borderRadius: 10,
        border: "none",
        cursor: "pointer",
        textAlign: "left",
        marginBottom: 2,
      }}
    >
      {ai && (
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: 14,
            background: "var(--ai-100)",
            color: "var(--ai-500)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          {I.spark(14)}
        </div>
      )}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: "var(--ink-900)" }}>{title}</div>
        {sub && (
          <div
            style={{
              fontSize: 11,
              color: "var(--ink-500)",
              marginTop: 2,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {sub}
          </div>
        )}
      </div>
      {active && <span style={{ color: ai ? "var(--ai-500)" : "var(--brand-500)" }}>{I.check(16)}</span>}
    </button>
  );
}

function ChatHeader({
  isAll,
  customer,
  onPickerOpen,
  onBack,
  hidePicker,
}: {
  isAll: boolean;
  customer: CustomerDetail | undefined;
  onPickerOpen: () => void;
  onBack: () => void;
  hidePicker?: boolean;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 12px 8px" }}>
      <button
        onClick={onBack}
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
        {I.back(20)}
      </button>
      <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{ fontSize: 13, color: "var(--ink-500)" }}>问问</div>
        {hidePicker ? (
          <div style={{ fontSize: 14, fontWeight: 600, color: "var(--ink-900)" }}>
            {isAll ? "全部客户" : customer?.name}
          </div>
        ) : (
          <button
            onClick={onPickerOpen}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "6px 12px",
              borderRadius: 10,
              background: "var(--surface)",
              border: "1px solid var(--ink-100)",
              cursor: "pointer",
            }}
          >
            <span style={{ fontSize: 14, fontWeight: 600, color: "var(--ink-900)" }}>
              {isAll ? "全部客户" : customer?.name}
            </span>
            <span style={{ color: "var(--ink-400)" }}>{I.chev(11)}</span>
          </button>
        )}
      </div>
    </div>
  );
}

function ContextStripAll({
  customers,
  totalReceivable,
}: {
  customers: number;
  totalReceivable: number;
}) {
  return (
    <div
      style={{
        margin: "0 16px 12px",
        padding: "10px 12px",
        borderRadius: 12,
        background: "var(--ai-50)",
        border: "1px solid #dfe5fb",
        display: "flex",
        alignItems: "center",
        gap: 10,
      }}
    >
      <span style={{ color: "var(--ai-500)" }}>{I.spark(14)}</span>
      <div style={{ fontSize: 12, color: "var(--ink-700)" }}>
        跨全部 <span className="num" style={{ fontWeight: 700 }}>{customers}</span> 个客户汇总回答
      </div>
      <div style={{ marginLeft: "auto", fontSize: 11, color: "var(--ink-500)" }}>
        总未收款{" "}
        <span className="num" style={{ color: "var(--warn-700)", fontWeight: 700 }}>
          {fmtCNYRaw(totalReceivable)}
        </span>
      </div>
    </div>
  );
}

function ContextStripOne({ customer }: { customer: CustomerDetail }) {
  return (
    <div
      style={{
        margin: "0 16px 12px",
        padding: "10px 12px",
        borderRadius: 12,
        background: "var(--surface)",
        border: "1px solid var(--ink-100)",
        display: "flex",
        alignItems: "center",
        gap: 10,
      }}
    >
      <div style={{ fontSize: 12, color: "var(--ink-700)" }}>
        未收款{" "}
        <span className="num" style={{ color: "var(--warn-700)", fontWeight: 700 }}>
          {fmtCNYRaw(customer.metrics.receivable)}
        </span>
      </div>
      <div style={{ marginLeft: "auto", fontSize: 11, color: "var(--ink-500)" }}>
        更新 {customer.updated}
      </div>
    </div>
  );
}

function ChatBody({
  msgs,
  pending,
  suggestions,
  isAll,
  onAsk,
  scrollRef,
}: {
  msgs: AskMessage[];
  pending: boolean;
  suggestions: string[];
  isAll: boolean;
  onAsk: (s: string) => void;
  scrollRef: React.Ref<HTMLDivElement>;
}) {
  const allSuggestions = isAll
    ? ["哪些客户最需要跟进？", "总未收款是多少？", "本周要优先联系谁？", "哪些客户风险较高？"]
    : suggestions;

  return (
    <div ref={scrollRef} className="scroll" style={{ flex: 1, padding: "0 16px 12px" }}>
      <div style={{ textAlign: "center", fontSize: 11, color: "var(--ink-400)", margin: "4px 0 12px" }}>今天 14:30</div>

      {msgs.map((m, i) => (m.role === "user" ? <UserBubble key={i} text={m.text} /> : <AIBubble key={i} block={m.blocks} />))}

      {pending && <PendingBubble />}

      {!pending && (
        <div style={{ marginTop: 16 }}>
          <div
            style={{
              fontSize: 11,
              color: "var(--ink-500)",
              fontWeight: 600,
              marginBottom: 8,
              textTransform: "uppercase",
              letterSpacing: "0.04em",
            }}
          >
            试试这样问
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {allSuggestions.map((s) => (
              <button
                key={s}
                onClick={() => onAsk(s)}
                className="pill"
                style={{
                  background: "var(--surface)",
                  color: "var(--ink-700)",
                  border: "1px solid var(--ink-100)",
                  padding: "7px 12px",
                  fontSize: 12,
                  fontWeight: 500,
                  cursor: "pointer",
                }}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Composer({
  draft,
  setDraft,
  onSend,
}: {
  draft: string;
  setDraft: (s: string) => void;
  onSend: () => void;
}) {
  return (
    <div
      style={{
        padding: "8px 12px 12px",
        background: "rgba(245,247,250,0.92)",
        borderTop: "1px solid var(--ink-100)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-end",
          gap: 8,
          background: "var(--surface)",
          borderRadius: 22,
          padding: "6px 6px 6px 14px",
          boxShadow: "var(--shadow-card-soft)",
          border: "1px solid var(--ink-100)",
        }}
      >
        <button
          style={{
            width: 32,
            height: 32,
            borderRadius: 16,
            background: "var(--surface-3)",
            color: "var(--ink-600)",
            border: "none",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
          }}
        >
          {I.plus(16)}
        </button>
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") onSend();
          }}
          placeholder="问客户的合同、回款、风险或下一步…"
          style={{
            flex: 1,
            border: "none",
            outline: "none",
            background: "transparent",
            fontSize: 14,
            fontFamily: "var(--font)",
            color: "var(--ink-800)",
            padding: "8px 0",
          }}
        />
        <button
          onClick={onSend}
          disabled={!draft.trim()}
          style={{
            width: 36,
            height: 36,
            borderRadius: 18,
            background: draft.trim() ? "var(--brand-500)" : "var(--ink-200)",
            color: "#fff",
            border: "none",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: draft.trim() ? "pointer" : "not-allowed",
          }}
        >
          {I.send(16, "#fff")}
        </button>
      </div>
    </div>
  );
}

function UserBubble({ text }: { text: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 12 }}>
      <div
        style={{
          background: "var(--brand-500)",
          color: "#fff",
          padding: "10px 14px",
          borderRadius: "18px 18px 4px 18px",
          fontSize: 14,
          fontWeight: 500,
          lineHeight: 1.45,
          maxWidth: "82%",
        }}
      >
        {text}
      </div>
    </div>
  );
}

function PendingBubble() {
  return (
    <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
      <div
        style={{
          width: 28,
          height: 28,
          borderRadius: 14,
          background: "var(--ai-100)",
          color: "var(--ai-500)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        {I.spark(13)}
      </div>
      <div
        style={{
          background: "var(--surface)",
          border: "1px solid var(--ink-100)",
          borderRadius: "18px 18px 18px 4px",
          padding: "10px 14px",
        }}
      >
        <div style={{ display: "flex", gap: 4 }}>
          <Dot delay={0} />
          <Dot delay={0.15} />
          <Dot delay={0.3} />
        </div>
        <style>{`
          @keyframes dotbounce { 0%, 80%, 100% { transform: translateY(0); opacity: 0.4; } 40% { transform: translateY(-4px); opacity: 1; } }
        `}</style>
      </div>
    </div>
  );
}

function Dot({ delay }: { delay: number }) {
  return (
    <span
      style={{
        width: 6,
        height: 6,
        borderRadius: 3,
        background: "var(--ai-500)",
        animation: `dotbounce 1.2s ${delay}s infinite ease-in-out`,
      }}
    />
  );
}

function AIBubble({ block }: { block: AskAIBlock }) {
  const hasEvidence = block.evidence.length > 0;
  const hasNext = block.next.length > 0;
  const hasRelated = block.related.length > 0;
  return (
    <div style={{ display: "flex", gap: 8, marginBottom: 16, alignItems: "flex-start" }}>
      <div
        style={{
          width: 28,
          height: 28,
          borderRadius: 14,
          background: "linear-gradient(135deg, #eaeefc, #d6deff)",
          color: "var(--ai-500)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        {I.spark(13)}
      </div>
      <div style={{ flex: 1, minWidth: 0, maxWidth: "calc(100% - 36px)" }}>
        <div className="card" style={{ padding: 14, borderRadius: "14px 14px 14px 4px" }}>
          {/* Verdict */}
          <SectionHeader icon={I.warn(14)} iconColor="var(--warn-500)" label="当前结论" />
          <div style={{ fontSize: 14.5, lineHeight: 1.55, color: "var(--ink-900)" }}>{block.verdict}</div>

          {hasEvidence && (
            <>
              <div className="sep" style={{ margin: "12px 0 10px" }} />
              <SectionHeader icon={I.link(13)} iconColor="var(--ink-500)" label="证据支持" />
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {block.evidence.map((e) => (
                  <EvidenceChip key={e.id} type={e.type} label={e.label} />
                ))}
              </div>
            </>
          )}

          {hasNext && (
            <>
              <div className="sep" style={{ margin: "12px 0 10px" }} />
              <SectionHeader icon={I.bulb(13)} iconColor="var(--ai-500)" label="下一步建议" />
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {block.next.map((n, i) => (
                  <div key={i} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                    <div
                      style={{
                        width: 18,
                        height: 18,
                        borderRadius: 9,
                        background: "var(--ai-100)",
                        color: "var(--ai-700)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: 11,
                        fontWeight: 700,
                        flexShrink: 0,
                        marginTop: 1,
                      }}
                    >
                      {i + 1}
                    </div>
                    <div style={{ fontSize: 13.5, lineHeight: 1.55, color: "var(--ink-800)", flex: 1 }}>{n}</div>
                  </div>
                ))}
              </div>
            </>
          )}

          {hasRelated && (
            <>
              <div className="sep" style={{ margin: "12px 0 10px" }} />
              <div
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  color: "var(--ink-500)",
                  letterSpacing: "0.04em",
                  textTransform: "uppercase",
                  marginBottom: 8,
                }}
              >
                相关记录
              </div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {block.related.map((r, i) => (
                  <span
                    key={i}
                    className="pill pill-ink"
                    style={{ fontSize: 11, padding: "4px 10px", fontWeight: 500, color: "var(--ink-700)" }}
                  >
                    <span style={{ color: "var(--ink-500)" }}>
                      {r.kind === "联系人" ? I.customers(11) : I.doc(11)}
                    </span>
                    {r.label}
                  </span>
                ))}
              </div>
            </>
          )}
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 6, paddingLeft: 4 }}>
          <button style={{ background: "transparent", border: "none", fontSize: 11, color: "var(--ink-500)", cursor: "pointer" }}>
            👍
          </button>
          <button style={{ background: "transparent", border: "none", fontSize: 11, color: "var(--ink-500)", cursor: "pointer" }}>
            👎
          </button>
          <button
            style={{ background: "transparent", border: "none", fontSize: 11, color: "var(--brand-500)", cursor: "pointer", fontWeight: 600 }}
          >
            + 加入待办
          </button>
        </div>
      </div>
    </div>
  );
}

function SectionHeader({
  icon,
  iconColor,
  label,
}: {
  icon: React.ReactNode;
  iconColor: string;
  label: string;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
      <span style={{ color: iconColor }}>{icon}</span>
      <div
        style={{
          fontSize: 12,
          fontWeight: 700,
          color: "var(--ink-500)",
          letterSpacing: "0.04em",
          textTransform: "uppercase",
        }}
      >
        {label}
      </div>
    </div>
  );
}

function CustomerPickerSheet({
  customers,
  activeId,
  onSelect,
  onClose,
}: {
  customers: CustomerDetail[];
  activeId: string;
  onSelect: (id: string) => void;
  onClose: () => void;
}) {
  const isAll = activeId === ALL;
  return (
    <>
      <div onClick={onClose} style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.35)", zIndex: 30 }} />
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 0,
          zIndex: 40,
          background: "var(--bg)",
          borderRadius: "20px 20px 0 0",
          display: "flex",
          flexDirection: "column",
          height: "55%",
          boxShadow: "0 -10px 30px rgba(0,0,0,0.18)",
        }}
      >
        <div
          style={{
            width: 36,
            height: 5,
            borderRadius: 99,
            background: "var(--ink-300)",
            margin: "8px auto 0",
          }}
        />
        <div style={{ padding: "14px 16px 8px", fontSize: 16, fontWeight: 700 }}>选择要问的客户</div>
        <div className="scroll" style={{ flex: 1, padding: "0 12px 24px" }}>
          <CustomerRailItem
            active={isAll}
            onClick={() => onSelect(ALL)}
            title="全部客户"
            sub="跨客户汇总提问"
            ai
          />
          <div style={{ height: 1, background: "var(--ink-100)", margin: "8px 12px" }} />
          {customers.map((c) => (
            <CustomerRailItem
              key={c.id}
              active={c.id === activeId}
              onClick={() => onSelect(c.id)}
              title={c.name}
              sub={c.tag}
            />
          ))}
        </div>
      </div>
    </>
  );
}
