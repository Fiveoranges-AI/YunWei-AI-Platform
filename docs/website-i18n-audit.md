# Marketing website localization audit

## Baseline
- Audited Fiveoranges-AI `main`, not the older local application branch. Untracked `yunwei-parse-p0/` is unrelated and preserved.
- React 19, Vite, TypeScript, Tailwind 4, Wouter; shared navigation/footer and steel-blue/navy Sora/Manrope design system.
- Routes: `/`, `/about`, `/resources`, `/kobeli`, `/strategy-call`, `/privacy`, `/terms`, `/data-security`, `/404`; separate static `/demo.html`.
- Chinese-first copy with bilingual labels; no locale infrastructure. Contact form opens a prefilled email; no form backend. Existing analytics events, external customer portal, and illustrative demo must remain intact.
- Metadata is client-effect based; no sitemap, robots, reciprocal alternates, or static localized page content. Root Vercel configuration rewrites public routes to the SPA.

## Decisions
- English uses existing paths; Chinese uses `/zh/` plus the same paths. Explicit URLs determine language, including on reload; save explicit selection without redirecting English URLs. Localized links retain the selected language. Preserve queries and anchors on switching.
- Central typed catalogs, shared page components, context-based locale, existing Radix keyboard-accessible language menu. No framework migration or translation widget.
- Generate static HTML for each supported locale/route during build, including body content and SEO tags. Hydrate the same components in the browser. Existing Vercel filesystem routing serves generated files before the SPA fallback.
- Keep existing Chinese copy/layout except clear factual qualification. English addresses Canadian/US SME manufacturers and complements existing ERP. No new customer claims or founder endorsements.

## Risks and verification
- Existing hero percentages, use-case outcomes, named demo customers, named founder associations, and delivery promises are unverified: label visuals/demo as illustrative, qualify English capabilities, and avoid carrying unverified associations into English marketing.
- Existing Shanghai location is retained in Chinese; English describes the supplied Canadian company context. No invented office address or certification.
- Privacy/terms translations preserve the existing scope; they do not introduce new contractual promises.
- Verify all pages, form email composition, analytics, portal/demo links, direct URLs, back/forward, anchors, static metadata, keyboard menu and widths 375/390/768/1024/1440. Production deployment is excluded.

## Delivery verification
- `npm run check`, `npm run build`, and `npm test`: passing; 26 regression checks cover all 18 static pages, message completeness, internal links, route equivalence, email encoding, demo JavaScript, sitemap and extensionless route output.
- Browser: both homepages at 375, 390, 768, 1024, 1440 pixels; all 16 additional locale/page combinations at 375 pixels. No document overflow in those checks. Screenshots inspected for original Chinese desktop, localized Chinese desktop/mobile, English desktop and open dropdown, mobile drawer, form validation, and demo.
- Keyboard: language menu opens with ArrowDown, Escape closes; mobile dialog contains focus and restores it to the trigger. Native required fields use localized validation. Demo language change and skip/replay work. Switching `/zh/resources?review=1#roadmap` retains query/anchor at `/resources?review=1#roadmap`; browser back/forward returns the corresponding locales.
- Raw HTTP uncovered a Vite preview fallback: extensionless subpages initially received homepage HTML. Build now emits matching flat `.html` files as well as directory indexes; explicit root `vercel.json` marketing rewrites point to those files. Fresh browser sweep across localized subpages produced no React hydration warnings.
- Root Vercel edits only describe future marketing routing; no deployment, DNS, secrets, customer app, authentication or backend changes were made. Filesystem routes precede rewrites per [Vercel configuration documentation](https://vercel.com/docs/project-configuration/vercel-json#rewrites).
- Narrow Chinese factual adjustments: qualify the data/model-training statement pending project agreement; add illustrative-data and use-case boundaries. Existing Chinese content and sections remain, including the standalone demo.

## Limitations and release review
- The existing demo remains a scripted illustration: utility controls do not implement live ERP, arbitrary questions, export, file upload or voice. Its English UI makes these boundaries explicit.
- A language change reloads the equivalent page and does not transfer unsent form input or animation state. Preference persistence is through explicit selection plus locale-preserving links, never a saved-preference redirect.
- Unknown SPA paths show a localized noindex error view; the static fallback may return HTTP 200. This is inherited static hosting behavior, not an indexable marketing page.
- Browser review used Chromium and manual keyboard/semantic checks; no claim of complete screen-reader/WCAG certification or Safari/Firefox coverage.
- Dependency install reported existing audit findings (2 low, 3 moderate, 6 high); no dependency versions were changed. Vite reports the main minified bundle at approximately 504 kB / 153 kB gzip. These are disclosed for follow-up, not hidden by changing thresholds.
- No production release was performed. Preview-host verification of Vercel rewrites remains a reviewer check before separately authorizing production.
