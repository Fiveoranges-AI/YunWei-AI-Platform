// Shared chrome for the 设置 panels: a centered modal on desktop, a
// bottom sheet on mobile. Plus small form primitives (Field / Toggle /
// Btn / Banner) so the seven panels stay visually consistent without
// re-deriving styles.

import { useEffect, useId, useRef, type CSSProperties, type ReactNode } from "react";
import { I } from "../../icons";
import { useIsDesktop, useIsTablet } from "../../lib/breakpoints";

export function SettingsSheet({
  title,
  subtitle,
  onClose,
  children,
  footer,
}: {
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const isWide = useIsDesktop() || useIsTablet();
  const titleId = useId();
  const sheetRef = useRef<HTMLDivElement>(null);
  // Keep the latest onClose without re-running the open/close effect every
  // render (the parent passes a fresh arrow each time).
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    const trigger = document.activeElement as HTMLElement | null;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden"; // lock background scroll
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onCloseRef.current();
      }
    };
    document.addEventListener("keydown", onKey);
    sheetRef.current?.focus(); // move focus into the sheet for keyboard / SR users
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
      trigger?.focus?.(); // restore focus to whatever opened the sheet
    };
  }, []);

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(15,35,64,0.45)",
        display: "flex",
        alignItems: isWide ? "center" : "flex-end",
        justifyContent: "center",
        padding: isWide ? 24 : 0,
        zIndex: 200,
      }}
    >
      <div
        ref={sheetRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        style={{
          outline: "none",
          width: isWide ? 460 : "100%",
          maxWidth: "100%",
          maxHeight: isWide ? "86vh" : "92vh",
          display: "flex",
          flexDirection: "column",
          background: "#fff",
          borderRadius: isWide ? 16 : "16px 16px 0 0",
          boxShadow: "0 24px 64px rgba(15,35,64,0.22)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 12,
            padding: "18px 20px 14px",
            borderBottom: "1px solid var(--ink-100)",
          }}
        >
          <div style={{ flex: 1, minWidth: 0 }}>
            <div id={titleId} style={{ fontSize: 16, fontWeight: 700, color: "var(--ink-900)" }}>{title}</div>
            {subtitle && (
              <div style={{ fontSize: 12, color: "var(--ink-500)", marginTop: 3 }}>{subtitle}</div>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="关闭"
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              border: "none",
              background: "var(--surface-3)",
              color: "var(--ink-600)",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            {I.close(16)}
          </button>
        </div>

        <div style={{ flex: 1, overflowY: "auto", padding: "16px 20px" }}>{children}</div>

        {footer && (
          <div
            style={{
              display: "flex",
              gap: 10,
              padding: "12px 20px",
              borderTop: "1px solid var(--ink-100)",
              background: "var(--surface-2)",
            }}
          >
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label style={{ display: "block", marginBottom: 14 }}>
      <div style={{ fontSize: 12.5, fontWeight: 600, color: "var(--ink-700)", marginBottom: 6 }}>
        {label}
      </div>
      {children}
      {hint && <div style={{ fontSize: 11, color: "var(--ink-400)", marginTop: 5 }}>{hint}</div>}
    </label>
  );
}

const inputStyle: CSSProperties = {
  width: "100%",
  height: 40,
  padding: "0 12px",
  borderRadius: 9,
  border: "1px solid var(--ink-200)",
  background: "#fff",
  fontSize: 14,
  color: "var(--ink-900)",
  fontFamily: "var(--font)",
  boxSizing: "border-box",
};

export function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} style={{ ...inputStyle, ...(props.style || {}) }} />;
}

export function Toggle({
  on,
  onChange,
}: {
  on: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <button
      role="switch"
      aria-checked={on}
      onClick={() => onChange(!on)}
      style={{
        width: 44,
        height: 26,
        borderRadius: 13,
        border: "none",
        background: on ? "var(--brand-500, #2680CC)" : "var(--ink-200)",
        position: "relative",
        cursor: "pointer",
        flexShrink: 0,
        transition: "background 0.15s",
        padding: 0,
      }}
    >
      <span
        style={{
          position: "absolute",
          top: 3,
          left: on ? 21 : 3,
          width: 20,
          height: 20,
          borderRadius: 10,
          background: "#fff",
          boxShadow: "0 1px 3px rgba(0,0,0,0.25)",
          transition: "left 0.15s",
        }}
      />
    </button>
  );
}

export function Btn({
  variant = "secondary",
  onClick,
  disabled,
  children,
  style,
}: {
  variant?: "primary" | "secondary" | "danger";
  onClick?: () => void;
  disabled?: boolean;
  children: ReactNode;
  style?: CSSProperties;
}) {
  const base: CSSProperties = {
    height: 42,
    padding: "0 16px",
    borderRadius: 10,
    fontSize: 14,
    fontWeight: 600,
    cursor: disabled ? "not-allowed" : "pointer",
    fontFamily: "var(--font)",
    opacity: disabled ? 0.55 : 1,
    border: "1px solid transparent",
  };
  const variants: Record<string, CSSProperties> = {
    primary: { background: "var(--ink-900)", color: "#fff" },
    secondary: { background: "#fff", color: "var(--ink-800)", border: "1px solid var(--ink-200)" },
    danger: { background: "var(--risk-100)", color: "var(--risk-700)", border: "1px solid #f4cfcf" },
  };
  return (
    <button onClick={onClick} disabled={disabled} style={{ ...base, ...variants[variant], ...style }}>
      {children}
    </button>
  );
}

export function Banner({ kind, text }: { kind: "error" | "success" | "info"; text: string }) {
  const palette = {
    error: { bg: "var(--risk-100)", fg: "var(--risk-700)", bd: "#f4cfcf" },
    success: { bg: "#e7f6ec", fg: "#1f7a44", bd: "#bfe6cc" },
    info: { bg: "var(--surface-3)", fg: "var(--ink-600)", bd: "var(--ink-100)" },
  }[kind];
  return (
    <div
      style={{
        padding: "9px 12px",
        borderRadius: 9,
        background: palette.bg,
        color: palette.fg,
        border: `1px solid ${palette.bd}`,
        fontSize: 12.5,
        lineHeight: 1.5,
        marginBottom: 14,
      }}
    >
      {text}
    </div>
  );
}
