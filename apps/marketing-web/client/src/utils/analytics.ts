export const ANALYTICS_EVENTS = {
  heroDemoClick: "hero_demo_click",
  heroStrategyCallClick: "hero_strategy_call_click",
  demoEntryClick: "demo_entry_click",
  strategyFormStart: "strategy_form_start",
  strategyFormSubmit: "strategy_form_submit",
  dataSecurityClick: "data_security_click",
} as const;

export type AnalyticsEventName = (typeof ANALYTICS_EVENTS)[keyof typeof ANALYTICS_EVENTS];

declare global {
  interface Window {
    dataLayer?: Array<Record<string, unknown>>;
    gtag?: (command: "event", eventName: string, params?: Record<string, unknown>) => void;
    clarity?: (command: "event", eventName: string) => void;
  }
}

export function trackEvent(eventName: AnalyticsEventName, params: Record<string, unknown> = {}) {
  if (typeof window === "undefined") return;

  window.dataLayer?.push({ event: eventName, ...params });
  window.gtag?.("event", eventName, params);
  window.clarity?.("event", eventName);
}
