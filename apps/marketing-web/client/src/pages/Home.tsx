/* =============================================================
   Home — Five Oranges AI · 运帷AI
   Section order per v1.3 design:
   Navbar → Hero → Opportunities → Approach → Demo → Solutions →
   Why → UseCases → Philosophy → Founder → FAQ → CTA → Footer
   ============================================================= */

import { useEffect, useState } from "react";
import Navbar from "@/components/Navbar";
import HeroSection from "@/components/HeroSection";
import OpportunitySection from "@/components/OpportunitySection";
import SolutionsSection from "@/components/SolutionsSection";
import WhySection from "@/components/WhySection";
import ApproachSection from "@/components/ApproachSection";
import DemoIntroSection from "@/components/DemoIntroSection";
import UseCasesSection from "@/components/UseCasesSection";
import PhilosophySection from "@/components/PhilosophySection";
import FounderPreviewSection from "@/components/FounderPreviewSection";
import FAQSection from "@/components/FAQSection";
import CTASection from "@/components/CTASection";
import Footer from "@/components/Footer";

export default function Home() {
  const [showTop, setShowTop] = useState(false);

  useEffect(() => {
    const handler = () => setShowTop(window.scrollY > 600);
    window.addEventListener("scroll", handler, { passive: true });
    return () => window.removeEventListener("scroll", handler);
  }, []);

  return (
    <div className="min-h-screen bg-white">
      <Navbar />
      <main>
        <HeroSection />
        <OpportunitySection />
        <ApproachSection />
        <DemoIntroSection />
        <SolutionsSection />
        <WhySection />
        <UseCasesSection />
        <PhilosophySection />
        <FounderPreviewSection />
        <FAQSection />
        <CTASection />
      </main>
      <Footer />

      {showTop && (
        <button
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
          className="fixed bottom-8 right-8 z-50 w-11 h-11 rounded-full flex items-center justify-center shadow-lg transition-all duration-200 hover:opacity-90 hover:-translate-y-0.5"
          style={{ background: "#2D6EA8" }}
          aria-label="Scroll to top"
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path
              d="M9 14V4M5 8l4-4 4 4"
              stroke="white"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      )}
    </div>
  );
}
