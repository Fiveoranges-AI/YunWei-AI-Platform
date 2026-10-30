import { useLocale } from "@/i18n/LocaleContext";
import { ANALYTICS_EVENTS, trackEvent } from "@/utils/analytics";

const DEMO_URL = "/demo.html";
const STRATEGY_CALL_URL = "/strategy-call";

export default function DemoIntroSection() {
  const { copy: c, href: localize } = useLocale();
  return (
    <section className="demo-intro-section">
      <div className="container">
        <div className="demo-intro-panel">
          <div>
            <span className="section-label">
              <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
              {c.illustrativePlatformDemo}
            </span>
            <h2>{c.exploreThePlatform}</h2>
            <p>{c.exploreAnIllustrativeOrderManagement}</p>
          </div>

          <div className="demo-intro-actions">
            <a
              href={localize(DEMO_URL)}
              target="_blank"
              rel="noopener noreferrer"
              className="demo-intro-primary"
              onClick={() => trackEvent(ANALYTICS_EVENTS.demoEntryClick, { location: "demo_intro" })}
            >
              {c.exploreThePlatform}<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M5 12h14M13 6l6 6-6 6" />
              </svg>
            </a>
            <a
              href={localize(STRATEGY_CALL_URL)}
              className="demo-intro-secondary"
              onClick={() => trackEvent(ANALYTICS_EVENTS.heroStrategyCallClick, { location: "demo_intro" })}
            >
              {c.bookA30MinuteDiscovery2}
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}
