import { useEffect, useState } from "react";

const QUERIES = {
  mobile: "(max-width: 639px)",
  tablet: "(min-width: 640px) and (max-width: 1023px)",
  desktop: "(min-width: 1024px)",
} as const;

function useMatch(query: string): boolean {
  const [matches, setMatches] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.matchMedia(query).matches;
  });

  useEffect(() => {
    const mql = window.matchMedia(query);
    const onChange = (e: MediaQueryListEvent) => setMatches(e.matches);
    setMatches(mql.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, [query]);

  return matches;
}

export function useIsMobile(): boolean {
  return useMatch(QUERIES.mobile);
}

export function useIsTablet(): boolean {
  return useMatch(QUERIES.tablet);
}

export function useIsDesktop(): boolean {
  return useMatch(QUERIES.desktop);
}
