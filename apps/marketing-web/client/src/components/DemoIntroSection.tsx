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
              先看演示 · LIVE DEMO
            </span>
            <h2>先看一个 AI 如何读懂订单、库存和经营数据。</h2>
            <p>
              演示不是炫技页面，而是让企业主快速判断：如果把真实业务数据接进来，AI 能先帮你看清哪些问题。
            </p>
          </div>

          <div className="demo-intro-actions">
            <a href={DEMO_URL} target="_blank" rel="noopener noreferrer" className="demo-intro-primary">
              查看演示
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M5 12h14M13 6l6 6-6 6" />
              </svg>
            </a>
            <a href={STRATEGY_CALL_URL} className="demo-intro-secondary">
              预约30分钟AI数字化诊断
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}
