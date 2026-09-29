import { Outlet } from "react-router-dom";
import { Header } from "./Header";
import { Nav } from "./Nav";

export function AppShell({ theme, onToggle }: { theme: string; onToggle: () => void }) {
  return (
    <div className="app">
      <Header theme={theme} onToggle={onToggle} />
      <Nav />
      <Outlet />
    </div>
  );
}
