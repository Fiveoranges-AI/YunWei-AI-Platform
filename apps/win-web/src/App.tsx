import { useEffect, useState } from "react";
import { AppShell } from "./components/AppShell";
import { HomeScreen } from "./screens/Home";
import { CustomerListScreen } from "./screens/CustomerList";
import { CustomerDetailScreen } from "./screens/CustomerDetail";
import { UploadScreen } from "./screens/Upload";
import { InboxScreen } from "./screens/Inbox";
import { ReviewScreen } from "./screens/Review";
import { AskScreen } from "./screens/Ask";
import { ProfileScreen } from "./screens/Profile";
import { JintaiDemoPage } from "./screens/jintai/JintaiDemoPage";
import { ConfirmDemoScreen } from "./screens/ConfirmDemo";

export type ScreenName =
  | "home"
  | "list"
  | "detail"
  | "upload"
  | "inbox"
  | "review"
  | "ask"
  | "profile"
  | "jintai"
  | "confirmDemo";
export type TabName = "home" | "customers" | "inbox" | "upload" | "ask" | "profile" | "jintai";

export type ScreenStackEntry = {
  name: ScreenName;
  params?: Record<string, string>;
};

export type GoFn = (name: ScreenName, params?: Record<string, string>) => void;

const SCREEN_TO_TAB: Record<ScreenName, TabName | undefined> = {
  home: "home",
  list: "customers",
  detail: undefined,
  upload: "upload",
  inbox: "inbox",
  review: undefined,
  ask: "ask",
  profile: "profile",
  jintai: "jintai",
  confirmDemo: undefined,
};

const TAB_TO_SCREEN: Record<TabName, ScreenName> = {
  home: "home",
  customers: "list",
  inbox: "inbox",
  upload: "upload",
  ask: "ask",
  profile: "profile",
  jintai: "jintai",
};

function readInitialScreen(): ScreenStackEntry {
  // Allow `?screen=confirmDemo` for the P0 task ③ demo page so it can be
  // exercised without adding a permanent tab. Anything else falls back to
  // the home capture desk.
  if (typeof window === "undefined") return { name: "list" };
  const params = new URLSearchParams(window.location.search);
  const name = params.get("screen");
  if (name === "confirmDemo") return { name: "confirmDemo" };
  return { name: "home" };
}

export function App() {
  const initial = readInitialScreen();
  const [activeTab, setActiveTab] = useState<TabName>(
    SCREEN_TO_TAB[initial.name] ?? "home",
  );
  const [stack, setStack] = useState<ScreenStackEntry[]>([initial]);

  useEffect(() => {
    function onPop() {
      const next = readInitialScreen();
      setStack([next]);
      setActiveTab(SCREEN_TO_TAB[next.name] ?? "home");
    }
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const go: GoFn = (name, params = {}) => {
    const tab = SCREEN_TO_TAB[name];
    if (tab) {
      setActiveTab(tab);
      setStack([{ name, params }]);
    } else {
      setStack((s) => [...s, { name, params }]);
    }
  };

  const setTab = (tab: TabName) => {
    setActiveTab(tab);
    setStack([{ name: TAB_TO_SCREEN[tab] }]);
  };

  const current = stack[stack.length - 1];

  return (
    <AppShell activeTab={activeTab} onTabChange={setTab} currentScreen={current.name} onAdd={() => go("upload")}>
      <CurrentScreen entry={current} go={go} />
    </AppShell>
  );
}

function CurrentScreen({ entry, go }: { entry: ScreenStackEntry; go: GoFn }) {
  switch (entry.name) {
    case "home":
      return <HomeScreen go={go} />;
    case "list":
      return <CustomerListScreen go={go} />;
    case "detail":
      return <CustomerDetailScreen go={go} params={entry.params ?? {}} />;
    case "upload":
      return <UploadScreen go={go} />;
    case "inbox":
      return <InboxScreen go={go} params={entry.params ?? {}} />;
    case "review":
      return <ReviewScreen go={go} params={entry.params ?? {}} />;
    case "ask":
      return <AskScreen go={go} params={entry.params ?? {}} />;
    case "profile":
      return <ProfileScreen go={go} />;
    case "jintai":
      return <JintaiDemoPage />;
    case "confirmDemo":
      return <ConfirmDemoScreen go={go} />;
  }
}
