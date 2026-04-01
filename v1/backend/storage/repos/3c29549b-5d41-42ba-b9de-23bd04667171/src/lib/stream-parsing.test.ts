import { describe, it, expect } from "vitest";

/**
 * Tests validate the SSE event parsing + handleEvent logic used by ClaudeTerminal.
 */

type EntryType = "system" | "tool-start" | "tool-result" | "text" | "code-preview" | "cost";

interface TerminalEntry {
  type: EntryType;
  content: string;
  meta?: string;
}

function extractFileName(filePath: string): string {
  return filePath.split("/").pop() || filePath;
}

function formatBytes(str: string): string {
  const bytes = new TextEncoder().encode(str).length;
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

function truncateCode(code: string, maxLines: number = 8): string {
  const lines = code.split("\n");
  if (lines.length <= maxLines) return code;
  return lines.slice(0, maxLines).join("\n") + `\n  ... (${lines.length - maxLines} more lines)`;
}

const TOOL_ICONS: Record<string, string> = {
  Write: "\u270F\uFE0F",
  Edit: "\u2702\uFE0F",
  Read: "\uD83D\uDC41",
  Bash: "\u26A1",
};

// Mirrors ClaudeTerminal's handleEvent + handleToolUse + handleToolResult
function handleEvent(event: any): TerminalEntry[] {
  const entries: TerminalEntry[] = [];

  if (event.type === "done") {
    entries.push({ type: "system", content: `Done! ${event.fileCount} file(s) generated.` });
    return entries;
  }

  if (event.type === "error") {
    entries.push({ type: "system", content: `Error: ${event.message}` });
    return entries;
  }

  if (event.type === "system" && event.subtype === "init") {
    entries.push({ type: "system", content: `Connected to ${event.model || "Claude"}` });
    return entries;
  }

  if (event.type === "assistant" && event.message) {
    if (Array.isArray(event.message.content)) {
      for (const block of event.message.content) {
        if (block.type === "tool_use") {
          entries.push(...handleToolUse(block));
        } else if (block.type === "text" && block.text?.trim()) {
          entries.push({ type: "text", content: block.text.trim() });
        }
      }
    }
    return entries;
  }

  if (event.type === "user" && event.tool_use_result) {
    entries.push(...handleToolResult(event.tool_use_result));
    return entries;
  }

  if (event.type === "result" && event.subtype === "success") {
    if (event.total_cost_usd) {
      entries.push({
        type: "cost",
        content: `$${event.total_cost_usd.toFixed(4)}`,
        meta: `${event.num_turns} turns, ${(event.duration_ms / 1000).toFixed(1)}s`,
      });
    }
    return entries;
  }

  return entries;
}

function handleToolUse(block: any): TerminalEntry[] {
  const entries: TerminalEntry[] = [];
  const name = block.name;
  const input = block.input || {};
  const icon = TOOL_ICONS[name] || "\u2699\uFE0F";

  if (name === "Write") {
    const fileName = extractFileName(input.file_path || "");
    const size = input.content ? formatBytes(input.content) : "";
    entries.push({ type: "tool-start", content: `${icon}  Write  ${fileName}`, meta: size });
    if (input.content) {
      entries.push({ type: "code-preview", content: truncateCode(input.content, 12) });
    }
  } else if (name === "Edit") {
    const fileName = extractFileName(input.file_path || "");
    entries.push({ type: "tool-start", content: `${icon}  Edit  ${fileName}` });
  } else if (name === "Read") {
    const fileName = extractFileName(input.file_path || "");
    entries.push({ type: "tool-start", content: `${icon}  Read  ${fileName}` });
  } else if (name === "Bash") {
    const cmd = input.command || input.description || "";
    entries.push({ type: "tool-start", content: `${icon}  Bash  ${cmd.slice(0, 200)}` });
  } else {
    entries.push({ type: "tool-start", content: `${icon}  ${name}  ${JSON.stringify(input).slice(0, 150)}` });
  }
  return entries;
}

function handleToolResult(r: any): TerminalEntry[] {
  const entries: TerminalEntry[] = [];
  if (r.type === "create") {
    entries.push({ type: "tool-result", content: `\u2713 Created ${extractFileName(r.filePath || "")}` });
  } else if (r.type === "edit") {
    entries.push({ type: "tool-result", content: `\u2713 Edited ${extractFileName(r.filePath || "")}` });
  } else if (r.stdout !== undefined) {
    const output = (r.stdout || r.stderr || "").trim();
    if (output) {
      entries.push({ type: "tool-result", content: `  ${output.slice(0, 300)}` });
    } else if (r.noOutputExpected) {
      entries.push({ type: "tool-result", content: "\u2713 (done)" });
    } else {
      entries.push({ type: "tool-result", content: "\u2713 (no output)" });
    }
  } else if (typeof r.content === "string") {
    entries.push({ type: "tool-result", content: `  ${r.content.slice(0, 200)}` });
  }
  return entries;
}

function parseSSEChunk(text: string): any[] {
  const events: any[] = [];
  const lines = text.split("\n");
  for (const line of lines) {
    if (!line.startsWith("data: ")) continue;
    try {
      events.push(JSON.parse(line.slice(6)));
    } catch {}
  }
  return events;
}

// --- Real Claude output samples ---

const REAL_INIT_EVENT = `{"type":"system","subtype":"init","cwd":"/tmp/site","session_id":"cf15588a","model":"claude-opus-4-6[1m]","permissionMode":"default"}`;

const REAL_ASSISTANT_TEXT = `{"type":"assistant","message":{"model":"claude-opus-4-6","id":"msg_01X","type":"message","role":"assistant","content":[{"type":"text","text":"I'll create the landing page now."}],"usage":{"input_tokens":100,"output_tokens":10}},"session_id":"abc"}`;

const REAL_ASSISTANT_WRITE = `{"type":"assistant","message":{"content":[{"type":"tool_use","id":"toolu_01","name":"Write","input":{"file_path":"/tmp/site/index.html","content":"<!DOCTYPE html>\\n<html>\\n<head><title>Test</title></head>\\n<body><h1>Hello</h1></body>\\n</html>"}}]},"session_id":"abc"}`;

const REAL_ASSISTANT_BASH = `{"type":"assistant","message":{"content":[{"type":"tool_use","id":"toolu_02","name":"Bash","input":{"command":"mkdir -p /tmp/site","description":"Create output directory"}}]},"session_id":"abc"}`;

const REAL_ASSISTANT_READ = `{"type":"assistant","message":{"content":[{"type":"tool_use","id":"toolu_03","name":"Read","input":{"file_path":"/tmp/site/_reference/inspiration-1.png"}}]},"session_id":"abc"}`;

const REAL_USER_CREATE = `{"type":"user","tool_use_result":{"type":"create","filePath":"/tmp/site/index.html","content":"<!DOCTYPE html>..."}}`;

const REAL_USER_BASH_RESULT = `{"type":"user","tool_use_result":{"stdout":"","stderr":"","noOutputExpected":true}}`;

const REAL_USER_BASH_WITH_OUTPUT = `{"type":"user","tool_use_result":{"stdout":"file1.html\\nfile2.css","stderr":""}}`;

const REAL_RESULT = `{"type":"result","subtype":"success","is_error":false,"duration_ms":20560,"num_turns":3,"result":"Created the landing page.","total_cost_usd":0.0628,"session_id":"abc"}`;

const REAL_RATE_LIMIT = `{"type":"rate_limit_event","rate_limit_info":{"status":"allowed"},"session_id":"abc"}`;

// --- Tests ---

describe("SSE line parsing", () => {
  it("parses data: prefixed lines", () => {
    const events = parseSSEChunk(`data: {"type":"system","subtype":"init","model":"claude"}\n\ndata: {"type":"done","fileCount":1}\n\n`);
    expect(events).toHaveLength(2);
  });

  it("skips invalid JSON gracefully", () => {
    const events = parseSSEChunk(`data: {"type":"broken\ndata: {"type":"done","fileCount":1}\n`);
    expect(events).toHaveLength(1);
  });
});

describe("handleEvent — system init", () => {
  it("shows model name", () => {
    const entries = handleEvent(JSON.parse(REAL_INIT_EVENT));
    expect(entries).toHaveLength(1);
    expect(entries[0]).toEqual({ type: "system", content: "Connected to claude-opus-4-6[1m]" });
  });
});

describe("handleEvent — assistant text", () => {
  it("renders Claude's reasoning text", () => {
    const entries = handleEvent(JSON.parse(REAL_ASSISTANT_TEXT));
    expect(entries).toHaveLength(1);
    expect(entries[0].type).toBe("text");
    expect(entries[0].content).toBe("I'll create the landing page now.");
  });
});

describe("handleEvent — Write tool", () => {
  it("shows file name, size, and code preview", () => {
    const entries = handleEvent(JSON.parse(REAL_ASSISTANT_WRITE));
    expect(entries.length).toBeGreaterThanOrEqual(2);
    expect(entries[0].type).toBe("tool-start");
    expect(entries[0].content).toContain("Write");
    expect(entries[0].content).toContain("index.html");
    expect(entries[0].meta).toMatch(/\d+ B/);
    expect(entries[1].type).toBe("code-preview");
    expect(entries[1].content).toContain("<!DOCTYPE html>");
  });
});

describe("handleEvent — Bash tool", () => {
  it("shows command", () => {
    const entries = handleEvent(JSON.parse(REAL_ASSISTANT_BASH));
    expect(entries).toHaveLength(1);
    expect(entries[0].type).toBe("tool-start");
    expect(entries[0].content).toContain("Bash");
    expect(entries[0].content).toContain("mkdir");
  });
});

describe("handleEvent — Read tool", () => {
  it("shows file name", () => {
    const entries = handleEvent(JSON.parse(REAL_ASSISTANT_READ));
    expect(entries).toHaveLength(1);
    expect(entries[0].type).toBe("tool-start");
    expect(entries[0].content).toContain("Read");
    expect(entries[0].content).toContain("inspiration-1.png");
  });
});

describe("handleEvent — tool results", () => {
  it("shows file creation result", () => {
    const entries = handleEvent(JSON.parse(REAL_USER_CREATE));
    expect(entries).toHaveLength(1);
    expect(entries[0].type).toBe("tool-result");
    expect(entries[0].content).toContain("Created");
    expect(entries[0].content).toContain("index.html");
  });

  it("shows bash no-output result", () => {
    const entries = handleEvent(JSON.parse(REAL_USER_BASH_RESULT));
    expect(entries).toHaveLength(1);
    expect(entries[0].type).toBe("tool-result");
    expect(entries[0].content).toContain("(done)");
  });

  it("shows bash output", () => {
    const entries = handleEvent(JSON.parse(REAL_USER_BASH_WITH_OUTPUT));
    expect(entries).toHaveLength(1);
    expect(entries[0].type).toBe("tool-result");
    expect(entries[0].content).toContain("file1.html");
  });
});

describe("handleEvent — result with cost", () => {
  it("shows cost and timing", () => {
    const entries = handleEvent(JSON.parse(REAL_RESULT));
    expect(entries).toHaveLength(1);
    expect(entries[0].type).toBe("cost");
    expect(entries[0].content).toContain("$0.0628");
    expect(entries[0].meta).toContain("3 turns");
    expect(entries[0].meta).toContain("20.6s");
  });
});

describe("handleEvent — ignored events", () => {
  it("ignores rate_limit_event", () => {
    expect(handleEvent(JSON.parse(REAL_RATE_LIMIT))).toHaveLength(0);
  });

  it("ignores unknown types", () => {
    expect(handleEvent({ type: "unknown_thing" })).toHaveLength(0);
  });
});

describe("handleEvent — done event", () => {
  it("shows file count", () => {
    const entries = handleEvent({ type: "done", fileCount: 3, files: ["a", "b", "c"], outputDir: "/tmp" });
    expect(entries).toHaveLength(1);
    expect(entries[0]).toEqual({ type: "system", content: "Done! 3 file(s) generated." });
  });
});

describe("handleEvent — error event", () => {
  it("shows error message", () => {
    const entries = handleEvent({ type: "error", message: "Process crashed" });
    expect(entries).toHaveLength(1);
    expect(entries[0]).toEqual({ type: "system", content: "Error: Process crashed" });
  });
});

describe("full pipeline — realistic Claude session", () => {
  it("produces rich terminal output from a real event sequence", () => {
    const events = [
      REAL_INIT_EVENT,
      REAL_ASSISTANT_READ,
      `{"type":"user","tool_use_result":{"content":"[image data]"}}`,
      REAL_ASSISTANT_TEXT,
      REAL_ASSISTANT_BASH,
      REAL_USER_BASH_RESULT,
      REAL_ASSISTANT_WRITE,
      REAL_USER_CREATE,
      REAL_RESULT,
    ].map((e) => JSON.parse(e));

    const allEntries: TerminalEntry[] = [];
    for (const event of events) {
      allEntries.push(...handleEvent(event));
    }

    const types = allEntries.map((e) => e.type);

    // system(Connected) -> tool-start(Read) -> tool-result(content) -> text(I'll create...) ->
    // tool-start(Bash) -> tool-result(done) -> tool-start(Write) -> code-preview -> tool-result(Created) -> cost
    expect(types).toEqual([
      "system",       // Connected
      "tool-start",   // Read inspiration
      "tool-result",  // image data
      "text",         // I'll create the landing page
      "tool-start",   // Bash mkdir
      "tool-result",  // (done)
      "tool-start",   // Write index.html
      "code-preview", // HTML content
      "tool-result",  // Created index.html
      "cost",         // $0.0628
    ]);

    // Verify specific content
    expect(allEntries[0].content).toContain("Connected");
    expect(allEntries[1].content).toContain("Read");
    expect(allEntries[1].content).toContain("inspiration-1.png");
    expect(allEntries[3].content).toBe("I'll create the landing page now.");
    expect(allEntries[6].content).toContain("Write");
    expect(allEntries[6].content).toContain("index.html");
    expect(allEntries[6].meta).toMatch(/\d+ B/);
    expect(allEntries[7].content).toContain("<!DOCTYPE html>");
    expect(allEntries[8].content).toContain("Created index.html");
    expect(allEntries[9].content).toContain("$0.0628");
  });
});

describe("truncateCode", () => {
  it("shows full code under maxLines", () => {
    expect(truncateCode("line1\nline2\nline3", 5)).toBe("line1\nline2\nline3");
  });

  it("truncates with count of remaining lines", () => {
    const code = Array.from({ length: 20 }, (_, i) => `line ${i + 1}`).join("\n");
    const result = truncateCode(code, 8);
    const lines = result.split("\n");
    expect(lines[lines.length - 1]).toContain("12 more lines");
  });
});

describe("formatBytes", () => {
  it("formats small content as bytes", () => {
    expect(formatBytes("hello")).toBe("5 B");
  });

  it("formats larger content as KB", () => {
    const big = "x".repeat(2048);
    expect(formatBytes(big)).toBe("2.0 KB");
  });
});
