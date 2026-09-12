import { BrowserRouter, Routes, Route } from "react-router-dom";
import { useTheme } from "./hooks/useTheme";
import { AuthProvider } from "./state/auth";
import { Header } from "./components/Header";
import { Nav } from "./components/Nav";
import { ChatView } from "./views/ChatView";
import { MyTeamView } from "./views/MyTeamView";
import { WaiversView } from "./views/WaiversView";
import { TradeView } from "./views/TradeView";
import { LeagueView } from "./views/LeagueView";
import { SettingsView } from "./views/SettingsView";
import "./styles/tokens.css";
import "./styles/app.css";

export default function App() {
  const { theme, toggle } = useTheme();
  return (
    <AuthProvider>
      <BrowserRouter>
        <div className="app">
          <Header theme={theme} onToggle={toggle} />
          <Nav />
          <Routes>
            <Route path="/" element={<ChatView />} />
            <Route path="/my-team" element={<MyTeamView />} />
            <Route path="/waivers" element={<WaiversView />} />
            <Route path="/trade" element={<TradeView />} />
            <Route path="/league" element={<LeagueView />} />
            <Route path="/settings" element={<SettingsView theme={theme} onToggle={toggle} />} />
          </Routes>
        </div>
      </BrowserRouter>
    </AuthProvider>
  );
}
