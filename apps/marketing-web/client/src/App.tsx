import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import NotFound from "@/pages/NotFound";
import { Route, Switch, Router as WouterRouter, useLocation } from "wouter";
import { LocaleProvider } from "./i18n/LocaleContext";
import { localeFromPath, unlocalizedPath } from "./i18n/routing";
import PageSeo from "./components/PageSeo";
import ErrorBoundary from "./components/ErrorBoundary";
import { ThemeProvider } from "./contexts/ThemeContext";
import About from "./pages/About";
import Home from "./pages/Home";
import Kobeli from "./pages/Kobeli";
import Resources from "./pages/Resources";
import StrategyCall from "./pages/StrategyCall";
import { DataSecurityPage, PrivacyPage, TermsPage } from "./pages/TrustPages";

function Router() {
  const [path] = useLocation();
  return (
    <LocaleProvider locale={localeFromPath(path)}>
      <ErrorBoundary locale={localeFromPath(path)}>
        <PageSeo path={path} />
        <Switch location={unlocalizedPath(path).replace(/\/$/, "") || "/"}>
          <Route path={"/"} component={Home} />
          <Route path={"/about"} component={About} />
          <Route path={"/resources"} component={Resources} />
          <Route path={"/kobeli"} component={Kobeli} />
          <Route path={"/strategy-call"} component={StrategyCall} />
          <Route path={"/privacy"} component={PrivacyPage} />
          <Route path={"/terms"} component={TermsPage} />
          <Route path={"/data-security"} component={DataSecurityPage} />
          <Route path={"/404"} component={NotFound} />
          <Route component={NotFound} />
        </Switch>
      </ErrorBoundary>
    </LocaleProvider>
  );
}

function App({ path }: { path?: string }) {
  return (
    <WouterRouter ssrPath={path}>
      <ThemeProvider defaultTheme="light">
        <TooltipProvider>
          <Toaster />
          <Router />
        </TooltipProvider>
      </ThemeProvider>
    </WouterRouter>
  );
}

export default App;
