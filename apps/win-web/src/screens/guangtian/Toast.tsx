import { useGT, type ToastLevel } from "./state";

const LEVEL_STYLE: Record<
  ToastLevel,
  { bg: string; border: string; color: string; icon: string }
> = {
  ok:   { bg: "linear-gradient(135deg, #ECFDF5 0%, #D1FAE5 100%)", border: "1px solid #6EE7B7", color: "#065F46", icon: "✓" },
  warn: { bg: "linear-gradient(135deg, #FFFBEB 0%, #FEF3C7 100%)", border: "1px solid #FCD34D", color: "#92400E", icon: "⚠" },
  err:  { bg: "linear-gradient(135deg, #FEF2F2 0%, #FEE2E2 100%)", border: "1px solid #FCA5A5", color: "#991B1B", icon: "✗" },
  info: { bg: "linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%)", border: "1px solid #93C5FD", color: "#1E3A8A", icon: "ℹ" },
  ai:   { bg: "linear-gradient(135deg, #FAF8FF 0%, #F1E8FF 100%)", border: "1px solid #C4B5FD", color: "#5B21B6", icon: "✦" },
};

export function ToastContainer() {
  const { toasts, dismissToast } = useGT();
  return (
    <div
      aria-live="polite"
      style={{
        position: "fixed",
        top: 20,
        right: 20,
        zIndex: 10000,
        display: "flex",
        flexDirection: "column",
        gap: 10,
        pointerEvents: "none",
      }}
    >
      {toasts.map((t) => {
        const s = LEVEL_STYLE[t.level];
        return (
          <div
            key={t.id}
            onClick={() => dismissToast(t.id)}
            style={{
              pointerEvents: "auto",
              maxWidth: 420,
              padding: "11px 14px",
              background: s.bg,
              border: s.border,
              color: s.color,
              borderRadius: 10,
              fontSize: 12.5,
              fontWeight: 600,
              lineHeight: 1.5,
              fontFamily: "var(--font)",
              boxShadow: "0 8px 24px rgba(11,18,32,0.14), 0 2px 6px rgba(11,18,32,0.08)",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 9,
              animation: "gt-toast-in 220ms cubic-bezier(0.32, 0.72, 0.24, 1.0)",
            }}
          >
            <span
              style={{
                flexShrink: 0,
                width: 22,
                height: 22,
                borderRadius: 6,
                background: "rgba(255,255,255,0.7)",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 13,
                fontWeight: 800,
              }}
            >
              {s.icon}
            </span>
            <span>{t.message}</span>
          </div>
        );
      })}
      <style>{`
        @keyframes gt-toast-in {
          from { opacity: 0; transform: translateX(20px); }
          to { opacity: 1; transform: translateX(0); }
        }
        @keyframes gt-spin {
          from { transform: rotate(0); }
          to { transform: rotate(360deg); }
        }
        @keyframes gt-pulse-urgent {
          0%, 100% { box-shadow: 0 0 0 2px rgba(195,38,41,0.18), 0 1px 2px rgba(11, 34, 50, 0.04), 0 4px 14px rgba(11, 34, 50, 0.05); }
          50%      { box-shadow: 0 0 0 4px rgba(195,38,41,0.30), 0 1px 2px rgba(11, 34, 50, 0.04), 0 4px 14px rgba(11, 34, 50, 0.05); }
        }
      `}</style>
    </div>
  );
}

// 行内 loading spinner (供 AI 生成 / 提交按钮使用)
export function Spinner({ size = 14, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <span
      aria-label="加载中"
      style={{
        display: "inline-block",
        width: size,
        height: size,
        border: `2px solid ${color}`,
        borderRightColor: "transparent",
        borderRadius: "50%",
        animation: "gt-spin 0.7s linear infinite",
      }}
    />
  );
}
