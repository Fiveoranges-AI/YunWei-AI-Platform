import { useState } from "react";
import { AppShell } from "./components/AppShell";
import { CustomerListScreen } from "./screens/CustomerList";
import { CustomerDetailScreen } from "./screens/CustomerDetail";
import { UploadScreen } from "./screens/Upload";
import { InboxScreen } from "./screens/Inbox";
import { ReviewScreen } from "./screens/Review";
import { AskScreen } from "./screens/Ask";
import { ProfileScreen } from "./screens/Profile";
import { JintaiDemoPage } from "./screens/jintai/JintaiDemoPage";

export type ScreenName =
  | "list"
  | "detail"
  | "upload"
  | "inbox"
  | "review"
  | "ask"
  | "profile"
  | "jintai";
export type TabName = "customers" | "inbox" | "upload" | "ask" | "profile" | "jintai";

export type ScreenStackEntry = {
  name: ScreenName;
  params?: Record<string, string>;
};

export type GoFn = (name: ScreenName, params?: Record<string, string>) => void;

const SCREEN_TO_TAB: Record<ScreenName, TabName | undefined> = {
  list: "customers",
  detail: undefined,
  upload: "upload",
  inbox: "inbox",
  review: undefined,
  ask: "ask",
  profile: "profile",
  jintai: "jintai",
};

const TAB_TO_SCREEN: Record<TabName, ScreenName> = {
  customers: "list",
  inbox: "inbox",
  upload: "upload",
  ask: "ask",
  profile: "profile",
  jintai: "jintai",
};

export function App() {
  const [activeTab, setActiveTab] = useState<TabName>("customers");
  const [stack, setStack] = useState<ScreenStackEntry[]>([{ name: "list" }]);

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
  }
}
