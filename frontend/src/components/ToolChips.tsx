import { Check } from "lucide-react";
import { toolMeta } from "../lib/toolMeta";

export function ToolChips({ tools, active }: { tools: string[]; active: boolean }) {
  return (
    <div className="chips">
      {tools.map((name, i) => {
        const { label, icon: Icon } = toolMeta(name);
        const last = i === tools.length - 1;
        const running = active && last;
        return (
          <span className="chip" key={`${name}-${i}`}>
            {running ? <Icon size={14} className="spin" /> : <Check size={14} />}
            {label}
          </span>
        );
      })}
    </div>
  );
}
