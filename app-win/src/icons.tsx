import type { JSX } from "react";

type IconFn = (size?: number, color?: string) => JSX.Element;

export const I = {
  search: (s = 18, c = "currentColor") => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <circle cx="11" cy="11" r="7" stroke={c} strokeWidth="2" />
      <path d="M20 20l-3.5-3.5" stroke={c} strokeWidth="2" strokeLinecap="round" />
    </svg>
  ),
  plus: (s = 18, c = "currentColor") => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path d="M12 5v14M5 12h14" stroke={c} strokeWidth="2.2" strokeLinecap="round" />
    </svg>
  ),
  back: (s = 22, c = "currentColor") => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path d="M15 5l-7 7 7 7" stroke={c} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  chev: (s = 14, c = "currentColor") => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path d="M9 6l6 6-6 6" stroke={c} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  close: (s = 22, c = "currentColor") => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path d="M6 6l12 12M18 6L6 18" stroke={c} strokeWidth="2.2" strokeLinecap="round" />
    </svg>
  ),
  customers: (s = 22, c = "currentColor") => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <circle cx="9" cy="9" r="3.5" stroke={c} strokeWidth="1.8" />
      <path d="M3 19c.7-3 3.2-4.5 6-4.5s5.3 1.5 6 4.5" stroke={c} strokeWidth="1.8" strokeLinecap="round" />
      <circle cx="17" cy="8" r="2.5" stroke={c} strokeWidth="1.8" />
      <path d="M15.5 13.6c2.5.2 4.5 1.6 5 3.9" stroke={c} strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  ),
  upload: (s = 22, c = "currentColor") => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path d="M7 17h10M12 4v11M7.5 8.5L12 4l4.5 4.5" stroke={c} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  ask: (s = 22, c = "currentColor") => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path d="M12 2l1.6 4.2L18 8l-4.4 1.8L12 14l-1.6-4.2L6 8l4.4-1.8L12 2z" fill={c} />
      <circle cx="18.5" cy="17" r="2" fill={c} opacity="0.6" />
      <circle cx="6.5" cy="18" r="1.4" fill={c} opacity="0.4" />
    </svg>
  ),
  profile: (s = 22, c = "currentColor") => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="8" r="3.5" stroke={c} strokeWidth="1.8" />
      <path d="M5 20c1-4 4-6 7-6s6 2 7 6" stroke={c} strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  ),
  spark: (s = 16, c = "currentColor") => (
    <svg width={s} height={s} viewBox="0 0 16 16" fill={c}>
      <path d="M8 0l1.2 3.4L12.5 4.5 9.2 5.7 8 9 6.8 5.7 3.5 4.5 6.8 3.4 8 0z" />
      <path d="M13 9l.7 1.8L15.5 11.5l-1.8.7L13 14l-.7-1.8L10.5 11.5l1.8-.7L13 9z" opacity="0.7" />
    </svg>
  ),
  doc: (s = 16, c = "currentColor") => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path d="M7 3h7l4 4v13a1 1 0 01-1 1H7a1 1 0 01-1-1V4a1 1 0 011-1z" stroke={c} strokeWidth="1.6" />
      <path d="M14 3v4h4" stroke={c} strokeWidth="1.6" />
      <path d="M9 12h6M9 15h6M9 18h4" stroke={c} strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  ),
  wechat: (s = 16, c = "currentColor") => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path
        d="M14 9c3.3 0 6 2.2 6 5 0 1-.3 1.9-.9 2.7l.4 2.3-2.4-1.1c-.9.4-2 .6-3.1.6-3.3 0-6-2.2-6-5s2.7-4.5 6-4.5z"
        stroke={c}
        strokeWidth="1.5"
      />
      <path
        d="M9.5 4C5.9 4 3 6.5 3 9.5c0 1.5.7 2.9 1.9 3.9l-.5 2.4 2.6-1.3c.7.3 1.5.4 2.3.4"
        stroke={c}
        strokeWidth="1.5"
      />
    </svg>
  ),
  voice: (s = 16, c = "currentColor") => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <rect x="9" y="3" width="6" height="12" rx="3" stroke={c} strokeWidth="1.6" />
      <path d="M5 11a7 7 0 0014 0M12 18v3M9 21h6" stroke={c} strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  ),
  camera: (s = 22, c = "currentColor") => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <rect x="3" y="6" width="18" height="14" rx="2.5" stroke={c} strokeWidth="1.6" />
      <circle cx="12" cy="13" r="3.5" stroke={c} strokeWidth="1.6" />
      <path d="M9 6l1.4-2h3.2L15 6" stroke={c} strokeWidth="1.6" />
    </svg>
  ),
  cloud: (s = 22, c = "currentColor") => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path
        d="M7 18a4 4 0 010-8 6 6 0 0111.5 1.5A4 4 0 0117 18H7z"
        stroke={c}
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path
        d="M12 11v5M9.5 13.5L12 11l2.5 2.5"
        stroke={c}
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  ),
  check: (s = 16, c = "currentColor") => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path
        d="M5 12.5l4.5 4.5L19 7"
        stroke={c}
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  ),
  warn: (s = 16, c = "currentColor") => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path d="M12 3l10 18H2L12 3z" stroke={c} strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M12 10v5M12 18v.01" stroke={c} strokeWidth="2" strokeLinecap="round" />
    </svg>
  ),
  cash: (s = 16, c = "currentColor") => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <rect x="3" y="6" width="18" height="12" rx="2" stroke={c} strokeWidth="1.6" />
      <circle cx="12" cy="12" r="2.5" stroke={c} strokeWidth="1.6" />
    </svg>
  ),
  task: (s = 16, c = "currentColor") => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <rect x="4" y="4" width="16" height="16" rx="3.5" stroke={c} strokeWidth="1.6" />
      <path d="M8 12.5l3 3 5-6" stroke={c} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  hand: (s = 16, c = "currentColor") => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path d="M3 11a3 3 0 015.5-1.7L13 5.5a2 2 0 013 2.6L13.5 11" stroke={c} strokeWidth="1.6" strokeLinecap="round" />
      <path d="M3 11l1 6 5 4h6l4-3 2-7-4-2-3 1" stroke={c} strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  ),
  chat: (s = 16, c = "currentColor") => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path
        d="M4 6a2 2 0 012-2h12a2 2 0 012 2v9a2 2 0 01-2 2h-7l-4 3v-3H6a2 2 0 01-2-2V6z"
        stroke={c}
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
    </svg>
  ),
  bulb: (s = 16, c = "currentColor") => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path d="M9 18h6M10 21h4" stroke={c} strokeWidth="1.6" strokeLinecap="round" />
      <path
        d="M12 3a6 6 0 00-3.5 10.8c.5.4.8 1 .8 1.7V17h5.4v-1.5c0-.7.3-1.3.8-1.7A6 6 0 0012 3z"
        stroke={c}
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
    </svg>
  ),
  send: (s = 18, c = "currentColor") => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path
        d="M5 12l15-8-5 16-3-7-7-1z"
        stroke={c}
        strokeWidth="1.8"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  ),
  link: (s = 14, c = "currentColor") => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path
        d="M10 14a4 4 0 005 .5l3-3a4 4 0 00-5.5-5.5l-1.5 1.5M14 10a4 4 0 00-5-.5l-3 3a4 4 0 005.5 5.5l1.5-1.5"
        stroke={c}
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  ),
  bookmark: (s = 14, c = "currentColor") => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path d="M6 4h12v17l-6-4-6 4V4z" stroke={c} strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  ),
} as const satisfies Record<string, IconFn>;
