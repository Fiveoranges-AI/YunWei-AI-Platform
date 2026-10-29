import { buildMailtoUrl } from "@/i18n/contact";
import { useLocale } from "@/i18n/LocaleContext";
import type { Copy } from "@/i18n/catalog";
import Footer from "@/components/Footer";
import Navbar from "@/components/Navbar";
import { ANALYTICS_EVENTS, trackEvent } from "@/utils/analytics";
import { useState } from "react";

const EMAIL = "contact@fiveoranges.ai";

const DIAGNOSIS_ITEMS = (c: Copy) => [
  c.theOperationalChallengesTakingThe,
  c.howYouCurrentlyManageInventory,
  c.aFocusedUseCaseSuitable,
  c.howYourExistingSystemsCould,
];

const BEST_FIT = (c: Copy) => [
  c.youManageInventoryOrdersOr2,
  c.youWantToImproveBusiness,
  c.aLargeErpProjectFeels,
  c.youWantToExploreAi,
  c.youAreLeadingASuccession2,
  c.youAreExpandingIntoNew2,
];

const OUTCOMES = (c: Copy) => [
  c.weAssessWhetherAiOr2,
  c.ifThereIsAFit,
  c.ifThereIsNoClear,
];

export default function StrategyCall() {
  const { copy: c, href: localize, locale } = useLocale();
  const [form, setForm] = useState({ name: "", company: "", contact: "", challenge: "" });
  const [draftOpened, setDraftOpened] = useState(false);
  const [formStarted, setFormStarted] = useState(false);

  const handleFormStart = () => {
    if (formStarted) return;
    setFormStarted(true);
    trackEvent(ANALYTICS_EVENTS.strategyFormStart, { location: "strategy_call_form" });
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    trackEvent(ANALYTICS_EVENTS.strategyFormSubmit, { location: "strategy_call_form" });
    window.location.href = buildMailtoUrl(form, locale);
    setDraftOpened(true);
  };

  return (
    <div className="min-h-screen bg-white">
      <Navbar />
      <main className="strategy-page">
        <section className="strategy-hero-section">
          <div className="container">
            <div className="strategy-hero-grid">
              <div>
                <span className="section-label">
                  <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
                  {c.discoveryCall}
                </span>
                <h1>{c.bookA30MinuteDiscovery2}</h1>
                <p className="strategy-lead">
                  {c.letSReviewYourInventory}
                </p>
                <p className="strategy-support">
                  {c.theAimIsToDefine}
                </p>

                <div className="strategy-actions">
                  <a
                    href={localize("#strategy-form")}
                    className="strategy-primary-button"
                    onClick={() => trackEvent(ANALYTICS_EVENTS.strategyFormStart, { location: "strategy_hero" })}
                  >
                    {c.shareYourDetails}<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M5 12h14M13 6l6 6-6 6" />
                    </svg>
                  </a>
                  <a
                    href={localize("/demo.html")}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="strategy-secondary-button"
                    onClick={() => trackEvent(ANALYTICS_EVENTS.demoEntryClick, { location: "strategy_hero" })}
                  >
                    {c.exploreThePlatform}
                  </a>
                </div>
              </div>

              <aside className="strategy-card">
                <div className="strategy-card-kicker">{c.message30Minutes}</div>
                <h2>{c.whatWillWeDiscuss}</h2>
                <ul>
                  {DIAGNOSIS_ITEMS(c).map((item) => (
                    <li key={item}>
                      <span aria-hidden>✓</span>
                      {item}
                    </li>
                  ))}
                </ul>
                <div className="strategy-card-footer">
                  <strong>{EMAIL}</strong>
                  <span>{c.fiveOrangesAi}</span>
                </div>
              </aside>
            </div>
          </div>
        </section>

        <section className="strategy-submit-section">
          <div className="container">
            <div className="strategy-submit-grid">
              <article className="strategy-outcome-card">
                <span className="section-label">
                  <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
                  {c.nextSteps}
                </span>
                <h2>{c.whatHappensAfterYouReach}</h2>
                <ol>
                  {OUTCOMES(c).map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ol>
              </article>

              <form id="strategy-form" className="strategy-form-card" onFocus={handleFormStart} onSubmit={handleSubmit}>
                <h2>{c.yourDetails}</h2>
                <div className="strategy-form-row">
                  <label>
                    {c.name}<input
                      value={form.name}
                      onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                      placeholder={c.yourName}
                    />
                  </label>
                  <label>
                    {c.company}<input
                      value={form.company}
                      onChange={(event) => setForm((current) => ({ ...current, company: event.target.value }))}
                      placeholder={c.companyName}
                    />
                  </label>
                </div>
                <label>
                  {c.contactDetails}<input
                    value={form.contact}
                    onChange={(event) => setForm((current) => ({ ...current, contact: event.target.value }))}
                    placeholder={c.emailOrPhoneNumber}
                    onInvalid={(event) => event.currentTarget.setCustomValidity(c.formRequired)}
                    onInput={(event) => event.currentTarget.setCustomValidity("")}
                    required
                  />
                </label>
                <label>
                  {c.yourMainOperationalChallenge}<textarea
                    value={form.challenge}
                    onChange={(event) => setForm((current) => ({ ...current, challenge: event.target.value }))}
                    placeholder={c.forExampleInaccurateInventoryUnclear}
                    rows={4}
                    onInvalid={(event) => event.currentTarget.setCustomValidity(c.formRequired)}
                    onInput={(event) => event.currentTarget.setCustomValidity("")}
                    required
                  />
                </label>
                <p className="strategy-wechat-note">
                  {c.thisFormOpensYourEmail}
                </p>
                <button type="submit" className="strategy-primary-button">
                  {c.openEmailDraft}
                </button>
                {draftOpened && <p role="status">{c.emailDraftNotice}</p>}
              </form>
            </div>
          </div>
        </section>

        <section className="strategy-fit-section">
          <div className="container">
            <div className="strategy-section-header">
              <span className="section-label">
                <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
                {c.whoWeWorkWith}
              </span>
              <h2>{c.aConversationForManufacturingOwners}</h2>
            </div>

            <div className="strategy-fit-grid">
              {BEST_FIT(c).map((item) => (
                <article key={item} className="strategy-fit-card">
                  <span aria-hidden>✓</span>
                  <p>{item}</p>
                </article>
              ))}
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}
