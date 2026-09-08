import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message } from "../state/messages";
import { ToolChips } from "./ToolChips";

export function MessageBubble({ m }: { m: Message }) {
  if (m.role === "user")
    return <div className="row end"><div className="bubble user">{m.content}</div></div>;
  return (
    <div className="row start">
      <div className="bubble assistant">
        {m.tools && m.tools.length > 0 && (
          <ToolChips tools={m.tools} active={!!m.streaming} />
        )}
        {m.error ? (
          <div className="err">{m.error}</div>
        ) : (
          <div className="md" aria-live="polite">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
            {m.streaming && !m.content && <span className="caret" />}
          </div>
        )}
      </div>
    </div>
  );
}
