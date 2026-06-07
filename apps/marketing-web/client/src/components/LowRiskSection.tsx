const PRINCIPLES = [
  "不建议一开始就上大而全 ERP",
  "不把 AI 做成单纯聊天机器人",
  "不为了做系统而做系统，而是先判断业务场景是否值得投入",
];

export default function LowRiskSection() {
  return (
    <section className="low-risk-section">
      <div className="container">
        <div className="low-risk-panel">
          <div>
            <span className="section-label">
              <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
              低风险落地 · LOW-RISK START
            </span>
            <h2>我们不从复杂系统开始</h2>
          </div>

          <div className="low-risk-content">
            <ul>
              {PRINCIPLES.map((item) => (
                <li key={item}>
                  <span aria-hidden>✓</span>
                  {item}
                </li>
              ))}
            </ul>
            <div className="low-risk-flow">小场景验证 → 数据结构化 → AI工作流 → 分阶段扩展</div>
          </div>
        </div>
      </div>
    </section>
  );
}
