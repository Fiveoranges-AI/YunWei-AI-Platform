export default function FounderPreviewSection() {
  return (
    <section className="founder-preview-section">
      <div className="container">
        <div className="founder-preview-panel">
          <div className="founder-preview-avatar" aria-hidden>
            KL
          </div>

          <div className="founder-preview-copy">
            <span className="section-label">
              <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
              创始人主导 · FOUNDER-LED
            </span>
            <h2>由 Kobe Li 主导，连接企业系统经验与 AI 落地能力。</h2>
            <p>
              由 Kobe Li 主导，具备10年以上 Dynamics 365 / Power Platform / CRM / ERP
              与企业级数字化交付经验。
            </p>
          </div>

          <a href="/kobeli" className="founder-preview-link">
            查看创始人背景
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M5 12h14M13 6l6 6-6 6" />
            </svg>
          </a>
        </div>
      </div>
    </section>
  );
}
