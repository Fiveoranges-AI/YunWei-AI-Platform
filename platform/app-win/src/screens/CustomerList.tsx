import { useEffect, useState, type ReactNode } from "react";
import { deleteAllCustomers, getMe, listCustomers } from "../api/client";
import { AISummary } from "../components/AISummary";
import { MiniStat } from "../components/MiniStat";
import type { CustomerDetail } from "../data/types";
import { I } from "../icons";
import { useIsDesktop } from "../lib/breakpoints";
import { onCustomersChanged } from "../lib/customerRefresh";
import { fmtCNYRaw } from "../lib/format";
import type { GoFn } from "../App";

export function CustomerListScreen({ go }: { go: GoFn }) {
  const [customers, setCustomers] = useState<CustomerDetail[]>([]);
  const [q, setQ] = useState("");
  const [displayName, setDisplayName] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [bulkDeleting, setBulkDeleting] = useState(false);
  const [bulkError, setBulkError] = useState<string | null>(null);
  const isDesktop = useIsDesktop();

  async function handleClearAll() {
    if (customers.length === 0) return;
    if (
      !window.confirm(
        `这将删除全部 ${customers.length} 个客户，包括他们的合同、订单、联系人、任务和风险记录。原始上传文档保留作为审计。继续吗？`,
      )
    )
      return;
    const typed = window.prompt(`再次确认：输入「清空全部客户」以继续。`);
    if (typed !== "清空全部客户") {
      if (typed !== null) window.alert("输入不匹配，已取消。");
      return;
    }
    setBulkDeleting(true);
    setBulkError(null);
    try {
      await deleteAllCustomers();
      setCustomers([]);
    } catch (e) {
      setBulkError(e instanceof Error ? e.message : "清空失败");
    } finally {
      setBulkDeleting(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    let requestId = 0;

    function load(showLoading: boolean) {
      const id = ++requestId;
      if (showLoading) setLoading(true);
      listCustomers()
        .then((rows) => {
          if (cancelled || id !== requestId) return;
          setCustomers(rows);
          setLoadError(null);
        })
        .catch((e) => {
          if (cancelled || id !== requestId) return;
          setLoadError(e instanceof Error ? e.message : "客户列表加载失败");
        })
        .finally(() => {
          if (!cancelled && id === requestId) setLoading(false);
        });
    }

    load(true);
    const stopListening = onCustomersChanged(() => load(false));
    const onFocus = () => load(false);
    window.addEventListener("focus", onFocus);
    return () => {
      cancelled = true;
      stopListening();
      window.removeEventListener("focus", onFocus);
    };
  }, []);

  useEffect(() => {
    // Greeting uses the platform's logged-in user. /api/me lives on the
    // platform host (same origin as /win/), returns { display_name, ... }.
    let cancelled = false;
    getMe()
      .then((body) => {
        if (cancelled) return;
        const name = (body.display_name || body.username || "").trim();
        if (name) setDisplayName(name);
      })
      .catch(() => {
        /* silently fall back to nameless greeting */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = customers.filter((c) => q === "" || c.name.includes(q));
  const featured = filtered[0];
  const rest = filtered.slice(1);

  return (
    <div className="screen" style={{ background: "var(--bg)" }}>
      {/* Header — greeting + search */}
      <div
        style={{
          padding: isDesktop ? "20px 32px 12px" : "8px 16px 8px",
          maxWidth: isDesktop ? 1280 : undefined,
          width: "100%",
          margin: "0 auto",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginTop: 4,
          }}
        >
          <div>
            <div style={{ color: "var(--ink-500)", fontSize: 13 }}>你好，</div>
            <div
              style={{
                fontSize: isDesktop ? 28 : 22,
                fontWeight: 700,
                color: "var(--ink-900)",
                letterSpacing: "-0.01em",
              }}
            >
              {displayName || "—"}
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {customers.length > 0 && (
              <button
                onClick={handleClearAll}
                disabled={bulkDeleting}
                style={{
                  height: 32,
                  padding: "0 12px",
                  borderRadius: 16,
                  background: "transparent",
                  border: "1px solid var(--ink-100)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "var(--ink-500)",
                  cursor: bulkDeleting ? "not-allowed" : "pointer",
                  fontFamily: "var(--font)",
                  fontSize: 12,
                  fontWeight: 600,
                  opacity: bulkDeleting ? 0.6 : 1,
                }}
                aria-label="清空全部客户"
              >
                {bulkDeleting ? "清空中…" : "清空"}
              </button>
            )}
            <button
              style={{
                width: 40,
                height: 40,
                borderRadius: 20,
                background: "var(--surface)",
                border: "1px solid var(--ink-100)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                boxShadow: "var(--shadow-card)",
                color: "var(--ink-700)",
                cursor: "pointer",
              }}
              aria-label="search"
            >
              {I.search(18)}
            </button>
          </div>
        </div>
        {bulkError && (
          <div
            style={{
              marginTop: 8,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 8,
              fontSize: 12,
              color: "var(--risk-700)",
              background: "var(--risk-100)",
              border: "1px solid #f4cfcf",
              padding: "6px 10px",
              borderRadius: 10,
            }}
          >
            <span>{bulkError}</span>
            <button
              onClick={() => setBulkError(null)}
              style={{
                border: "none",
                background: "transparent",
                color: "var(--risk-700)",
                cursor: "pointer",
                fontFamily: "var(--font)",
                fontSize: 12,
                fontWeight: 600,
              }}
              aria-label="dismiss"
            >
              关闭
            </button>
          </div>
        )}
      </div>

      <div
        className="scroll"
        style={{
          flex: 1,
          padding: isDesktop ? "8px 32px 40px" : "4px 16px 100px",
          width: "100%",
          maxWidth: isDesktop ? 1280 : undefined,
          margin: "0 auto",
        }}
      >
        {/* Search input */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            background: "var(--surface)",
            borderRadius: 14,
            padding: "11px 14px",
            border: "1px solid var(--ink-100)",
            marginBottom: 16,
            boxShadow: "var(--shadow-card-soft)",
          }}
        >
          <span style={{ color: "var(--ink-400)" }}>{I.search(18)}</span>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="搜索客户、合同、联系人或语音备注…"
            style={{
              flex: 1,
              border: "none",
              outline: "none",
              background: "transparent",
              fontFamily: "var(--font)",
              fontSize: 14,
              color: "var(--ink-800)",
            }}
          />
          <span className="pill pill-ai" style={{ fontSize: 11, padding: "3px 8px" }}>
            {I.spark(11)} AI
          </span>
        </div>

        {/* AI 今日要点 */}
        <AISummary style={{ marginBottom: 16 }}>
          {renderListInsight(customers, loading)}
        </AISummary>

        {loadError && <ListStateCard tone="risk" title="客户列表加载失败" detail={loadError} />}

        {!loadError && !loading && filtered.length === 0 && (
          <ListStateCard
            tone="empty"
            title={q ? "没有匹配的客户" : "还没有客户档案"}
            detail={q ? "换个关键词再试试。" : "上传合同或名片后，客户会出现在这里。"}
            actionLabel={q ? undefined : "上传资料"}
            onAction={q ? undefined : () => go("upload")}
          />
        )}

        {/* Featured customer */}
        {!loadError && featured && (
          <FeaturedCustomerCard
            customer={featured}
            onClick={() => go("detail", { id: featured.id })}
          />
        )}

        {/* Other customers */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: isDesktop ? "1fr 1fr" : "1fr",
            gap: isDesktop ? 14 : 10,
          }}
        >
          {!loadError && rest.map((c) => (
            <CompactCustomerCard
              key={c.id}
              customer={c}
              onClick={() => go("detail", { id: c.id })}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function renderListInsight(customers: CustomerDetail[], loading: boolean): ReactNode {
  if (loading) return "正在读取真实客户档案…";
  if (!customers.length) return "当前还没有客户档案。上传合同或名片后，AI 会自动整理客户、联系人和后续事项。";

  const receivable = customers.reduce((sum, c) => sum + (c.metrics?.receivable ?? 0), 0);
  const tasks = customers.reduce((sum, c) => sum + (c.metrics?.tasks ?? 0), 0);
  const highRisk = customers.filter((c) => c.risk?.level === "high").length;
  const parts = [
    receivable > 0 ? `未收款 ${fmtCNYRaw(receivable)}` : null,
    tasks > 0 ? `待办 ${tasks} 项` : null,
    highRisk > 0 ? `高风险客户 ${highRisk} 个` : null,
  ].filter(Boolean);

  return (
    <>
      <span style={{ fontWeight: 600 }}>当前 {customers.length} 个客户档案：</span>{" "}
      {parts.length ? parts.join("；") : "暂无待办、风险或未收款。"}
    </>
  );
}

function ListStateCard({
  tone,
  title,
  detail,
  actionLabel,
  onAction,
}: {
  tone: "risk" | "empty";
  title: string;
  detail: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  const isRisk = tone === "risk";
  return (
    <div
      className="card"
      style={{
        padding: 16,
        marginBottom: 12,
        border: isRisk ? "1px solid #f4cfcf" : "1px solid var(--ink-100)",
        background: isRisk ? "var(--risk-100)" : "var(--surface)",
      }}
    >
      <div style={{ fontSize: 15, fontWeight: 700, color: isRisk ? "var(--risk-700)" : "var(--ink-900)" }}>
        {title}
      </div>
      <div style={{ fontSize: 13, color: isRisk ? "var(--risk-700)" : "var(--ink-500)", marginTop: 6 }}>
        {detail}
      </div>
      {actionLabel && onAction && (
        <button className="btn btn-primary" onClick={onAction} style={{ marginTop: 12 }}>
          {I.cloud(16, "#fff")}
          <span>{actionLabel}</span>
        </button>
      )}
    </div>
  );
}

function FeaturedCustomerCard({
  customer,
  onClick,
}: {
  customer: CustomerDetail;
  onClick: () => void;
}) {
  return (
    <div
      className="card"
      style={{ padding: 16, marginBottom: 12, cursor: "pointer" }}
      onClick={onClick}
    >
      <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 2 }}>
            <div
              style={{
                fontSize: 17,
                fontWeight: 700,
                color: "var(--ink-900)",
                letterSpacing: "-0.01em",
              }}
            >
              {customer.name}
            </div>
          </div>
          <div style={{ fontSize: 12, color: "var(--ink-500)" }}>
            最近更新 · {customer.updated}
          </div>
        </div>
      </div>

      {/* AI summary inline */}
      <div
        style={{
          marginTop: 12,
          padding: "10px 12px",
          background: "var(--ai-50)",
          borderRadius: 12,
          border: "1px solid #e7ecfb",
          display: "flex",
          gap: 8,
          alignItems: "flex-start",
        }}
      >
        <span style={{ color: "var(--ai-500)", marginTop: 2 }}>{I.spark(13)}</span>
        <div style={{ fontSize: 13, lineHeight: 1.55, color: "var(--ink-800)" }}>
          {customer.aiSummary}
        </div>
      </div>

      {/* Mini stats */}
      <div
        style={{
          display: "flex",
          gap: 12,
          marginTop: 12,
          paddingTop: 12,
          borderTop: "1px dashed var(--ink-100)",
        }}
      >
        <MiniStat label="未收款" value={fmtCNYRaw(customer.metrics.receivable)} tone="warn" />
        <div style={{ width: 1, background: "var(--ink-100)" }} />
        <MiniStat label="合同" value={customer.metrics.contracts} />
        <div style={{ width: 1, background: "var(--ink-100)" }} />
        <MiniStat label="待办" value={customer.metrics.tasks} tone="ai" />
        <div style={{ width: 1, background: "var(--ink-100)" }} />
        <MiniStat label="联系人" value={customer.metrics.contacts} />
      </div>
    </div>
  );
}

function CompactCustomerCard({
  customer,
  onClick,
}: {
  customer: CustomerDetail;
  onClick: () => void;
}) {
  return (
    <div
      className="card"
      style={{ padding: 14, cursor: "pointer" }}
      onClick={onClick}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: "var(--ink-900)" }}>
              {customer.name}
            </div>
            <span className="pill pill-ink" style={{ fontSize: 10, padding: "2px 7px" }}>
              {customer.tag}
            </span>
          </div>
          <div
            style={{
              fontSize: 12,
              color: "var(--ink-500)",
              marginTop: 2,
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <span style={{ color: "var(--ai-500)" }}>{I.spark(11)}</span>
            <span
              style={{
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {customer.aiSummary.slice(0, 30)}…
            </span>
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 11, color: "var(--ink-400)" }}>{customer.updated}</div>
        </div>
      </div>
    </div>
  );
}
