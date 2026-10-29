import { Check, ChevronDown } from "lucide-react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useLocale } from "@/i18n/LocaleContext";
import { localizedHref, type Locale } from "@/i18n/routing";

export default function LanguageSwitcher() {
  const { locale } = useLocale();
  const label = locale === "en" ? "Choose language" : "选择语言";
  const switchTo = (next: Locale) => {
    try {
      localStorage.setItem("fiveoranges.locale.v1", next);
    } catch {
      /* URLs work when storage is unavailable. */
    }
    window.location.assign(
      localizedHref(window.location.pathname, next) +
        window.location.search +
        window.location.hash
    );
  };
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger className="language-trigger" aria-label={label}>
        {locale === "en" ? "EN" : "中文"}
        <ChevronDown size={14} aria-hidden />
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          className="language-menu"
          align="end"
          sideOffset={8}
          aria-label={label}
        >
          {(
            [
              ["en", "English"],
              ["zh-CN", "简体中文"],
            ] as const
          ).map(([value, name]) => (
            <DropdownMenu.Item
              aria-current={locale === value ? "true" : undefined}
              key={value}
              className="language-option"
              lang={value}
              onSelect={() => switchTo(value)}
              aria-label={name}
            >
              <span>{name}</span>
              {locale === value && (
                <Check
                  size={15}
                  aria-label={locale === "en" ? "Selected" : "已选择"}
                />
              )}
            </DropdownMenu.Item>
          ))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
