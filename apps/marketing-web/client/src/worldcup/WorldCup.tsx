/* =============================================================
   WorldCup — the /worldcup microsite router.
   Mounted from the main App's <Switch> for "/worldcup" and any
   "/worldcup/*" child path. Uses its own absolute-path <Switch>
   inside the standalone WcLayout shell, so the main site router,
   navigation, and pages are left completely untouched.
   ============================================================= */

import { Route, Switch } from "wouter";
import WcLayout from "./WcLayout";
import WcHome from "./pages/WcHome";
import WcSchedule from "./pages/WcSchedule";
import WcFanFestival from "./pages/WcFanFestival";
import WcTransportation from "./pages/WcTransportation";
import WcFamilyGuide from "./pages/WcFamilyGuide";
import WcWhereToWatch from "./pages/WcWhereToWatch";
import WcOnlineViewing from "./pages/WcOnlineViewing";
import WcBusiness from "./pages/WcBusiness";
import WcJoin from "./pages/WcJoin";
import WcNotFound from "./pages/WcNotFound";

export default function WorldCup() {
  return (
    <WcLayout>
      <Switch>
        <Route path="/worldcup" component={WcHome} />
        <Route path="/worldcup/schedule" component={WcSchedule} />
        <Route path="/worldcup/fan-festival" component={WcFanFestival} />
        <Route path="/worldcup/transportation" component={WcTransportation} />
        <Route path="/worldcup/family-guide" component={WcFamilyGuide} />
        <Route path="/worldcup/where-to-watch" component={WcWhereToWatch} />
        <Route path="/worldcup/online-viewing" component={WcOnlineViewing} />
        <Route path="/worldcup/business" component={WcBusiness} />
        <Route path="/worldcup/join" component={WcJoin} />
        <Route component={WcNotFound} />
      </Switch>
    </WcLayout>
  );
}
