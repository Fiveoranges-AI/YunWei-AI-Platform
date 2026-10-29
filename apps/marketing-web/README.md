# Five Oranges AI marketing website

## Local review

```sh
npm ci
npm run check
npm run build
npm test
npm run preview -- --host 127.0.0.1 --port 4173
```

English is served at `/`; Chinese at `/zh/`. Both have equivalent `/about`,
`/resources`, `/kobeli`, `/strategy-call`, `/privacy`, `/terms`, `/data-security`,
and `/demo.html` routes. Existing unprefixed links remain valid and now select
English. Unknown routes show a localized, non-indexable not-found page.

## Localization

- `client/src/i18n/catalog.ts` owns typed messages; English must contain every
  Chinese message key. Shared components use `useLocale()`.
- URL prefixes determine locale on every load. Explicit selection is saved in
  `fiveoranges.locale.v1`; subsequent internal links retain the selected prefix.
  Saved preferences deliberately never redirect explicit English or Chinese URLs.
- Switching preserves the pathname, query, and anchor. It performs a page load,
  so unsent form input and demo animation state are not transferred.
- The standalone demo is generated from `templates/demo.html` and its message
  catalog. Tokens are resolved at build time, not by runtime DOM translation.
- `npm run build` builds the client and a temporary server rendering bundle, then
  emits 18 static localized pages, two localized 404s, sitemap and robots files.
  Only `dist/public/` is publishable; `dist/server/` is build tooling.
- `PageSeo` maintains metadata after client routing; the same route metadata is
  embedded in static HTML by the build. No runtime server or secrets are needed.

## Content and integrations

The strategy form validates required fields and opens an encoded email draft.
Users must send that draft themselves. It does not book a meeting or send data to
an API. Existing analytics event names and customer portal destinations are kept.
Demos and dashboard metrics are illustrations, not customer results. The English
site describes capabilities as discovery-dependent and omits unverified named
founder associations and numerical tenure claims.

## Review and release

See `../../docs/website-i18n-audit.md` for the baseline, decisions and QA results.
No production release is authorized by this change. Review the PR and any preview
before separately approving a merge or production deployment.
