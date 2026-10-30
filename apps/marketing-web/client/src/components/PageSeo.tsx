import { useEffect } from "react";
import { pageSeo } from "@/i18n/seo";

export default function PageSeo({ path }: { path: string }) {
  useEffect(() => {
    const seo = pageSeo(path);
    document.documentElement.lang = seo.locale;
    document.title = seo.title;
    const meta = (attribute: string, name: string, content: string) => {
      let node = document.head.querySelector<HTMLMetaElement>(
        `meta[${attribute}="${name}"]`
      );
      if (!node) {
        node = document.createElement("meta");
        node.setAttribute(attribute, name);
        document.head.append(node);
      }
      node.content = content;
    };
    const link = (rel: string, href: string, language?: string) => {
      let node = document.head.querySelector<HTMLLinkElement>(
        `link[rel="${rel}"]${language ? `[hreflang="${language}"]` : ""}`
      );
      if (!node) {
        node = document.createElement("link");
        node.rel = rel;
        if (language) node.hreflang = language;
        document.head.append(node);
      }
      node.href = href;
    };
    meta("name", "description", seo.description);
    meta("name", "robots", seo.found ? "index,follow" : "noindex,follow");
    for (const [key, value] of Object.entries({
      title: seo.title,
      description: seo.description,
      url: seo.canonical,
      type: "website",
      locale: seo.locale === "en" ? "en_CA" : "zh_CN",
      "locale:alternate": seo.locale === "en" ? "zh_CN" : "en_CA",
      image: "https://fiveoranges.ai/manus-storage/logo_clean_934597e8.png",
    }))
      meta("property", `og:${key}`, value);
    link("canonical", seo.canonical);
    for (const [language, url] of Object.entries(seo.alternates))
      link("alternate", url, language);
  }, [path]);
  return null;
}
