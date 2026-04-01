import { getDb } from "@/lib/db";
import { streamClaudeRefinement, collectFiles } from "@/lib/generate";
import { NextRequest, NextResponse } from "next/server";
import path from "path";
import fs from "fs";
import { GoogleGenerativeAI } from "@google/generative-ai";

export async function POST(req: NextRequest) {
  const { siteDir, sessionId, message, provider: reqProvider } = await req.json();

  if (!siteDir || !message) {
    return NextResponse.json({ error: "siteDir and message are required" }, { status: 400 });
  }

  const outputDir = path.join(process.cwd(), "output", siteDir);
  if (!fs.existsSync(outputDir)) {
    return NextResponse.json({ error: "Site directory not found" }, { status: 404 });
  }

  const db = getDb();
  const settingsRows = db.prepare("SELECT key, value FROM settings").all() as { key: string; value: string }[];
  const settings: Record<string, string> = {};
  for (const row of settingsRows) settings[row.key] = row.value;

  const chosenProvider = reqProvider || settings.ai_provider || "gemini";

  if (chosenProvider === "claude") {
    if (!sessionId) {
      return NextResponse.json({ error: "sessionId is required for Claude refinement" }, { status: 400 });
    }

    const stream = streamClaudeRefinement(sessionId, message, outputDir);

    return new Response(stream, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
    });
  }

  // Gemini path: read current files, re-prompt with refinement instruction
  if (!settings.gemini_api_key) {
    return NextResponse.json({ error: "Gemini API key not configured" }, { status: 400 });
  }

  const files: Record<string, string> = {};
  collectFiles(outputDir, outputDir, files);

  const currentCode = Object.entries(files)
    .map(([name, content]) => `--- ${name} ---\n${content}`)
    .join("\n\n");

  const prompt = `You are refining an existing landing page. Here are the current files:\n\n${currentCode}\n\nUser's refinement request: ${message}\n\nReturn the COMPLETE updated files as a JSON object where keys are file paths and values are file contents. Only include files that need changes. Return valid JSON wrapped in a \`\`\`json code block.`;

  try {
    const genAI = new GoogleGenerativeAI(settings.gemini_api_key);
    const model = genAI.getGenerativeModel({ model: "gemini-2.5-pro-preview-06-05" });
    const result = await model.generateContent(prompt);
    const text = result.response.text();

    // Parse the JSON response
    const jsonMatch = text.match(/```(?:json)?\s*\n?([\s\S]*?)\n?```/) || [null, text];
    const jsonStr = jsonMatch[1] || text;
    let updatedFiles: Record<string, string>;
    try {
      updatedFiles = JSON.parse(jsonStr.trim());
    } catch {
      return NextResponse.json({ error: "Failed to parse Gemini response" }, { status: 500 });
    }

    // Write updated files
    for (const [filePath, content] of Object.entries(updatedFiles)) {
      const fullPath = path.join(outputDir, filePath);
      fs.mkdirSync(path.dirname(fullPath), { recursive: true });
      fs.writeFileSync(fullPath, content, "utf-8");
    }

    return NextResponse.json({
      message: `Updated ${Object.keys(updatedFiles).length} file(s).`,
      files: Object.keys(updatedFiles),
    });
  } catch (error: any) {
    return NextResponse.json({ error: `Refinement failed: ${error.message}` }, { status: 500 });
  }
}
