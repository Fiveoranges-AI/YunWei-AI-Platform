import { createContext, useContext, type ReactNode } from "react";
import { en, zh, type Copy } from "./catalog";
import { localizedHref, type Locale } from "./routing";

const LocaleContext = createContext<Locale>("en");

export function LocaleProvider({
  locale,
  children,
}: {
  locale: Locale;
  children: ReactNode;
}) {
  return (
    <LocaleContext.Provider value={locale}>{children}</LocaleContext.Provider>
  );
}

export function useLocale() {
  const locale = useContext(LocaleContext);
  return {
    locale,
    copy: (locale === "en" ? en : zh) as Copy,
    href: (path: string) => localizedHref(path, locale),
  };
}
