import { getDb } from "@/lib/db";
import { generateWithGemini, generateWithClaude, writeGeneratedSite } from "@/lib/generate";
import { getRepoContent } from "@/lib/github";
import { NextRequest, NextResponse } from "next/server";
import path from "path";

export async function POST(req: NextRequest) {
  const { userPrompt, provider } = await req.json();
  const db = getDb();

  const pins = db.prepare("SELECT url, title, description, thumbnail FROM pins").all() as any[];
  const activePresets = db
    .prepare("SELECT category, name, value FROM presets WHERE is_active = 1")
    .all() as any[];
  const settingsRows = db.prepare("SELECT key, value FROM settings").all() as { key: string; value: string }[];
  const settings: Record<string, string> = {};
  for (const row of settingsRows) settings[row.key] = row.value;

  let repoContent = null;
  if (settings.github_repo) {
    try {
      repoContent = await getRepoContent(settings.github_token || null, settings.github_repo);
    } catch {}
  }

  const input = { pins, repoContent, userPrompt: userPrompt || "", presets: activePresets };

  const dirName = `site-${Date.now()}`;
  const outputDir = path.join(process.cwd(), "output", dirName);

  let files: Record<string, string>;
  try {
    const chosenProvider = provider || settings.ai_provider || "gemini";
    if (chosenProvider === "claude") {
      files = await generateWithClaude(input, outputDir);
    } else {
      if (!settings.gemini_api_key) {
        return NextResponse.json({ error: "Gemini API key not configured" }, { status: 400 });
      }
      files = await generateWithGemini(settings.gemini_api_key, input);
      writeGeneratedSite(files, outputDir);
    }
  } catch (error: any) {
    return NextResponse.json({ error: `Generation failed: ${error.message}` }, { status: 500 });
  }

  return NextResponse.json({
    outputDir,
    fileCount: Object.keys(files).length,
    files: Object.keys(files),
    previewUrl: `/api/preview/${dirName}/`,
  });
}
