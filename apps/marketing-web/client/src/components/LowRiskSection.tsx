import { useLocale } from "@/i18n/LocaleContext";
import type { Copy } from "@/i18n/catalog";
const PRINCIPLES = (c: Copy) => [
  c.complementYourExistingErpBefore,
  c.connectAiToRealOperational,
  c.validateTheBusinessNeedBefore,
];

export default function LowRiskSection() {
  const { copy: c } = useLocale();
  return (
    <section className="low-risk-section">
      <div className="container">
        <div className="low-risk-panel">
          <div>
            <span className="section-label">
              <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
              {c.aFocusedFirstStep}
            </span>
            <h2>{c.buildOnWhatAlreadyWorks}</h2>
          </div>

          <div className="low-risk-content">
            <ul>
              {PRINCIPLES(c).map((item) => (
                <li key={item}>
                  <span aria-hidden>✓</span>
                  {item}
                </li>
              ))}
            </ul>
            <div className="low-risk-flow">{c.validateAUseCaseStructure}</div>
          </div>
        </div>
      </div>
    </section>
  );
}
