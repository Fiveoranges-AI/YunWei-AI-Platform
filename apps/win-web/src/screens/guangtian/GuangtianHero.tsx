import { useIsDesktop } from "../../lib/breakpoints";

type Props = {
  onGoSku: () => void;
  onGoInbound: () => void;
  onGoAsk: () => void;
};

export function GuangtianHero({ onGoSku, onGoInbound, onGoAsk }: Props) {
  const isDesktop = useIsDesktop();
  const logo = `${import.meta.env.BASE_URL}guangtian-logo.png`;
  return (
    <section
      style={{
        position: "relative",
        marginBottom: 20,
        borderRadius: 16,
        overflow: "hidden",
        background:
          "linear-gradient(135deg, #FCFBFA 0%, #F4F5FA 60%, #EBEEF7 100%)",
        border: "1px solid var(--ink-100)",
        boxShadow: "var(--shadow-card-soft)",
      }}
    >
      {/* 顶部红蓝渐变装饰条 */}
      <div
        aria-hidden
        style={{
          height: 3,
          background:
            "linear-gradient(90deg, var(--guangtian-red) 0%, var(--guangtian-red) 50%, var(--guangtian-blue) 50%, var(--guangtian-blue) 100%)",
        }}
      />
      <div
        style={{
          padding: isDesktop ? "24px 28px 26px" : "18px 18px 20px",
          display: "flex",
          flexDirection: isDesktop ? "row" : "column",
          alignItems: isDesktop ? "center" : "flex-start",
          gap: isDesktop ? 24 : 14,
        }}
      >
        {/* logo + 公司信息 */}
        <div style={{ display: "flex", alignItems: "center", gap: 14, flex: 1, minWidth: 0 }}>
          <img
            src={logo}
            alt="光天科技"
            style={{
              width: isDesktop ? 84 : 64,
              height: "auto",
              flexShrink: 0,
              filter: "drop-shadow(0 2px 6px rgba(15,35,64,0.10))",
            }}
          />
          <div style={{ minWidth: 0 }}>
            <div
              style={{
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: "0.18em",
                color: "var(--guangtian-blue)",
                marginBottom: 5,
              }}
            >
              YIXING GUANGTIAN REFRACTORY · AI 库存试点
            </div>
            <h1
              style={{
                margin: 0,
                fontSize: isDesktop ? 22 : 19,
                fontWeight: 800,
                color: "var(--ink-900)",
                lineHeight: 1.25,
                letterSpacing: "-0.005em",
              }}
            >
              宜兴光天耐火材料 · <span style={{ color: "var(--guangtian-red)" }}>AI 库存管家</span>
            </h1>
            <p
              style={{
                margin: "6px 0 0",
                fontSize: 13,
                color: "var(--ink-600)",
                lineHeight: 1.55,
                maxWidth: 660,
              }}
            >
              轻量仓库管理 · 生产出入库风险预警 · 用 AI 把 1,000+ SKU 管清楚，
              告别 Excel 和人工记忆。
            </p>
          </div>
        </div>
        {/* CTA */}
        <div
          style={{
            display: "flex",
            gap: 8,
            flexWrap: "wrap",
            flexShrink: 0,
          }}
        >
          <button onClick={onGoInbound} style={ctaPrimary}>
            ⬇ 模拟入库登记
          </button>
          <button onClick={onGoSku} style={ctaGhost}>
            查看 SKU 档案
          </button>
          <button onClick={onGoAsk} style={ctaAccent}>
            问问 AI 库存管家
          </button>
        </div>
      </div>
    </section>
  );
}

const ctaPrimary: React.CSSProperties = {
  padding: "10px 16px",
  fontSize: 13,
  fontWeight: 700,
  borderRadius: 10,
  border: "none",
  background: "var(--guangtian-red)",
  color: "#fff",
  cursor: "pointer",
  fontFamily: "var(--font)",
  boxShadow: "0 4px 12px rgba(217,32,32,0.22)",
};

const ctaGhost: React.CSSProperties = {
  padding: "10px 14px",
  fontSize: 13,
  fontWeight: 600,
  borderRadius: 10,
  border: "1px solid var(--ink-200)",
  background: "#fff",
  color: "var(--ink-700)",
  cursor: "pointer",
  fontFamily: "var(--font)",
};

const ctaAccent: React.CSSProperties = {
  padding: "10px 14px",
  fontSize: 13,
  fontWeight: 600,
  borderRadius: 10,
  border: "none",
  background: "var(--guangtian-blue)",
  color: "#fff",
  cursor: "pointer",
  fontFamily: "var(--font)",
  boxShadow: "0 4px 12px rgba(26,63,142,0.22)",
};
