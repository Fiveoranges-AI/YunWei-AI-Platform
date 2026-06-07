/* =============================================================
   Founder credibility block (homepage) — 由具备企业级数字化交付经验
   的架构师主导. A concise trust teaser that links to the full /kobeli
   founder page. Positioned as founder/architect credibility, not a CV.
   ============================================================= */

import { ArrowRight } from "lucide-react";

const CREDENTIALS = [
  "10 年以上企业级数字化交付",
  "Microsoft Dynamics 365 · Power Platform",
  "CRM · ERP · 流程自动化",
  "制造业轻量化 AI 系统",
];

export default function FounderBlock() {
  return (
    <section className="founder-block bg-section-blue" style={{ padding: "7rem 0" }}>
      <div className="container">
        <div className="founder-block-grid">
          {/* Left — copy + CTA */}
          <div>
            <span className="section-label">
              <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
              创始人 · FOUNDER
            </span>
            <h2 className="founder-block-title">由具备企业级数字化交付经验的架构师主导</h2>
            <p className="founder-block-copy">
              Five Oranges AI / 运帷AI 由 <strong>Kobe Li</strong> 创立。Kobe 拥有 10
              年以上 Microsoft Dynamics 365、Power Platform、CRM、ERP、流程自动化和数字化转型项目经验，并将企业级交付经验转化为更适合中小制造企业的轻量化
              AI 系统方法。
            </p>
            <a href="/kobeli" className="founder-block-cta hover-lift">
              查看创始人背景
              <ArrowRight size={16} strokeWidth={2.2} aria-hidden />
            </a>
          </div>

          {/* Right — credential card */}
          <div className="founder-block-card">
            <div className="founder-block-card-head">
              <span className="founder-block-avatar" aria-hidden>
                KL
              </span>
              <span className="founder-block-id">
                <strong>Kobe Li</strong>
                <span>创始人 · AI 转型架构师</span>
              </span>
            </div>
            <ul className="founder-block-creds">
              {CREDENTIALS.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
