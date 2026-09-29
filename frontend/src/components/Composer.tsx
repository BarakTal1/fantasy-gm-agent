import { useState } from "react";
import { Send, Square } from "lucide-react";

export function Composer({ streaming, onSend, onStop }: {
  streaming: boolean; onSend: (t: string) => void; onStop: () => void;
}) {
  const [value, setValue] = useState("");
  const submit = () => { const t = value.trim(); if (t) { onSend(t); setValue(""); } };
  return (
    <form className="composer" onSubmit={(e) => { e.preventDefault(); submit(); }}>
      <textarea
        rows={1} value={value} placeholder="Ask about your team…"
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
        }}
        aria-label="Message"
      />
      {streaming ? (
        <button type="button" className="icon-btn stop" onClick={onStop} aria-label="Stop">
          <Square size={18} />
        </button>
      ) : (
        <button type="submit" className="icon-btn send" aria-label="Send">
          <Send size={18} />
        </button>
      )}
    </form>
  );
}
