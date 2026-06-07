import { useEffect } from "react";

type SeoOptions = {
  title: string;
  description: string;
  canonical: string;
  keywords?: string;
  ogType?: string;
};

export function usePageSeo({ title, description, canonical, keywords, ogType = "website" }: SeoOptions) {
  useEffect(() => {
    const previousTitle = document.title;
    document.title = title;

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

    let canonicalTag = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    const previousCanonical = canonicalTag?.getAttribute("href");
    if (!canonicalTag) {
      canonicalTag = document.createElement("link");
      canonicalTag.setAttribute("rel", "canonical");
      document.head.appendChild(canonicalTag);
    }
    canonicalTag.setAttribute("href", canonical);

    const cleanup = [
      upsertMeta("name", "description", description),
      upsertMeta("property", "og:title", title),
      upsertMeta("property", "og:description", description),
      upsertMeta("property", "og:url", canonical),
      upsertMeta("property", "og:type", ogType),
      upsertMeta("name", "twitter:title", title),
      upsertMeta("name", "twitter:description", description),
    ];

    if (keywords) cleanup.push(upsertMeta("name", "keywords", keywords));

    return () => {
      document.title = previousTitle;
      cleanup.forEach((fn) => fn());
      if (previousCanonical === undefined) canonicalTag?.remove();
      else if (previousCanonical === null) canonicalTag?.removeAttribute("href");
      else canonicalTag?.setAttribute("href", previousCanonical);
    };
  }, [canonical, description, keywords, ogType, title]);
}
