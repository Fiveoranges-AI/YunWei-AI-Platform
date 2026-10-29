import { useLocale } from "@/i18n/LocaleContext";
import type { Copy } from "@/i18n/catalog";
import { useState } from "react";

const OPPORTUNITIES = (c: Copy) => [
  {
    cn: c.inventoryVisibility,
    en: "Inventory Visibility",
    desc: c.bringInventoryCountsLocationsShortages,
  },
  {
    cn: c.orderTracking,
    en: "Order Tracking",
    desc: c.connectOrderStatusProductionProgress,
  },
  {
    cn: c.customerIntelligence,
    en: "Customer Memory",
    desc: c.makeCustomerRecordsQuotesFollow,
  },
  {
    cn: c.workflowAutomation,
    en: "Workflow Automation",
    desc: c.identifyOpportunitiesToStreamlineApprovals,
  },
  {
    cn: c.lightweightOperationalSystems,
    en: "Lightweight Systems",
    desc: c.assessWhereFocusedCustomerInventory,
  },
  {
    cn: c.aiUseCaseDiscovery,
    en: "AI Use Case Mapping",
    desc: c.identifyWhereAiCouldSolve,
  },
];

export default function OpportunitySection() {
  const { copy: c, locale } = useLocale();
  const [expanded, setExpanded] = useState(false);

  return (
    <section id="opportunities" className="opportunity-section">
      <div className="container">
        <div className="opportunity-header">
          <span className="section-label">
            <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
            {c.opportunitiesInYourOperations}
          </span>
          <h2>{c.findWhereAiCanMake}</h2>
          <p>{c.startWithTheOperationalChallenges}</p>
        </div>

        <div className="opportunity-grid">
          {OPPORTUNITIES(c).map((item, index) => (
            <article
              key={item.en}
              className={`opportunity-card card-lift ${
                index > 2 && !expanded ? "opportunity-card-mobile-hidden" : ""
              }`}
            >
              <div className="opportunity-card-index">{String(index + 1).padStart(2, "0")}</div>
              <div>
                <h3>{item.cn}</h3>
                {locale === "zh-CN" && <div>{item.en}</div>}
              </div>
              <p>{item.desc}</p>
            </article>
          ))}
        </div>

        <button
          type="button"
          className="opportunity-expand-btn"
          onClick={() => setExpanded((value) => !value)}
          aria-expanded={expanded}
        >
          {expanded ? c.showFewerOpportunities : c.exploreMoreOpportunities}
        </button>
      </div>
    </section>
  );
}
