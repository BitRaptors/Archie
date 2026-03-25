import { NextResponse } from "next/server";
import { execFile } from "child_process";
import { promisify } from "util";
import path from "path";
import fs from "fs";

const execFileAsync = promisify(execFile);

export async function GET() {
  const status: Record<string, { ok: boolean; detail: string }> = {};

  // Check Claude Code CLI
  const localClaude = path.join(process.cwd(), "node_modules", ".bin", "claude");
  const claudeBin = fs.existsSync(localClaude) ? localClaude : "claude";
  try {
    const { stdout } = await execFileAsync(claudeBin, ["--version"], { timeout: 5000 });
    status.claude = { ok: true, detail: stdout.trim() };
  } catch {
    status.claude = { ok: false, detail: "Claude Code not found. Install with: npm i -g @anthropic-ai/claude-code" };
  }

  // Check Gemini API key
  const geminiKey = process.env.GEMINI_API_KEY;
  if (geminiKey && geminiKey.length > 0) {
    status.gemini = { ok: true, detail: "API key configured" };
  } else {
    status.gemini = { ok: false, detail: "GEMINI_API_KEY not set in .env" };
  }

  return NextResponse.json(status);
}
