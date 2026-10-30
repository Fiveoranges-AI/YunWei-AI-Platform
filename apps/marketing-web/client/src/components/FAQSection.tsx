import { useLocale } from "@/i18n/LocaleContext";
import type { Copy } from "@/i18n/catalog";
const FAQS = (c: Copy) => [
  {
    q: c.doWeNeedToReplace,
    a: c.noStartWithAFocused,
  },
  {
    q: c.canWeStartIfOur,
    a: c.yesFirstWeReviewYour,
  },
  {
    q: c.whatHappensOnThe30,
    a: c.weDiscussYourCurrentTools,
  },
  {
    q: c.howDoYouAssessThe,
    a: c.weFocusOnPracticalTestable,
  },
];

export default function FAQSection() {
  const { copy: c } = useLocale();
  return (
    <section id="faq" className="faq-section">
      <div className="container">
        <div className="faq-header">
          <span className="section-label">
            <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
            {c.frequentlyAskedQuestions}
          </span>
          <h2>{c.questionsFromManufacturingLeaders}</h2>
        </div>

        <div className="faq-list">
          {FAQS(c).map((item) => (
            <details key={item.q} className="faq-item">
              <summary>{item.q}</summary>
              <p>{item.a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
