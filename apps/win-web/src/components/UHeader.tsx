import type { ReactNode } from "react";
import { I } from "../icons";
import type { TabName } from "../App";

type Props = {
  title: ReactNode;
  sub?: ReactNode;
  view: TabName;
  compact?: boolean;
  /** Optional search input controlled by parent (only rendered when view === "customers"). */
  searchValue?: string;
  onSearchChange?: (v: string) => void;
  /** Slot rendered on the far right of the header — useful for screen-specific
   *  actions (e.g. "清空" on customers, "编辑" on detail). */
  right?: ReactNode;
};

export function UHeader({
  title,
  sub,
  view,
  compact = false,
  searchValue,
  onSearchChange,
  right,
}: Props) {
  const showSearch = view === "customers";

  return (
    <div
      style={{
        height: 60,
        flexShrink: 0,
        padding: compact ? "0 24px" : "0 32px",
        display: "flex",
        alignItems: "center",
        gap: 24,
        borderBottom: "1px solid var(--ink-100)",
        background: "#fff",
      }}
    >
      <div style={{ flexShrink: 0, minWidth: 0 }}>
        <div
          style={{
            fontSize: 15,
            fontWeight: 600,
            color: "var(--ink-900)",
            letterSpacing: "-0.005em",
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {title}
        </div>
        {sub && (
          <div style={{ fontSize: 11.5, color: "var(--ink-400)", marginTop: 1 }}>{sub}</div>
        )}
      </div>

      <div style={{ flex: 1 }} />

      {/* Search — customers page only */}
      {showSearch && (
        <div style={{ width: compact ? 320 : 380, flexShrink: 0 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "7px 12px",
              borderRadius: 10,
              background: "var(--ink-50)",
              border: "1px solid var(--ink-100)",
            }}
          >
            <span style={{ color: "var(--ink-400)", display: "flex" }}>{I.search(14)}</span>
            <input
              type="text"
              value={searchValue ?? ""}
              onChange={(e) => onSearchChange?.(e.target.value)}
              placeholder="搜索客户、合同、规格……"
              style={{
                flex: 1,
                border: "none",
                outline: "none",
                background: "transparent",
                fontFamily: "var(--font)",
                fontSize: 12.5,
                color: "var(--ink-800)",
              }}
            />
            <span
              style={{
                marginLeft: "auto",
                fontSize: 10,
                color: "var(--ink-400)",
                padding: "1px 5px",
                border: "1px solid var(--ink-200)",
                borderRadius: 4,
                background: "#fff",
                fontFamily: "ui-monospace, monospace",
              }}
            >
              ⌘K
            </span>
          </div>
        </div>
      )}

      {right && <div style={{ flexShrink: 0 }}>{right}</div>}
    </div>
  );
}
