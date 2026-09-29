import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useTheme } from "./hooks/useTheme";
import { AuthProvider } from "./state/auth";
import { AppShell } from "./components/AppShell";
import { LandingView } from "./views/LandingView";
import { LoginView } from "./views/LoginView";
import { ChatView } from "./views/ChatView";
import { MyTeamView } from "./views/MyTeamView";
import { WaiversView } from "./views/WaiversView";
import { TradeView } from "./views/TradeView";
import { LeagueView } from "./views/LeagueView";
import { SettingsView } from "./views/SettingsView";
import "./styles/tokens.css";
import "./styles/app.css";
import "./styles/landing.css";

export default function App() {
  const { theme, toggle } = useTheme();
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingView theme={theme} onToggle={toggle} />} />
          <Route path="/login" element={<LoginView theme={theme} onToggle={toggle} />} />
          <Route path="/app" element={<AppShell theme={theme} onToggle={toggle} />}>
            <Route index element={<ChatView />} />
            <Route path="my-team" element={<MyTeamView />} />
            <Route path="waivers" element={<WaiversView />} />
            <Route path="trade" element={<TradeView />} />
            <Route path="league" element={<LeagueView />} />
            <Route path="settings" element={<SettingsView theme={theme} onToggle={toggle} />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
