import { describe, it, expect, afterEach } from "vitest";
import { spawn } from "child_process";
import fs from "fs";
import path from "path";
import os from "os";
import { buildClaudePrompt } from "./generate";

function makeTmpDir(): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "claude-test-"));
  return dir;
}

function cleanup(dir: string) {
  try {
    fs.rmSync(dir, { recursive: true, force: true });
  } catch {}
}

const TINY_INPUT = {
  pins: [],
  repoContent: null,
  userPrompt:
    "Create the absolute simplest page possible: a single index.html with a centered heading that says 'Hello World' and a blue background. Nothing else. No CSS file, no JS, just one HTML file with inline styles.",
  presets: [],
};

/**
 * Calls Claude Code via spawn with stdin, same as generateWithClaude does.
 * Returns { stdout, stderr, code }.
 */
function callClaude(
  prompt: string,
  cwd: string,
  args: string[]
): Promise<{ stdout: string; stderr: string; code: number | null }> {
  return new Promise((resolve, reject) => {
    const localClaude = path.join(process.cwd(), "node_modules", ".bin", "claude");
    const claudeBin = fs.existsSync(localClaude) ? localClaude : "claude";

    const proc = spawn(claudeBin, args, {
      cwd,
      stdio: ["pipe", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";
    proc.stdout.on("data", (chunk: Buffer) => {
      stdout += chunk.toString();
    });
    proc.stderr.on("data", (chunk: Buffer) => {
      stderr += chunk.toString();
    });
    proc.on("close", (code) => {
      resolve({ stdout, stderr, code });
    });
    proc.on("error", reject);

    proc.stdin.write(prompt);
    proc.stdin.end();
  });
}

describe("Claude Code integration", () => {
  let outputDir: string;

  afterEach(() => {
    if (outputDir) cleanup(outputDir);
  });

  it(
    "generates a site via --print --output-format json (non-streaming path)",
    async () => {
      outputDir = makeTmpDir();
      const prompt = buildClaudePrompt(TINY_INPUT, outputDir);

      const { stdout, stderr, code } = await callClaude(prompt, outputDir, [
        "--print",
        "--output-format",
        "json",
        "--max-turns",
        "5",
        "--allowedTools",
        "Write,Edit,Bash",
        "-",
      ]);

      console.log("--- NON-STREAMING ---");
      console.log("exit code:", code);
      console.log("stderr:", stderr.slice(0, 500));
      console.log("stdout (first 500):", stdout.slice(0, 500));

      expect(code).toBe(0);

      // Claude should have written files into outputDir
      const files = fs.readdirSync(outputDir);
      console.log("files in outputDir:", files);
      expect(files.length).toBeGreaterThan(0);
      expect(files).toContain("index.html");

      const html = fs.readFileSync(path.join(outputDir, "index.html"), "utf-8");
      expect(html.toLowerCase()).toContain("<h1");
      expect(html.toLowerCase()).toContain("hello");
    },
    120_000
  );

  it(
    "generates a site via --print --verbose --output-format stream-json (streaming path)",
    async () => {
      outputDir = makeTmpDir();
      const prompt = buildClaudePrompt(TINY_INPUT, outputDir);

      const { stdout, stderr, code } = await callClaude(prompt, outputDir, [
        "--print",
        "--verbose",
        "--output-format",
        "stream-json",
        "--max-turns",
        "5",
        "--allowedTools",
        "Write,Edit,Bash",
        "-",
      ]);

      console.log("--- STREAMING ---");
      console.log("exit code:", code);
      console.log("stderr:", stderr.slice(0, 500));

      // Parse the stream-json lines
      const lines = stdout.split("\n").filter((l) => l.trim());
      const events = lines.map((l) => {
        try {
          return JSON.parse(l);
        } catch {
          return null;
        }
      }).filter(Boolean);

      console.log("event count:", events.length);
      console.log(
        "event types:",
        [...new Set(events.map((e: any) => e.type))]
      );

      expect(code).toBe(0);
      expect(events.length).toBeGreaterThan(0);

      // Should have an init event
      const initEvent = events.find((e: any) => e.type === "system" && e.subtype === "init");
      expect(initEvent).toBeTruthy();

      // Should have a result event
      const resultEvent = events.find((e: any) => e.type === "result");
      expect(resultEvent).toBeTruthy();
      expect(resultEvent.is_error).toBe(false);

      // Claude should have written files into outputDir
      const files = fs.readdirSync(outputDir);
      console.log("files in outputDir:", files);
      expect(files.length).toBeGreaterThan(0);
      expect(files).toContain("index.html");

      const html = fs.readFileSync(path.join(outputDir, "index.html"), "utf-8");
      expect(html.toLowerCase()).toContain("<h1");
    },
    120_000
  );
});
