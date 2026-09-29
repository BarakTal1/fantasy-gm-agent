import { ClipboardList, Search, TrendingUp, CalendarDays, Settings, Loader,
         type LucideIcon } from "lucide-react";

const MAP: Record<string, { label: string; icon: LucideIcon }> = {
  get_my_roster: { label: "Reading your roster", icon: ClipboardList },
  get_free_agents: { label: "Scanning the waiver wire", icon: Search },
  get_trends: { label: "Analyzing recent form", icon: TrendingUp },
  get_weekly_schedule: { label: "Counting games this week", icon: CalendarDays },
  get_league_settings: { label: "Checking league settings", icon: Settings },
};

export function toolMeta(name: string) {
  return MAP[name] ?? { label: "Working…", icon: Loader };
}
