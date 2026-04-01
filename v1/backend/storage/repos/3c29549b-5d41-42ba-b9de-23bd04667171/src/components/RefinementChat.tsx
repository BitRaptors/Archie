"use client";

import { useState, useRef, useEffect } from "react";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface RefinementChatProps {
  siteDir: string;
  sessionId?: string;
  provider: string;
  messages: ChatMessage[];
  onMessage: (msg: ChatMessage) => void;
  onFileChange: () => void;
}

export default function RefinementChat({
  siteDir,
  sessionId,
  provider,
  messages,
  onMessage,
  onFileChange,
}: RefinementChatProps) {
  const [input, setInput] = useState("");
  const [refining, setRefining] = useState(false);
  const [streamText, setStreamText] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, streamText]);

  const send = async () => {
    const message = input.trim();
    if (!message || refining) return;

    setInput("");
    onMessage({ role: "user", content: message });
    setRefining(true);
    setStreamText("");

    try {
      const res = await fetch("/api/generate/refine", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ siteDir, sessionId, message, provider }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({ error: "Refinement failed" }));
        onMessage({ role: "assistant", content: `Error: ${data.error || "Refinement failed"}` });
        setRefining(false);
        return;
      }

      if (provider === "claude" && res.headers.get("Content-Type")?.includes("text/event-stream")) {
        const reader = res.body?.getReader();
        if (!reader) {
          onMessage({ role: "assistant", content: "Error: No response body" });
          setRefining(false);
          return;
        }

        const decoder = new TextDecoder();
        let buffer = "";
        let fullResponse = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            try {
              const event = JSON.parse(line.slice(6));

              if (event.type === "assistant" && event.message?.content) {
                for (const block of event.message.content) {
                  if (block.type === "text" && block.text?.trim()) {
                    fullResponse += block.text;
                    setStreamText(fullResponse);
                  }
                }
              }

              if (event.type === "user" && event.tool_use_result) {
                const r = event.tool_use_result;
                if (r.type === "create" || r.type === "edit") {
                  onFileChange();
                }
              }

              if (event.type === "done") {
                onFileChange();
              }
            } catch {
              // skip
            }
          }
        }

        onMessage({ role: "assistant", content: fullResponse || "Changes applied." });
      } else {
        const data = await res.json();
        onMessage({ role: "assistant", content: data.message || "Changes applied." });
        onFileChange();
      }
    } catch (e: any) {
      onMessage({ role: "assistant", content: `Error: ${e.message}` });
    } finally {
      setRefining(false);
      setStreamText("");
    }
  };

  return (
    <div className="flex flex-col rounded-[var(--radius-lg)] bg-[var(--surface)] shadow-[0_1px_3px_rgba(0,0,0,0.2)] overflow-hidden">
      <div className="flex items-center gap-2 px-4 pt-3 pb-2">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-[var(--text-secondary)]">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
        <h3 className="text-sm font-bold text-[var(--text)]">Refine</h3>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 pb-2 space-y-2.5 max-h-60 min-h-[60px]">
        {messages.length === 0 && !refining && (
          <p className="text-xs text-[var(--text-muted)] py-2">Ask the AI to tweak your site...</p>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`text-xs leading-relaxed ${
              msg.role === "user" ? "text-[var(--text)]" : "text-[var(--text-secondary)]"
            }`}
          >
            <span className={`font-bold ${msg.role === "user" ? "text-[var(--accent)]" : "text-[var(--text-muted)]"}`}>
              {msg.role === "user" ? "You" : "AI"}
            </span>{" "}
            {msg.content}
          </div>
        ))}
        {refining && streamText && (
          <div className="text-xs leading-relaxed text-[var(--text-secondary)]">
            <span className="font-bold text-[var(--text-muted)]">AI</span> {streamText}
          </div>
        )}
        {refining && !streamText && (
          <div className="flex items-center gap-2 text-xs text-[var(--text-muted)] py-1">
            <svg className="h-3 w-3 animate-spin" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Refining...
          </div>
        )}
      </div>

      {/* Input */}
      <div className="flex gap-2 border-t border-[var(--border)] p-3">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
          placeholder="Make the CTA button red..."
          className="flex-1 rounded-full border border-[var(--border)] bg-[var(--bg)] px-4 py-2 text-sm placeholder:text-[var(--text-muted)]"
          disabled={refining}
        />
        <button
          onClick={send}
          disabled={refining || !input.trim()}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--accent)] text-white shadow-[0_2px_8px_var(--accent-glow)] transition-all hover:bg-[var(--accent-hover)] hover:scale-105 disabled:opacity-30 disabled:shadow-none disabled:hover:scale-100"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        </button>
      </div>
    </div>
  );
}
