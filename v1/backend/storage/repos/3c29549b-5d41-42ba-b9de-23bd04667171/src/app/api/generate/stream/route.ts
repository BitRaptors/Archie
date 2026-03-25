import { getDb } from "@/lib/db";
import { streamClaudeGeneration } from "@/lib/generate";
import { getRepoContent } from "@/lib/github";
import { NextRequest } from "next/server";
import path from "path";

export async function POST(req: NextRequest) {
  let userPrompt: string;
  try {
    ({ userPrompt } = await req.json());
  } catch {
    return new Response(JSON.stringify({ error: "Invalid request body" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }
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

  const stream = streamClaudeGeneration(input, outputDir);

  // Wrap stream to inject previewUrl into the done event
  const encoder = new TextEncoder();
  const transformedStream = stream.pipeThrough(
    new TransformStream<Uint8Array, Uint8Array>({
      transform(chunk, controller) {
        const text = new TextDecoder().decode(chunk);
        if (text.includes('"type":"done"')) {
          try {
            const dataMatch = text.match(/^data: (.+)$/m);
            if (dataMatch) {
              const parsed = JSON.parse(dataMatch[1]);
              if (parsed.type === "done") {
                parsed.previewUrl = `/api/preview/${dirName}/`;
                const replaced = `data: ${JSON.stringify(parsed)}\n\n`;
                controller.enqueue(encoder.encode(replaced));
                return;
              }
            }
          } catch {}
        }
        controller.enqueue(chunk);
      },
    })
  );

  return new Response(transformedStream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
