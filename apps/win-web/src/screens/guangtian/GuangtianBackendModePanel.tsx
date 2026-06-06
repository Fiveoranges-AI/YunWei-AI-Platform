/**
 * 光天 backend-mode 控制面板 (右下角浮窗).
 *
 * mock ↔ backend 切换 + /health 状态 + 真实写入演示 (一键真实出库 → 扣库 →
 * 触发缺货预警 → 生成补产建议), 让 demo 在不依赖文件上传的情况下也能展示
 * 完整的 "真实写入→风险→补产" 闭环. 仅 inspect (?inspect=1) 或 backend 模式展开.
 */

import { useEffect, useState } from "react";
import {
  generateReplenishments, getHealth, listSkus, postOutbound,
  type HealthOut,
} from "../../api/guangtian-backend";
import type { BackendMode } from "./backendMode";

export function GuangtianBackendModePanel({
  mode, onSetMode,
}: { mode: BackendMode; onSetMode: (m: BackendMode) => void }) {
  const [open, setOpen] = useState(mode === "backend");
  const [health, setHealth] = useState<HealthOut | null>(null);
  const [healthErr, setHealthErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<string[]>([]);

  useEffect(() => {
    if (mode !== "backend") return;
    let alive = true;
    getHealth()
      .then((h) => { if (alive) { setHealth(h); setHealthErr(null); } })
      .catch((e) => { if (alive) setHealthErr(e instanceof Error ? e.message : String(e)); });
    return () => { alive = false; };
  }, [mode]);

  const runWriteDemo = async () => {
    setBusy(true);
    const lines: string[] = [];
    try {
      const skus = await listSkus();
      const al90 = skus.find((s) => s.code === "JT-GZB-AL90") ?? skus.find((s) => Number(s.last_balance) > 0);
      if (!al90) throw new Error("无可出库 SKU");
      const bal = Number(al90.last_balance);
      lines.push(`① 出库 ${al90.code} 全部 ${bal} ${al90.unit}…`);
      setLog([...lines]);
      const out = await postOutbound({ sku_id: al90.id, quantity: bal, customer: "常州新材科技", order_no: "SO-20260519-003" });
      lines.push(`② 余额 ${Number(out.balance_before)} → ${Number(out.balance_after)}${out.alert_id ? "，✓ 触发缺货预警" : ""}`);
      setLog([...lines]);
      const gen = await generateReplenishments();
      lines.push(`③ AI 补产建议生成 ${gen.created.length} 条（去 AI 补产建议页查看）`);
      setLog([...lines]);
      lines.push("完成 — 切到「缺货预警 / AI 补产建议」tab 看 overlay 已更新");
      setLog([...lines]);
    } catch (e) {
      lines.push(`✗ ${e instanceof Error ? e.message : String(e)}`);
      setLog([...lines]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ position: "fixed", right: 16, bottom: 16, zIndex: 60, fontFamily: "var(--font)" }}>
      {!open ? (
        <button
          onClick={() => setOpen(true)}
          style={{
            padding: "8px 14px", borderRadius: 20, border: "1px solid var(--ink-200)",
            background: mode === "backend" ? "var(--guangtian-blue, #1A3F8E)" : "var(--surface-1)",
            color: mode === "backend" ? "#fff" : "var(--ink-700)", fontSize: 12.5, fontWeight: 700,
            cursor: "pointer", boxShadow: "var(--shadow-card-soft, 0 2px 8px rgba(0,0,0,0.12))",
          }}
        >
          {mode === "backend" ? "● 真后端模式" : "○ mock 模式"}
        </button>
      ) : (
        <div
          style={{
            width: 320, padding: 16, borderRadius: 14, background: "var(--surface-1)",
            border: "1px solid var(--ink-200)", boxShadow: "0 8px 28px rgba(0,0,0,0.18)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", marginBottom: 10 }}>
            <span style={{ fontSize: 13, fontWeight: 800, color: "var(--ink-900)" }}>Backend Reality Check</span>
            <button onClick={() => setOpen(false)} style={{ marginLeft: "auto", border: "none", background: "none", cursor: "pointer", color: "var(--ink-400)", fontSize: 16 }}>×</button>
          </div>

          <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
            {(["mock", "backend"] as BackendMode[]).map((m) => (
              <button
                key={m}
                onClick={() => onSetMode(m)}
                style={{
                  flex: 1, padding: "7px 0", borderRadius: 8, fontSize: 12, fontWeight: 700, cursor: "pointer",
                  border: "1px solid " + (mode === m ? "var(--guangtian-blue, #1A3F8E)" : "var(--ink-200)"),
                  background: mode === m ? "var(--guangtian-blue, #1A3F8E)" : "transparent",
                  color: mode === m ? "#fff" : "var(--ink-700)",
                }}
              >
                {m === "mock" ? "Mock (默认)" : "真后端"}
              </button>
            ))}
          </div>

          {mode === "backend" ? (
            <>
              <div style={{ fontSize: 11.5, marginBottom: 10, color: "var(--ink-600)", lineHeight: 1.6 }}>
                {healthErr ? (
                  <span style={{ color: "var(--guangtian-red, #D92020)" }}>⚠ /health 未连通: {healthErr}<br/>启动: <code>bash scripts/guangtian/start-demo.sh</code></span>
                ) : health ? (
                  <>✓ <b>{health.enterprise_id}</b> · {health.db}<br/>各 tab 顶部已挂实时数据 overlay。F5 刷新数字保持 = SQLite 已持久化。</>
                ) : "连接中…"}
              </div>
              <button
                onClick={runWriteDemo}
                disabled={busy || !!healthErr}
                style={{
                  width: "100%", padding: "9px 0", borderRadius: 9, fontSize: 12.5, fontWeight: 700,
                  border: "none", cursor: busy ? "wait" : "pointer",
                  background: "var(--guangtian-red, #D92020)", color: "#fff", opacity: busy || healthErr ? 0.6 : 1,
                }}
              >
                {busy ? "执行中…" : "▶ 真实写入演示: 出库 → 缺货预警 → 补产建议"}
              </button>
              {log.length > 0 && (
                <div style={{ marginTop: 10, fontSize: 11, color: "var(--ink-700)", lineHeight: 1.7, background: "var(--surface-2)", borderRadius: 8, padding: 10 }}>
                  {log.map((l, i) => <div key={i}>{l}</div>)}
                </div>
              )}
            </>
          ) : (
            <div style={{ fontSize: 11.5, color: "var(--ink-600)", lineHeight: 1.6 }}>
              当前为前端 mock。切到「真后端」后各 tab 顶部会显示来自
              <code> /api/win/guangtian/* </code>的真实数据（需先跑
              <code> dev_guangtian_backend</code>）。
            </div>
          )}
        </div>
      )}
    </div>
  );
}
