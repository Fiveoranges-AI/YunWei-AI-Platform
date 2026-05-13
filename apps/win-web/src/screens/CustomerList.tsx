import { useEffect, useState } from "react";
import { deleteAllCustomers, getCustomer, listCustomers } from "../api/client";
import { CustomerDetailPane } from "../components/CustomerDetailPane";
import type { CustomerDetail } from "../data/types";
import { I } from "../icons";
import { useIsDesktop, useIsTablet } from "../lib/breakpoints";
import { onCustomersChanged } from "../lib/customerRefresh";
import { fmtCNYBig } from "../lib/format";
import type { GoFn } from "../App";

type FilterId = "all" | "key" | "warn" | "lead";

export function CustomerListScreen({ go }: { go: GoFn }) {
  const isDesktop = useIsDesktop();
  const isTablet = useIsTablet();
  const isWide = isDesktop || isTablet;

  const [customers, setCustomers] = useState<CustomerDetail[]>([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterId>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<CustomerDetail | null>(null);
  const [bulkDeleting, setBulkDeleting] = useState(false);
  const [bulkError, setBulkError] = useState<string | null>(null);

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
          if (!selectedId && rows.length > 0) setSelectedId(rows[0].id);
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Lazy-load the full detail for the selected customer (desktop right pane).
  useEffect(() => {
    if (!isWide || !selectedId) {
      setSelectedDetail(null);
      return;
    }
    let cancelled = false;
    getCustomer(selectedId)
      .then((c) => {
        if (!cancelled) setSelectedDetail(c ?? null);
      })
      .catch(() => {
        if (!cancelled) setSelectedDetail(null);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId, isWide]);

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
      setSelectedId(null);
      setSelectedDetail(null);
    } catch (e) {
      setBulkError(e instanceof Error ? e.message : "清空失败");
    } finally {
      setBulkDeleting(false);
    }
  }

  const filtered = customers.filter((c) => {
    if (q && !c.name.includes(q)) return false;
    if (filter === "all") return true;
    if (filter === "key") return c.tag === "重点客户";
    if (filter === "warn") return c.tag === "注意客户" || c.risk?.level === "high";
    if (filter === "lead") return c.tag === "潜在客户";
    return true;
  });

  const filters: { id: FilterId; label: string; count: number }[] = [
    { id: "all", label: "全部", count: customers.length },
    { id: "key", label: "重点", count: customers.filter((c) => c.tag === "重点客户").length },
    {
      id: "warn",
      label: "注意",
      count: customers.filter((c) => c.tag === "注意客户" || c.risk?.level === "high").length,
    },
    { id: "lead", label: "潜在", count: customers.filter((c) => c.tag === "潜在客户").length },
  ];

  // ──────────────── Desktop / tablet — two pane ────────────────
  if (isWide) {
    return (
      <div style={{ flex: 1, display: "flex", minHeight: 0 }}>
        {/* Left list pane */}
        <div
          style={{
            width: 380,
            flexShrink: 0,
            borderRight: "1px solid var(--ink-100)",
            display: "flex",
            flexDirection: "column",
            background: "#fff",
          }}
        >
          <FilterStrip filter={filter} setFilter={setFilter} filters={filters} />

          {bulkError && (
            <div
              style={{
                margin: 12,
                fontSize: 12,
                color: "var(--risk-700)",
                background: "var(--risk-100)",
                border: "1px solid #f4cfcf",
                padding: "8px 10px",
                borderRadius: 8,
              }}
            >
              {bulkError}
            </div>
          )}

          <div className="scroll" style={{ flex: 1 }}>
            {loading && <EmptyHint text="读取真实客户档案…" />}
            {loadError && (
              <EmptyHint text={`客户列表加载失败：${loadError}`} />
            )}
            {!loading && !loadError && filtered.length === 0 && (
              <EmptyHint
                text={q ? "没有匹配的客户" : "还没有客户档案"}
                cta={
                  q
                    ? undefined
                    : { label: "上传第一份资料", onClick: () => go("upload") }
                }
              />
            )}
            {filtered.map((c) => (
              <CustomerRow
                key={c.id}
                customer={c}
                active={c.id === selectedId}
                onClick={() => setSelectedId(c.id)}
              />
            ))}
          </div>

          {customers.length > 0 && (
            <div
              style={{
                padding: "10px 16px",
                borderTop: "1px solid var(--ink-100)",
                display: "flex",
                justifyContent: "flex-end",
                gap: 8,
              }}
            >
              <button
                onClick={handleClearAll}
                disabled={bulkDeleting}
                style={{
                  height: 28,
                  padding: "0 12px",
                  borderRadius: 8,
                  background: "transparent",
                  border: "1px solid var(--ink-100)",
                  color: "var(--ink-500)",
                  cursor: bulkDeleting ? "not-allowed" : "pointer",
                  fontFamily: "var(--font)",
                  fontSize: 11.5,
                  fontWeight: 600,
                  opacity: bulkDeleting ? 0.6 : 1,
                }}
              >
                {bulkDeleting ? "清空中…" : "清空全部"}
              </button>
            </div>
          )}
        </div>

        {/* Right detail pane */}
        {selectedDetail ? (
          <CustomerDetailPane
            customer={selectedDetail}
            onAsk={() => go("ask", { id: selectedDetail.id })}
            onEdit={() => go("detail", { id: selectedDetail.id })}
            compact={isTablet}
          />
        ) : (
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
            {selectedId ? "客户档案加载中…" : "选择左侧客户查看完整档案"}
          </div>
        )}
      </div>
    );
  }

  // ──────────────── Mobile — list-first with drill-in ────────────────
  return (
    <div className="screen" style={{ background: "var(--bg)" }}>
      <div style={{ padding: "12px 16px 8px" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 12,
          }}
        >
          <div style={{ fontSize: 22, fontWeight: 700, color: "var(--ink-900)", letterSpacing: "-0.01em" }}>
            客户
          </div>
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
                color: "var(--ink-500)",
                cursor: bulkDeleting ? "not-allowed" : "pointer",
                fontFamily: "var(--font)",
                fontSize: 12,
                fontWeight: 600,
                opacity: bulkDeleting ? 0.6 : 1,
              }}
            >
              {bulkDeleting ? "清空中…" : "清空"}
            </button>
          )}
        </div>

        {/* Search */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            background: "var(--surface)",
            borderRadius: 14,
            padding: "10px 14px",
            border: "1px solid var(--ink-100)",
            boxShadow: "var(--shadow-card-soft)",
          }}
        >
          <span style={{ color: "var(--ink-400)", display: "flex" }}>{I.search(18)}</span>
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
        </div>

        {bulkError && (
          <div
            style={{
              marginTop: 8,
              fontSize: 12,
              color: "var(--risk-700)",
              background: "var(--risk-100)",
              border: "1px solid #f4cfcf",
              padding: "6px 10px",
              borderRadius: 8,
            }}
          >
            {bulkError}
          </div>
        )}
      </div>

      <div className="scroll" style={{ flex: 1, padding: "0 16px 100px" }}>
        {loading && (
          <div style={{ padding: 24, textAlign: "center", color: "var(--ink-400)", fontSize: 13 }}>
            读取真实客户档案…
          </div>
        )}
        {loadError && (
          <div className="card" style={{ padding: 16, color: "var(--risk-700)" }}>
            客户列表加载失败：{loadError}
          </div>
        )}
        {!loading && !loadError && filtered.length === 0 && (
          <div className="card" style={{ padding: 16 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: "var(--ink-900)" }}>
              {q ? "没有匹配的客户" : "还没有客户档案"}
            </div>
            <div style={{ fontSize: 13, color: "var(--ink-500)", marginTop: 6 }}>
              {q ? "换个关键词再试试。" : "上传合同或名片后，客户会出现在这里。"}
            </div>
            {!q && (
              <button
                className="btn btn-primary"
                style={{ marginTop: 12 }}
                onClick={() => go("upload")}
              >
                {I.cloud(16, "#fff")}
                <span>上传资料</span>
              </button>
            )}
          </div>
        )}

        {filtered.map((c) => (
          <MobileCustomerCard
            key={c.id}
            customer={c}
            onClick={() => go("detail", { id: c.id })}
          />
        ))}
      </div>
    </div>
  );
}

// ──────────────── pieces ────────────────

function FilterStrip({
  filter,
  setFilter,
  filters,
}: {
  filter: FilterId;
  setFilter: (f: FilterId) => void;
  filters: { id: FilterId; label: string; count: number }[];
}) {
  return (
    <div
      style={{
        display: "flex",
        gap: 22,
        padding: "14px 24px 0",
        borderBottom: "1px solid var(--ink-100)",
      }}
    >
      {filters.map((t) => {
        const active = t.id === filter;
        return (
          <button
            key={t.id}
            onClick={() => setFilter(t.id)}
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
            {t.label}
            <span
              className="num"
              style={{
                fontSize: 10.5,
                fontWeight: 600,
                color: active ? "var(--ink-500)" : "var(--ink-300)",
              }}
            >
              {t.count}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function CustomerRow({
  customer,
  active,
  onClick,
}: {
  customer: CustomerDetail;
  active: boolean;
  onClick: () => void;
}) {
  const dot =
    customer.risk?.level === "high" ? "#EF4444" :
    customer.risk?.level === "med" ? "#F59E0B" :
    customer.tag === "潜在客户" ? "#2D9BD8" : "#10B981";
  return (
    <button
      onClick={onClick}
      style={{
        width: "100%",
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "13px 24px",
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
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: 9,
          flexShrink: 0,
          background: customer.color || "#1F5FA3",
          color: "#fff",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 11.5,
          fontWeight: 700,
        }}
      >
        {customer.monogram}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
          <span
            style={{
              fontSize: 13.5,
              fontWeight: 600,
              color: "var(--ink-900)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {customer.name}
          </span>
          <span
            style={{
              width: 5,
              height: 5,
              borderRadius: 3,
              background: dot,
              flexShrink: 0,
            }}
          />
        </div>
        <div
          style={{
            fontSize: 11,
            color: "var(--ink-500)",
            marginTop: 3,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {customer.aiSummary.slice(0, 36)}{customer.aiSummary.length > 36 ? "…" : ""}
        </div>
      </div>
      <div style={{ textAlign: "right", flexShrink: 0 }}>
        {customer.metrics.receivable > 0 ? (
          <div className="num" style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-900)" }}>
            ¥ {fmtCNYBig(customer.metrics.receivable)}
          </div>
        ) : (
          <div style={{ fontSize: 11, color: "var(--ink-300)" }}>—</div>
        )}
        <div style={{ fontSize: 10.5, color: "var(--ink-400)", marginTop: 2 }}>{customer.updated}</div>
      </div>
    </button>
  );
}

function MobileCustomerCard({
  customer,
  onClick,
}: {
  customer: CustomerDetail;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="card"
      style={{
        width: "100%",
        textAlign: "left",
        padding: 14,
        marginBottom: 10,
        cursor: "pointer",
        display: "flex",
        alignItems: "center",
        gap: 12,
        fontFamily: "var(--font)",
      }}
    >
      <div
        style={{
          width: 40,
          height: 40,
          borderRadius: 10,
          flexShrink: 0,
          background: customer.color || "#1F5FA3",
          color: "#fff",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 13,
          fontWeight: 700,
        }}
      >
        {customer.monogram}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 15, fontWeight: 700, color: "var(--ink-900)" }}>
            {customer.name}
          </span>
          <span className="pill pill-ink" style={{ fontSize: 10, padding: "2px 7px" }}>
            {customer.tag}
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
          <span style={{ color: "var(--ai-500)", display: "flex" }}>{I.spark(11)}</span>
          <span
            style={{
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {customer.aiSummary.slice(0, 36)}{customer.aiSummary.length > 36 ? "…" : ""}
          </span>
        </div>
      </div>
      <div style={{ textAlign: "right" }}>
        {customer.metrics.receivable > 0 && (
          <div className="num" style={{ fontSize: 13, fontWeight: 600, color: "var(--warn-700)" }}>
            ¥ {fmtCNYBig(customer.metrics.receivable)}
          </div>
        )}
        <div style={{ fontSize: 11, color: "var(--ink-400)", marginTop: 2 }}>
          {customer.updated}
        </div>
      </div>
    </button>
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
