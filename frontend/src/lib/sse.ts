type Handler = (event: string, data: any) => void;

/** Feed raw SSE text chunks; buffers partial frames and dispatches complete ones. */
export function parseSSE(onEvent: Handler) {
  let buf = "";
  return (chunk: string) => {
    buf += chunk;
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) !== -1) {
      const frame = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      let event = "message";
      const dataLines: string[] = [];
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      }
      if (dataLines.length) {
        let data: any = dataLines.join("\n");
        try { data = JSON.parse(data); } catch { /* keep string */ }
        onEvent(event, data);
      }
    }
  };
}

export interface ChatCallbacks {
  onTool?: (name: string) => void;
  onToken?: (text: string) => void;
  onFinal?: (text: string) => void;
  onDone?: () => void;
  onError?: (err: unknown) => void;
}

/** POST to /chat and stream SSE events (browser EventSource cannot POST). */
export async function postChatStream(
  baseUrl: string,
  body: { message: string; conversation_id: string },
  cb: ChatCallbacks,
  signal?: AbortSignal,
) {
  try {
    const res = await fetch(`${baseUrl}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
    if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
    const feed = parseSSE((ev, data) => {
      if (ev === "tool") cb.onTool?.(data.name);
      else if (ev === "token") cb.onToken?.(data.text);
      else if (ev === "final") cb.onFinal?.(data.text);
      else if (ev === "done") cb.onDone?.();
    });
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      feed(dec.decode(value, { stream: true }));
    }
    cb.onDone?.();
  } catch (err) {
    if ((err as Error).name !== "AbortError") cb.onError?.(err);
  }
}
