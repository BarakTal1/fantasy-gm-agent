import { BrowserRouter, Routes, Route } from "react-router-dom";
import { useTheme } from "./hooks/useTheme";
import { Header } from "./components/Header";
import { Nav } from "./components/Nav";
import { ChatView } from "./views/ChatView";
import { DashboardView } from "./views/DashboardView";
import { TradeView } from "./views/TradeView";
import "./styles/tokens.css";
import "./styles/app.css";

export default function App() {
  const { theme, toggle } = useTheme();
  return (
    <BrowserRouter>
      <div className="app">
        <Header theme={theme} onToggle={toggle} />
        <Nav />
        <Routes>
          <Route path="/" element={<ChatView />} />
          <Route path="/dashboard" element={<DashboardView />} />
          <Route path="/trade" element={<TradeView />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
