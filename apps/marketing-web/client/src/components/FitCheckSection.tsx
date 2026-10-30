import { useLocale } from "@/i18n/LocaleContext";
import type { Copy } from "@/i18n/catalog";
import { ANALYTICS_EVENTS, trackEvent } from "@/utils/analytics";

const CHECKLIST = (c: Copy) => [
  c.youManageInventoryOrdersOr,
  c.youRelyOnManualUpdates,
  c.yourErpIsDifficultFor,
  c.customerInformationIsScatteredAcross,
  c.youWantToUseAi,
  c.youArePlanningASuccession,
];

export default function FitCheckSection() {
  const { copy: c, href: localize } = useLocale();
  return (
    <section className="fit-check-section">
      <div className="container">
        <div className="fit-check-panel">
          <div className="fit-check-copy">
            <span className="section-label">
              <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
              {c.isThisAFit}
            </span>
            <h2>{c.aPracticalStartingPointFor}</h2>
            <p>{c.ifTwoOrMoreOf}</p>
            <a
              href={localize("/strategy-call")}
              className="fit-check-cta"
              onClick={() => trackEvent(ANALYTICS_EVENTS.heroStrategyCallClick, { location: "fit_check" })}
            >
              {c.bookA30MinuteDiscovery2}
            </a>
          </div>

          <div className="fit-check-list">
            {CHECKLIST(c).map((item) => (
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
              <h3>{c.clearBoundariesForBusinessData}</h3>
              <p>
                {c.beforeAPilotWeAgree}
              </p>
              <a
                href={localize("/data-security")}
                onClick={() => trackEvent(ANALYTICS_EVENTS.dataSecurityClick, { location: "fit_check" })}
              >
                {c.readOurDataSecurityPrinciples}
              </a>
            </div>
          </article>
        </div>
      </div>
    </section>
  );
}
