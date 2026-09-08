export interface Message {
  role: "user" | "assistant";
  content: string;
  tools?: string[];
  streaming?: boolean;
  error?: string;
}
export interface ChatState { messages: Message[]; streaming: boolean; }
export const initialState: ChatState = { messages: [], streaming: false };

export type ChatAction =
  | { type: "send"; text: string }
  | { type: "tool"; name: string }
  | { type: "token"; text: string }
  | { type: "final"; text: string }
  | { type: "done" }
  | { type: "error"; message: string };

function patchLast(s: ChatState, fn: (m: Message) => Message): ChatState {
  const messages = s.messages.slice();
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === "assistant") { messages[i] = fn(messages[i]); break; }
  }
  return { ...s, messages };
}

export function chatReducer(s: ChatState, a: ChatAction): ChatState {
  switch (a.type) {
    case "send":
      return {
        streaming: true,
        messages: [...s.messages,
          { role: "user", content: a.text },
          { role: "assistant", content: "", tools: [], streaming: true }],
      };
    case "tool":
      return patchLast(s, (m) => ({ ...m, tools: [...(m.tools ?? []), a.name] }));
    case "token":
      return patchLast(s, (m) => ({ ...m, content: m.content + a.text }));
    case "final":
      return patchLast(s, (m) => (m.content ? m : { ...m, content: a.text }));
    case "done":
      return { ...patchLast(s, (m) => ({ ...m, streaming: false })), streaming: false };
    case "error":
      return { ...patchLast(s, (m) => ({ ...m, streaming: false, error: a.message })),
               streaming: false };
    default:
      return s;
  }
}
