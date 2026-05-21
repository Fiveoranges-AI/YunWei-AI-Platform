import { useIsDesktop } from "../../lib/breakpoints";
import { DemoStartButton } from "./GuangtianDemoTour";

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
          padding: isDesktop ? "32px 36px 34px" : "20px 18px 22px",
          display: "flex",
          flexDirection: isDesktop ? "row" : "column",
          alignItems: isDesktop ? "center" : "flex-start",
          gap: isDesktop ? 28 : 16,
        }}
      >
        {/* logo + 公司信息 — iter G16: logo 等比放大 + 圆角呼吸卡 */}
        <div style={{ display: "flex", alignItems: "center", gap: 22, flex: 1, minWidth: 0 }}>
          <div
            style={{
              flexShrink: 0,
              padding: isDesktop ? "16px 18px" : "10px 12px",
              borderRadius: 14,
              background: "linear-gradient(135deg, #FFFFFF 0%, #F8FAFC 100%)",
              border: "1px solid var(--ink-100)",
              boxShadow: "0 1px 2px rgba(15,35,64,0.04), 0 4px 14px rgba(15,35,64,0.06)",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <img
              src={logo}
              alt="光天科技"
              style={{
                width: isDesktop ? 156 : 104,
                height: "auto",
                display: "block",
              }}
            />
          </div>
          <div style={{ minWidth: 0 }}>
            <div
              style={{
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: "0.18em",
                color: "var(--guangtian-blue)",
                marginBottom: 6,
              }}
            >
              YIXING GUANGTIAN REFRACTORY · AI 库存试点
            </div>
            {/* iter G14: 标题字号对调 — 公司名大主标题 + 产品名小副标 */}
            <h1
              style={{
                margin: 0,
                lineHeight: 1.18,
                letterSpacing: "-0.01em",
                display: "flex",
                flexDirection: "column",
                gap: 3,
              }}
            >
              <span
                style={{
                  fontSize: isDesktop ? 32 : 24,
                  fontWeight: 800,
                  color: "var(--ink-900)",
                  letterSpacing: "-0.015em",
                }}
              >
                宜兴光天耐火材料
              </span>
              <span
                style={{
                  fontSize: isDesktop ? 19 : 15,
                  fontWeight: 600,
                  color: "var(--guangtian-red)",
                  letterSpacing: 0,
                }}
              >
                AI 库存管家
              </span>
            </h1>
            <p
              style={{
                margin: "8px 0 0",
                fontSize: 13.5,
                color: "var(--ink-600)",
                lineHeight: 1.55,
                maxWidth: 620,
              }}
            >
              知道有多少 · 每笔可查 · 缺货提前知道 · 老板直接问 — AI 替您管 1,000+ SKU。
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
            justifyContent: "flex-end",
          }}
        >
          {/* iter G12-B: 一键演示按钮（最醒目，紫红渐变） */}
          <div style={{ flexBasis: "100%", display: "flex", justifyContent: "flex-end", marginBottom: 2 }}>
            <DemoStartButton />
          </div>
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
