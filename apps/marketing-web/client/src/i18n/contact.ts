import { en, zh } from "./catalog";
import type { Locale } from "./routing";
export type ContactForm = {
  name: string;
  company: string;
  contact: string;
  challenge: string;
};

export function buildMailtoUrl(form: ContactForm, locale: Locale) {
  const c = locale === "en" ? en : zh;
  const separator = locale === "en" ? ": " : "：";
  const body = [
    c.helloFiveOrangesAiI,
    "",
    `${c.name}${separator}${form.name || c.notProvided}`,
    `${c.company}${separator}${form.company || c.notProvided}`,
    `${c.contactDetails}${separator}${form.contact || c.notProvided}`,
    "",
    c.mainChallenge,
    form.challenge || c.notProvided,
  ].join("\n");
  return `mailto:contact@fiveoranges.ai?subject=${encodeURIComponent(c.bookA30MinuteDiscovery2)}&body=${encodeURIComponent(body)}`;
}
