import { ANALYTICS_EVENTS, trackEvent } from "@/utils/analytics";

const DEMO_URL = "/demo.html";
const STRATEGY_CALL_URL = "/strategy-call";

export default function DemoIntroSection() {
  return (
    <section className="demo-intro-section">
      <div className="container">
        <div className="demo-intro-panel">
          <div>
            <span className="section-label">
              <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
              演示 · AI OPERATING ASSISTANT
            </span>
            <h2>查看 AI 经营助手演示</h2>
            <p>先看一个制造业老板如何用 AI 查询订单、库存、应收和客户风险。</p>
          </div>

          <div className="demo-intro-actions">
            <a
              href={DEMO_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="demo-intro-primary"
              onClick={() => trackEvent(ANALYTICS_EVENTS.demoEntryClick, { location: "demo_intro" })}
            >
              查看 AI 经营助手演示
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M5 12h14M13 6l6 6-6 6" />
              </svg>
            </a>
            <a
              href={STRATEGY_CALL_URL}
              className="demo-intro-secondary"
              onClick={() => trackEvent(ANALYTICS_EVENTS.heroStrategyCallClick, { location: "demo_intro" })}
            >
              预约30分钟AI数字化诊断
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}
