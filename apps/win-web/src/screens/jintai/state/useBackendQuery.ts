/**
 * Round 6: ~30 行原生 useBackendQuery hook.
 *
 * 替代 React Query / SWR (老板红线: 不引重依赖). 提供:
 *  - loading / error / data 三态
 *  - 30s stale-while-revalidate (可调 `staleMs`): 缓存命中立即返回旧数据,
 *    后台 refetch;新数据回来后 re-render
 *  - enabled gate: 用于"backend mode 才拉" 场景
 *  - manual refetch
 *
 * 不做的事: 全局缓存 (每个 hook 实例独立);并发去重 (单 tab 单页面流量小,
 * 不必要);乐观更新 (本项目只用于 GET).
 */

import { useCallback, useEffect, useRef, useState } from "react";


export type QueryState<T> = {
  data: T | null;
  loading: boolean;
  error: string | null;
  /** ms since epoch of last successful fetch; null 表示还没成功过 */
  loadedAt: number | null;
};

export type UseBackendQueryReturn<T> = QueryState<T> & {
  refetch: () => void;
};


export function useBackendQuery<T>(
  /** 稳定 key — 用作 dependency. 同 key 不同 fn 不会复用. */
  key: string,
  fetcher: () => Promise<T>,
  opts?: {
    enabled?: boolean;
    /** stale ms — 比这老才 refetch (mount 时);默认 30s */
    staleMs?: number;
  },
): UseBackendQueryReturn<T> {
  const enabled = opts?.enabled !== false;
  const staleMs = opts?.staleMs ?? 30_000;

  const [state, setState] = useState<QueryState<T>>({
    data: null, loading: false, error: null, loadedAt: null,
  });
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const runIdRef = useRef(0);

  const run = useCallback(async () => {
    if (!enabled) return;
    const myId = ++runIdRef.current;
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await fetcherRef.current();
      if (myId === runIdRef.current) {
        setState({ data, loading: false, error: null, loadedAt: Date.now() });
      }
    } catch (e) {
      if (myId === runIdRef.current) {
        const msg = e instanceof Error ? e.message : String(e);
        setState((s) => ({ ...s, loading: false, error: msg }));
      }
    }
  }, [enabled]);

  // Auto-fetch on mount / key change / enabled flip.
  useEffect(() => {
    if (!enabled) return;
    setState((s) => {
      if (s.loadedAt && Date.now() - s.loadedAt < staleMs) return s;
      // fresh enough → skip;else trigger
      void run();
      return s;
    });
    // intentionally not in deps: state.loadedAt (would loop)
  }, [enabled, key, run, staleMs]);

  return { ...state, refetch: run };
}
