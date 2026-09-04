import { useState } from "react";
import { askChat, FinReconApiError } from "../api";
import type { ChatMessage } from "../types";

interface Props {
  jobId: string;
  recordId?: string;
}

export function ChatPanel({ jobId, recordId }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send() {
    const text = input.trim();
    if (!text || sending) return;
    setInput("");
    setError(null);
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setSending(true);
    try {
      const response = await askChat(jobId, text, recordId, sessionId);
      setSessionId(response.session_id);
      setMessages((prev) => [...prev, { role: "assistant", content: response.reply }]);
    } catch (err) {
      setError(err instanceof FinReconApiError ? err.message : "Chat request failed.");
    } finally {
      setSending(false);
    }
  }

  function reset() {
    setMessages([]);
    setSessionId(undefined);
    setError(null);
  }

  return (
    <div className="chat-panel">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <strong style={{ fontSize: 13 }}>Ask FinRecon</strong>
        {messages.length > 0 && (
          <button className="ghost-button" style={{ padding: "2px 10px", fontSize: 12 }} onClick={reset}>
            Reset
          </button>
        )}
      </div>

      <div className="chat-messages" style={{ marginTop: 10 }}>
        {messages.length === 0 && (
          <p className="empty-state" style={{ padding: "8px 0" }}>
            {recordId ? `Ask why ${recordId} was flagged.` : "Ask about this report — e.g. which records have the largest variance."}
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat-bubble ${m.role}`}>
            {m.content}
          </div>
        ))}
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="chat-input-row">
        <input
          value={input}
          placeholder="Ask a question..."
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
        />
        <button className="primary-button" disabled={sending || !input.trim()} onClick={send}>
          {sending ? "..." : "Send"}
        </button>
      </div>
    </div>
  );
}
