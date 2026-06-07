import { ANALYTICS_EVENTS, trackEvent } from "@/utils/analytics";

const CHECKLIST = [
  "还在用 Excel 管库存、订单或客户",
  "老板每天靠人汇报才能知道进度",
  "ERP 太复杂，员工不愿意用",
  "客户资料分散在微信和个人电脑里",
  "想用 AI，但不知道第一个场景从哪里开始",
  "正在做接班、出海或管理规范化",
];

export default function FitCheckSection() {
  return (
    <section className="fit-check-section">
      <div className="container">
        <div className="fit-check-panel">
          <div className="fit-check-copy">
            <span className="section-label">
              <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
              适合沟通 · FIT CHECK
            </span>
            <h2>你的企业适合先聊一次吗？</h2>
            <p>如果你的企业符合以下任意 2 条，就值得预约一次 AI 数字化诊断。</p>
            <a
              href="/strategy-call"
              className="fit-check-cta"
              onClick={() => trackEvent(ANALYTICS_EVENTS.heroStrategyCallClick, { location: "fit_check" })}
            >
              预约30分钟AI数字化诊断
            </a>
          </div>

          <div className="fit-check-list">
            {CHECKLIST.map((item) => (
              <div key={item} className="fit-check-item">
                <span aria-hidden>✓</span>
                <p>{item}</p>
              </div>
            ))}
          </div>

          <article className="data-trust-card">
            <div className="data-trust-icon" aria-hidden>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" />
                <path d="M9 12l2 2 4-4" />
              </svg>
            </div>
            <div>
              <h3>企业数据边界清晰</h3>
              <p>
                客户数据不会用于训练公共模型。正式项目可根据客户要求设计权限、脱敏、审计和部署边界。
              </p>
              <a
                href="/data-security"
                onClick={() => trackEvent(ANALYTICS_EVENTS.dataSecurityClick, { location: "fit_check" })}
              >
                查看数据安全说明
              </a>
            </div>
          </article>
        </div>
      </div>
    </section>
  );
}
