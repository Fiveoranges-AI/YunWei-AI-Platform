/* =============================================================
   LegalPage — shared shell for /privacy, /terms, /data-security
   Navbar + branded header + prose content + Footer, with per-page
   SEO (title / description / keywords / canonical / og).
   ============================================================= */

import { useEffect } from "react";
import type { ReactNode } from "react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";

export type LegalSeo = { title: string; description: string; keywords?: string };

function useLegalSeo(seo: LegalSeo, path: string) {
  useEffect(() => {
    const url = `https://fiveoranges.ai${path}`;
    const previousTitle = document.title;
    document.title = seo.title;

    const upsertMeta = (attribute: "name" | "property", key: string, content: string) => {
      let tag = document.head.querySelector<HTMLMetaElement>(`meta[${attribute}="${key}"]`);
      if (!tag) {
        tag = document.createElement("meta");
        tag.setAttribute(attribute, key);
        document.head.appendChild(tag);
      }
      const previous = tag.getAttribute("content");
      tag.setAttribute("content", content);
      return () => {
        if (previous === null) tag?.remove();
        else tag?.setAttribute("content", previous);
      };
    };

    let canonical = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    const previousCanonical = canonical?.getAttribute("href");
    if (!canonical) {
      canonical = document.createElement("link");
      canonical.setAttribute("rel", "canonical");
      document.head.appendChild(canonical);
    }
    canonical.setAttribute("href", url);

    const cleanup = [
      upsertMeta("name", "description", seo.description),
      ...(seo.keywords ? [upsertMeta("name", "keywords", seo.keywords)] : []),
      upsertMeta("property", "og:title", seo.title),
      upsertMeta("property", "og:description", seo.description),
      upsertMeta("property", "og:url", url),
      upsertMeta("property", "og:type", "website"),
    ];

    window.scrollTo(0, 0);

    return () => {
      document.title = previousTitle;
      cleanup.forEach((fn) => fn());
      if (previousCanonical === undefined) canonical?.remove();
      else if (previousCanonical === null) canonical?.removeAttribute("href");
      else canonical?.setAttribute("href", previousCanonical);
    };
  }, [seo, path]);
}

export default function LegalPage({
  seo,
  path,
  label,
  title,
  subtitle,
  updated,
  children,
}: {
  seo: LegalSeo;
  path: string;
  label: string;
  title: string;
  subtitle?: string;
  updated?: string;
  children: ReactNode;
}) {
  useLegalSeo(seo, path);

  return (
    <div className="min-h-screen bg-white">
      <Navbar />
      <main>
        <section className="legal-hero">
          <div className="container">
            <span className="section-label">
              <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
              {label}
            </span>
            <h1 className="legal-title">{title}</h1>
            {subtitle && <p className="legal-subtitle">{subtitle}</p>}
            {updated && <p className="legal-updated">最后更新：{updated}</p>}
          </div>
        </section>

        <section className="legal-body">
          <div className="container">
            <div className="legal-prose">{children}</div>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}
