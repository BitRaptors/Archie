"use client";

import { useEffect, useRef, useState } from "react";

type EntryType = "system" | "tool-start" | "tool-result" | "text" | "code-preview" | "cost";

interface TerminalEntry {
  id: number;
  type: EntryType;
  content: string;
  meta?: string; // extra info like file size, tool name icon, etc.
}

interface ClaudeTerminalProps {
  userPrompt: string;
  onComplete: (result: {
    previewUrl: string;
    fileCount: number;
    files: string[];
    outputDir: string;
    sessionId?: string;
  }) => void;
  onError: (message: string) => void;
  onFileChange?: () => void;
}

function formatBytes(str: string): string {
  const bytes = new TextEncoder().encode(str).length;
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

function extractFileName(filePath: string): string {
  return filePath.split("/").pop() || filePath;
}

function truncateCode(code: string, maxLines: number = 8): string {
  const lines = code.split("\n");
  if (lines.length <= maxLines) return code;
  return lines.slice(0, maxLines).join("\n") + `\n  ... (${lines.length - maxLines} more lines)`;
}

const TOOL_ICONS: Record<string, string> = {
  Write: "\u270F\uFE0F",   // ✏️
  Edit: "\u2702\uFE0F",    // ✂️
  Read: "\uD83D\uDC41",    // 👁
  Bash: "\u26A1",           // ⚡
  Glob: "\uD83D\uDD0D",    // 🔍
  Grep: "\uD83D\uDD0E",    // 🔎
};

export default function ClaudeTerminal({ userPrompt, onComplete, onError, onFileChange }: ClaudeTerminalProps) {
  const [entries, setEntries] = useState<TerminalEntry[]>([]);
  const [expanded, setExpanded] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const expandedScrollRef = useRef<HTMLDivElement>(null);
  const idRef = useRef(0);
  const sessionIdRef = useRef<string | undefined>(undefined);

  useEffect(() => {
    const abortController = new AbortController();
    let cancelled = false;

    async function run() {
      addEntry("system", "Starting Claude Code...");

      let res: Response;
      try {
        res = await fetch("/api/generate/stream", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ userPrompt }),
          signal: abortController.signal,
        });
      } catch (e: any) {
        if (e.name !== "AbortError") onError(e.message);
        return;
      }

      if (cancelled) return;

      if (!res.ok) {
        onError(`Stream request failed: ${res.status}`);
        return;
      }

      const reader = res.body?.getReader();
      if (!reader) {
        onError("No response body");
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done || cancelled) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const jsonStr = line.slice(6);
          try {
            const event = JSON.parse(jsonStr);
            handleEvent(event);
          } catch {
            // Not valid JSON, skip
          }
        }
      }
    }

    run();

    return () => {
      cancelled = true;
      abortController.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    expandedScrollRef.current?.scrollTo({ top: expandedScrollRef.current.scrollHeight, behavior: "smooth" });
  }, [entries]);

  function addEntry(type: EntryType, content: string, meta?: string) {
    setEntries((prev) => [...prev, { id: ++idRef.current, type, content, meta }]);
  }

  function handleEvent(event: any) {
    // Custom done event (injected by our stream route)
    if (event.type === "done") {
      addEntry("system", `Done! ${event.fileCount} file(s) generated.`);
      onComplete({
        previewUrl: event.previewUrl,
        fileCount: event.fileCount,
        files: event.files,
        outputDir: event.outputDir,
        sessionId: sessionIdRef.current,
      });
      return;
    }

    if (event.type === "error") {
      addEntry("system", `Error: ${event.message}`);
      onError(event.message);
      return;
    }

    // System init — capture session_id
    if (event.type === "system" && event.subtype === "init") {
      if (event.session_id) {
        sessionIdRef.current = event.session_id;
      }
      addEntry("system", `Connected to ${event.model || "Claude"}`);
      return;
    }

    // Assistant message — tool calls and text
    if (event.type === "assistant" && event.message) {
      if (Array.isArray(event.message.content)) {
        for (const block of event.message.content) {
          if (block.type === "tool_use") {
            handleToolUse(block);
          } else if (block.type === "text" && block.text?.trim()) {
            addEntry("text", block.text.trim());
          }
        }
      }
      return;
    }

    // Tool results from user messages
    if (event.type === "user" && event.tool_use_result) {
      handleToolResult(event.tool_use_result);
      return;
    }

    // Final result summary
    if (event.type === "result" && event.subtype === "success") {
      if (event.total_cost_usd) {
        addEntry("cost", `$${event.total_cost_usd.toFixed(4)}`, `${event.num_turns} turns, ${(event.duration_ms / 1000).toFixed(1)}s`);
      }
      return;
    }

    // Skip rate_limit_event and other unknown types silently
  }

  function handleToolUse(block: any) {
    const name = block.name;
    const input = block.input || {};
    const icon = TOOL_ICONS[name] || "\u2699\uFE0F"; // ⚙️

    if (name === "Write") {
      const fileName = extractFileName(input.file_path || "");
      const size = input.content ? formatBytes(input.content) : "";
      addEntry("tool-start", `${icon}  Write  ${fileName}`, size);
      if (input.content) {
        addEntry("code-preview", truncateCode(input.content, 12));
      }
    } else if (name === "Edit") {
      const fileName = extractFileName(input.file_path || "");
      addEntry("tool-start", `${icon}  Edit  ${fileName}`);
      if (input.old_string && input.new_string) {
        const preview = `- ${input.old_string.split("\n").slice(0, 3).join("\n- ")}\n+ ${input.new_string.split("\n").slice(0, 3).join("\n+ ")}`;
        addEntry("code-preview", truncateCode(preview, 8));
      }
    } else if (name === "Read") {
      const fileName = extractFileName(input.file_path || "");
      addEntry("tool-start", `${icon}  Read  ${fileName}`);
    } else if (name === "Bash") {
      const cmd = input.command || input.description || "";
      addEntry("tool-start", `${icon}  Bash  ${cmd.slice(0, 200)}`);
    } else {
      const summary = JSON.stringify(input).slice(0, 150);
      addEntry("tool-start", `${icon}  ${name}  ${summary}`);
    }
  }

  function handleToolResult(r: any) {
    if (r.type === "create") {
      const fileName = extractFileName(r.filePath || "");
      addEntry("tool-result", `\u2713 Created ${fileName}`);
      onFileChange?.();
    } else if (r.type === "edit") {
      const fileName = extractFileName(r.filePath || "");
      addEntry("tool-result", `\u2713 Edited ${fileName}`);
      onFileChange?.();
    } else if (r.stdout !== undefined) {
      // Bash result
      const output = (r.stdout || r.stderr || "").trim();
      if (output) {
        addEntry("tool-result", `  ${output.slice(0, 300)}`);
      } else if (r.noOutputExpected) {
        addEntry("tool-result", "\u2713 (done)");
      } else {
        addEntry("tool-result", "\u2713 (no output)");
      }
    } else if (typeof r.content === "string") {
      addEntry("tool-result", `  ${r.content.slice(0, 200)}`);
    }
  }

  const terminalContent = (ref: React.RefObject<HTMLDivElement | null>, maxH: string) => (
    <div
      ref={ref}
      className={`bg-[#0c0c0f] p-4 font-mono text-[11px] leading-[1.6] ${maxH} overflow-y-auto`}
    >
      {entries.map((entry) => (
        <div key={entry.id} className={`mb-0.5 ${entry.type === "tool-start" ? "mt-3" : ""}`}>
          {entry.type === "system" && (
            <div className="text-emerald-400 font-semibold py-0.5">{entry.content}</div>
          )}

          {entry.type === "tool-start" && (
            <div className="flex items-baseline gap-2">
              <span className="text-amber-300 font-semibold">{entry.content}</span>
              {entry.meta && (
                <span className="text-zinc-600 text-[10px]">{entry.meta}</span>
              )}
            </div>
          )}

          {entry.type === "tool-result" && (
            <div className="text-emerald-600 text-[10px] pl-4">{entry.content}</div>
          )}

          {entry.type === "text" && (
            <div className="text-zinc-400 py-1 whitespace-pre-wrap">{entry.content}</div>
          )}

          {entry.type === "code-preview" && (
            <pre className="text-zinc-600 text-[10px] leading-[1.5] pl-4 py-1 border-l-2 border-zinc-800 ml-1 max-h-[200px] overflow-hidden whitespace-pre-wrap break-all">
              {entry.content}
            </pre>
          )}

          {entry.type === "cost" && (
            <div className="flex items-center gap-3 text-zinc-600 text-[10px] pt-1 border-t border-zinc-800/50 mt-2">
              <span>Cost: {entry.content}</span>
              {entry.meta && <span>{entry.meta}</span>}
            </div>
          )}
        </div>
      ))}
      {entries.length === 0 && (
        <div className="flex items-center gap-2 text-zinc-600">
          <svg className="h-3 w-3 animate-spin" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Connecting...
        </div>
      )}
    </div>
  );

  return (
    <>
      <div className="mt-3 rounded-[var(--radius-md)] border border-[var(--border)] overflow-hidden">
        <div className="flex items-center gap-2 px-3 py-2 bg-[#15151a] border-b border-[var(--border)]">
          <div className="flex gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#ff5f57]" />
            <span className="w-2.5 h-2.5 rounded-full bg-[#febc2e]" />
            <span className="w-2.5 h-2.5 rounded-full bg-[#28c840]" />
          </div>
          <span className="text-[11px] text-zinc-500 font-mono ml-1">claude</span>
          <button
            onClick={() => setExpanded(true)}
            className="ml-auto flex h-6 w-6 items-center justify-center rounded text-zinc-600 transition-colors hover:bg-white/5 hover:text-zinc-400"
            title="Expand"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 3 21 3 21 9" />
              <polyline points="9 21 3 21 3 15" />
              <line x1="21" y1="3" x2="14" y2="10" />
              <line x1="3" y1="21" x2="10" y2="14" />
            </svg>
          </button>
        </div>
        {terminalContent(scrollRef, "max-h-80")}
      </div>

      {expanded && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-6">
          <div className="w-full max-w-5xl h-[85vh] rounded-[var(--radius-xl)] border border-[var(--border)] overflow-hidden flex flex-col bg-[#0c0c0f] shadow-[0_24px_80px_rgba(0,0,0,0.6)]">
            <div className="flex items-center gap-2 px-4 py-2.5 bg-[#15151a] border-b border-[var(--border)] shrink-0">
              <div className="flex gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-[#ff5f57]" />
                <span className="w-2.5 h-2.5 rounded-full bg-[#febc2e]" />
                <span className="w-2.5 h-2.5 rounded-full bg-[#28c840]" />
              </div>
              <span className="text-xs text-zinc-500 font-mono ml-1">claude — full log</span>
              <span className="ml-auto text-[11px] text-zinc-600 font-medium">{entries.length} entries</span>
              <button
                onClick={() => setExpanded(false)}
                className="flex h-7 w-7 items-center justify-center rounded-full text-zinc-500 transition-colors hover:bg-white/5 hover:text-zinc-300 ml-2"
                title="Close"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
            <div className="flex-1 min-h-0">
              {terminalContent(expandedScrollRef, "h-full")}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
