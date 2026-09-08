import { useReducer, useRef } from "react";
import { chatReducer, initialState } from "./state/messages";
import { postChatStream } from "./lib/sse";
import { API_BASE } from "./lib/config";
import { useTheme } from "./hooks/useTheme";
import { Header } from "./components/Header";
import { EmptyState } from "./components/EmptyState";
import { MessageBubble } from "./components/MessageBubble";
import { Composer } from "./components/Composer";
import "./styles/tokens.css";
import "./styles/app.css";

export default function App() {
  const [state, dispatch] = useReducer(chatReducer, initialState);
  const { theme, toggle } = useTheme();
  const convId = useRef(crypto.randomUUID());
  const abort = useRef<AbortController | null>(null);

  const send = (text: string) => {
    dispatch({ type: "send", text });
    abort.current = new AbortController();
    postChatStream(API_BASE, { message: text, conversation_id: convId.current }, {
      onTool: (name) => dispatch({ type: "tool", name }),
      onToken: (t) => dispatch({ type: "token", text: t }),
      onFinal: (t) => dispatch({ type: "final", text: t }),
      onDone: () => dispatch({ type: "done" }),
      onError: (e) => dispatch({ type: "error", message: String(e) }),
    }, abort.current.signal);
  };
  const stop = () => { abort.current?.abort(); dispatch({ type: "done" }); };

  return (
    <div className="app">
      <Header theme={theme} onToggle={toggle} />
      <div className="list">
        {state.messages.length === 0
          ? <EmptyState onPick={send} />
          : state.messages.map((m, i) => <MessageBubble key={i} m={m} />)}
      </div>
      <Composer streaming={state.streaming} onSend={send} onStop={stop} />
    </div>
  );
}
