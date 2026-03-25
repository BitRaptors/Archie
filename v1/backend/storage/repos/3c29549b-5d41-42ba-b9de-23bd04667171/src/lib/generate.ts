import { GoogleGenerativeAI } from "@google/generative-ai";
import { execFile, spawn } from "child_process";
import { promisify } from "util";
import fs from "fs";
import path from "path";
import prompts from "./prompts.json";

const execFileAsync = promisify(execFile);

interface GenerateInput {
  pins: { url: string; title: string; description: string; thumbnail?: string | null }[];
  repoContent: {
    name: string;
    description: string;
    readme: string;
    language: string;
    topics: string[];
    stars: number;
    packageJson: string;
    fileTree: string[];
  } | null;
  userPrompt: string;
  presets: { category: string; name: string; value: string }[];
}

export function parseReadmeSections(readme: string): Record<string, string> {
  const lines = readme.split("\n");
  const sections: Record<string, string> = {};
  let currentHeading = "";
  let currentContent: string[] = [];

  for (const line of lines) {
    const headingMatch = line.match(/^#{1,3}\s+(.+)/);
    if (headingMatch) {
      if (currentHeading || currentContent.length > 0) {
        sections[currentHeading || "overview"] = currentContent.join("\n").trim();
      }
      currentHeading = headingMatch[1].toLowerCase().trim();
      currentContent = [];
    } else {
      currentContent.push(line);
    }
  }
  if (currentHeading || currentContent.length > 0) {
    sections[currentHeading || "overview"] = currentContent.join("\n").trim();
  }

  if (Object.keys(sections).length === 0) {
    return { overview: readme };
  }
  return sections;
}

export function extractDependencies(packageJsonStr: string): { prod: string[]; dev: string[] } {
  if (!packageJsonStr) return { prod: [], dev: [] };
  try {
    const parsed = JSON.parse(packageJsonStr);
    return {
      prod: Object.keys(parsed.dependencies || {}),
      dev: Object.keys(parsed.devDependencies || {}),
    };
  } catch {
    return { prod: [], dev: [] };
  }
}

export function inferProjectType(deps: string[], fileTree: string[]): string {
  const signals: string[] = [];

  const frameworkMap: [string, string][] = [
    ["next", "Next.js"],
    ["nuxt", "Nuxt"],
    ["@angular/core", "Angular"],
    ["vue", "Vue"],
    ["react", "React"],
    ["svelte", "Svelte"],
    ["express", "Express"],
    ["fastify", "Fastify"],
    ["hono", "Hono"],
    ["nest", "NestJS"],
    ["electron", "Electron"],
  ];
  for (const [pkg, label] of frameworkMap) {
    if (deps.some((d) => d === pkg || d.startsWith(`${pkg}/`) || d.startsWith(`@${pkg}/`))) {
      signals.push(label);
    }
  }

  if (deps.includes("typescript") || fileTree.some((f) => f.endsWith(".ts") || f.endsWith(".tsx"))) {
    signals.push("TypeScript");
  }

  const fileSignals: [string, string][] = [
    ["Cargo.toml", "Rust"],
    ["go.mod", "Go"],
    ["requirements.txt", "Python"],
    ["pyproject.toml", "Python"],
    ["Gemfile", "Ruby"],
    ["Package.swift", "Swift"],
  ];
  for (const [file, lang] of fileSignals) {
    if (fileTree.some((f) => f === file || f.endsWith(`/${file}`))) {
      signals.push(lang);
    }
  }

  return signals.length > 0 ? signals.join(" + ") + " project" : "Software project";
}

export function mapReadmeToLandingPageSections(sections: Record<string, string>): Record<string, string> {
  const mapping: [string[], string][] = [
    [["feature", "what", "highlights", "capabilities"], "Features/Benefits"],
    [["why", "problem", "motivation", "background", "pain"], "Problem/Pain"],
    [["getting started", "install", "quickstart", "setup", "quick start"], "How It Works"],
    [["usage", "example", "demo", "tutorial"], "Solution/Demo"],
    [["faq", "questions", "q&a"], "FAQ"],
  ];

  const result: Record<string, string> = {};
  for (const [heading, content] of Object.entries(sections)) {
    for (const [keywords, sectionName] of mapping) {
      if (keywords.some((kw) => heading.includes(kw))) {
        result[sectionName] = content.slice(0, 2000);
        break;
      }
    }
  }
  return result;
}

export function buildPrompt(input: GenerateInput): string {
  const sections: string[] = [];

  // 1. Role & task
  sections.push(prompts.task);

  // 2. Section blueprint — biggest quality lever
  sections.push(prompts.sectionBlueprint);

  // 3. Design configuration (presets)
  if (input.presets.length > 0) {
    const grouped: Record<string, string> = {};
    for (const p of input.presets) {
      grouped[p.category] = `${p.name}: ${p.value}`;
    }
    sections.push(prompts.designConfiguration + Object.entries(grouped).map(([k, v]) => `- **${k}:** ${v}`).join("\n"));
  }

  // 4. Copy guidelines
  sections.push(prompts.copyGuidelines);

  // 5. Inspiration sites (pins)
  if (input.pins.length > 0) {
    const hasAnyScreenshots = input.pins.some((p) => p.thumbnail);
    const header = hasAnyScreenshots ? prompts.inspirationSites : prompts.inspirationSitesNoImages;
    sections.push(
      header +
        input.pins.map((p, i) => {
          let line = `- ${p.url}${p.title ? ` — ${p.title}` : ""}${p.description ? `: ${p.description}` : ""}`;
          if (p.thumbnail && hasAnyScreenshots) {
            line += ` [Screenshot #${i + 1} attached]`;
          }
          return line;
        }).join("\n")
    );
  }

  if (input.repoContent) {
    const rc = input.repoContent;

    // 6. Product info with stars
    sections.push(
      prompts.productInformation +
        `**Product:** ${rc.name}\n` +
        `**Description:** ${rc.description}\n` +
        `**Language:** ${rc.language}\n` +
        `**Topics:** ${rc.topics.join(", ")}\n` +
        (rc.stars > 0 ? `**GitHub Stars:** ${rc.stars.toLocaleString()}\n` : "")
    );

    // 7. Tech stack (extracted deps, inferred project type, condensed file tree)
    const deps = extractDependencies(rc.packageJson);
    const allDeps = [...deps.prod, ...deps.dev];
    if (allDeps.length > 0 || rc.fileTree.length > 0) {
      let techSection = prompts.techStack;
      const projectType = inferProjectType(allDeps, rc.fileTree);
      techSection += `**Project Type:** ${projectType}\n`;
      if (deps.prod.length > 0) {
        techSection += `**Key Dependencies:** ${deps.prod.slice(0, 15).join(", ")}\n`;
      }
      if (rc.fileTree.length > 0) {
        techSection += `**File Structure (sample):**\n${rc.fileTree.slice(0, 30).map((f) => `  ${f}`).join("\n")}\n`;
      }
      sections.push(techSection);
    }

    // 8. README intelligence — parsed sections mapped to landing page structure
    if (rc.readme) {
      const readmeSections = parseReadmeSections(rc.readme);
      const mapped = mapReadmeToLandingPageSections(readmeSections);
      if (Object.keys(mapped).length > 0) {
        let intelSection = prompts.readmeIntel;
        for (const [sectionName, content] of Object.entries(mapped)) {
          intelSection += `\n## ${sectionName}\n${content}\n`;
        }
        sections.push(intelSection);
      }

      // 9. Full README (truncated)
      sections.push(`## Full README Reference\n${rc.readme.slice(0, 6000)}`);
    }
  }

  // 10. Technical constraints
  sections.push(prompts.technicalConstraints);

  // 11. Additional guidance (user prompt)
  if (input.userPrompt) {
    sections.push(prompts.additionalGuidance + input.userPrompt);
  }

  // 12. Output format
  sections.push(prompts.geminiOutputFormat);

  return sections.join("\n\n");
}

function loadPinScreenshots(pins: GenerateInput["pins"]): { index: number; base64: string }[] {
  const results: { index: number; base64: string }[] = [];
  for (let i = 0; i < pins.length; i++) {
    const pin = pins[i];
    if (!pin.thumbnail) continue;
    const filePath = path.join(process.cwd(), "public", pin.thumbnail);
    try {
      if (fs.existsSync(filePath)) {
        const data = fs.readFileSync(filePath);
        results.push({ index: i, base64: data.toString("base64") });
      }
    } catch {}
  }
  return results;
}

export async function generateWithGemini(apiKey: string, input: GenerateInput): Promise<Record<string, string>> {
  const genAI = new GoogleGenerativeAI(apiKey);
  const model = genAI.getGenerativeModel({ model: "gemini-2.5-pro-preview-06-05" });
  const prompt = buildPrompt(input);

  const screenshots = loadPinScreenshots(input.pins);

  if (screenshots.length > 0) {
    // Multimodal: text + images
    const parts: any[] = [{ text: prompt }];
    for (const ss of screenshots) {
      parts.push({
        inlineData: { mimeType: "image/png", data: ss.base64 },
      });
    }
    const result = await model.generateContent(parts);
    const text = result.response.text();
    return parseGeneratedFiles(text);
  }

  // Text-only fallback
  const result = await model.generateContent(prompt);
  const text = result.response.text();
  return parseGeneratedFiles(text);
}

function copyPinScreenshotsToDir(pins: GenerateInput["pins"], outputDir: string): string[] {
  const copied: string[] = [];
  const refDir = path.join(outputDir, "_reference");
  for (let i = 0; i < pins.length; i++) {
    const pin = pins[i];
    if (!pin.thumbnail) continue;
    const src = path.join(process.cwd(), "public", pin.thumbnail);
    try {
      if (fs.existsSync(src)) {
        fs.mkdirSync(refDir, { recursive: true });
        const dest = path.join(refDir, `inspiration-${i + 1}.png`);
        fs.copyFileSync(src, dest);
        copied.push(dest);
      }
    } catch {}
  }
  return copied;
}

export function buildClaudePrompt(input: GenerateInput, outputDir: string): string {
  const prompt = buildPrompt(input);
  let claudePrompt =
    prompts.claudeSystemPrefix.replace("{{outputDir}}", outputDir) +
    prompt.replace(prompts.geminiOutputFormat, prompts.claudeOutputFormat);

  // Tell Claude to look at the reference screenshots
  const screenshotPaths = input.pins
    .map((p, i) => p.thumbnail ? path.join(outputDir, "_reference", `inspiration-${i + 1}.png`) : null)
    .filter(Boolean);

  if (screenshotPaths.length > 0) {
    claudePrompt +=
      "\n\n# Reference Screenshots\n" +
      "IMPORTANT: Before writing any code, use the Read tool to view each of these inspiration screenshot images. " +
      "Study the visual design — colors, typography, spacing, layout, and aesthetic — then replicate that style.\n" +
      screenshotPaths.map((p, i) => `- Screenshot ${i + 1}: ${p}`).join("\n") +
      "\n\nAfter viewing, do NOT include these images in your output. They are reference only. " +
      "Delete the _reference folder when you are done.";
  }

  return claudePrompt;
}

export async function generateWithClaude(input: GenerateInput, outputDir: string): Promise<Record<string, string>> {
  fs.mkdirSync(outputDir, { recursive: true });

  // Copy pin screenshots so Claude can view them
  copyPinScreenshotsToDir(input.pins, outputDir);

  const claudePrompt = buildClaudePrompt(input, outputDir);

  // Resolve claude binary — prefer local node_modules, fall back to global
  const localClaude = path.join(process.cwd(), "node_modules", ".bin", "claude");
  const claudeBin = fs.existsSync(localClaude) ? localClaude : "claude";

  const { stdout } = await new Promise<{ stdout: string }>((resolve, reject) => {
    const proc = spawn(
      claudeBin,
      [
        "--print",
        "--output-format", "json",
        "--max-turns", "10",
        "--allowedTools", "Read,Write,Edit,Bash",
        "-",
      ],
      { cwd: outputDir, stdio: ["pipe", "pipe", "pipe"] }
    );

    let stdout = "";
    let stderr = "";
    proc.stdout.on("data", (chunk: Buffer) => { stdout += chunk.toString(); });
    proc.stderr.on("data", (chunk: Buffer) => { stderr += chunk.toString(); });
    proc.on("close", (code) => {
      if (code !== 0) reject(new Error(`Claude exited with code ${code}: ${stderr}`));
      else resolve({ stdout });
    });
    proc.on("error", reject);

    proc.stdin.write(claudePrompt);
    proc.stdin.end();
  });

  // Collect what files Claude Code wrote
  const files: Record<string, string> = {};
  collectFiles(outputDir, outputDir, files);
  return files;
}

export function collectFiles(dir: string, baseDir: string, files: Record<string, string>) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === "_reference") continue; // skip screenshot reference folder
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      collectFiles(fullPath, baseDir, files);
    } else {
      const relPath = path.relative(baseDir, fullPath);
      files[relPath] = fs.readFileSync(fullPath, "utf-8");
    }
  }
}

function parseGeneratedFiles(text: string): Record<string, string> {
  const jsonMatch = text.match(/```(?:json)?\s*\n?([\s\S]*?)\n?```/) || [null, text];
  const jsonStr = jsonMatch[1] || text;

  try {
    const parsed = JSON.parse(jsonStr.trim());
    if (typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed;
    }
  } catch {}

  return { "index.html": text };
}

export function streamClaudeGeneration(input: GenerateInput, outputDir: string): ReadableStream<Uint8Array> {
  fs.mkdirSync(outputDir, { recursive: true });

  // Copy pin screenshots so Claude can view them
  copyPinScreenshotsToDir(input.pins, outputDir);

  const claudePrompt = buildClaudePrompt(input, outputDir);
  const localClaude = path.join(process.cwd(), "node_modules", ".bin", "claude");
  const claudeBin = fs.existsSync(localClaude) ? localClaude : "claude";

  const encoder = new TextEncoder();

  let proc: ReturnType<typeof spawn> | null = null;
  let closed = false;

  function safeEnqueue(controller: ReadableStreamDefaultController<Uint8Array>, data: Uint8Array) {
    if (!closed) {
      try { controller.enqueue(data); } catch { closed = true; }
    }
  }

  function safeClose(controller: ReadableStreamDefaultController<Uint8Array>) {
    if (!closed) {
      closed = true;
      try { controller.close(); } catch {}
    }
  }

  return new ReadableStream<Uint8Array>({
    start(controller) {
      const p = spawn(
        claudeBin,
        [
          "--print",
          "--verbose",
          "--output-format", "stream-json",
          "--max-turns", "10",
          "--allowedTools", "Read,Write,Edit,Bash",
          "-",
        ],
        { cwd: outputDir, stdio: ["pipe", "pipe", "pipe"] }
      );
      proc = p;

      p.stdin!.write(claudePrompt);
      p.stdin!.end();

      let buffer = "";

      p.stdout!.on("data", (chunk: Buffer) => {
        buffer += chunk.toString();
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (line.trim()) {
            safeEnqueue(controller, encoder.encode(`data: ${line}\n\n`));
          }
        }
      });

      p.stderr!.on("data", (chunk: Buffer) => {
        console.error("[claude stderr]", chunk.toString());
      });

      p.on("close", (code) => {
        if (buffer.trim()) {
          safeEnqueue(controller, encoder.encode(`data: ${buffer}\n\n`));
        }

        const files: Record<string, string> = {};
        try {
          collectFiles(outputDir, outputDir, files);
        } catch (e) {
          // outputDir may not have files if generation failed
        }

        const doneEvent = JSON.stringify({
          type: "done",
          exitCode: code,
          files: Object.keys(files),
          fileCount: Object.keys(files).length,
          outputDir,
        });
        safeEnqueue(controller, encoder.encode(`data: ${doneEvent}\n\n`));
        safeClose(controller);
      });

      p.on("error", (err) => {
        const errorEvent = JSON.stringify({
          type: "error",
          message: err.message,
        });
        safeEnqueue(controller, encoder.encode(`data: ${errorEvent}\n\n`));
        safeClose(controller);
      });
    },
    cancel() {
      closed = true;
      try { proc?.kill(); } catch {}
    },
  });
}

export function streamClaudeRefinement(
  sessionId: string,
  message: string,
  outputDir: string
): ReadableStream<Uint8Array> {
  const localClaude = path.join(process.cwd(), "node_modules", ".bin", "claude");
  const claudeBin = fs.existsSync(localClaude) ? localClaude : "claude";

  const encoder = new TextEncoder();

  let proc: ReturnType<typeof spawn> | null = null;
  let closed = false;

  function safeEnqueue(controller: ReadableStreamDefaultController<Uint8Array>, data: Uint8Array) {
    if (!closed) {
      try { controller.enqueue(data); } catch { closed = true; }
    }
  }

  function safeClose(controller: ReadableStreamDefaultController<Uint8Array>) {
    if (!closed) {
      closed = true;
      try { controller.close(); } catch {}
    }
  }

  return new ReadableStream<Uint8Array>({
    start(controller) {
      const p = spawn(
        claudeBin,
        [
          "--resume", sessionId,
          "--print",
          "--verbose",
          "--output-format", "stream-json",
          "--max-turns", "5",
          "--allowedTools", "Read,Write,Edit,Bash",
          "-",
        ],
        { cwd: outputDir, stdio: ["pipe", "pipe", "pipe"] }
      );
      proc = p;

      p.stdin!.write(message);
      p.stdin!.end();

      let buffer = "";

      p.stdout!.on("data", (chunk: Buffer) => {
        buffer += chunk.toString();
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (line.trim()) {
            safeEnqueue(controller, encoder.encode(`data: ${line}\n\n`));
          }
        }
      });

      p.stderr!.on("data", (chunk: Buffer) => {
        console.error("[claude refine stderr]", chunk.toString());
      });

      p.on("close", (code) => {
        if (buffer.trim()) {
          safeEnqueue(controller, encoder.encode(`data: ${buffer}\n\n`));
        }

        const files: Record<string, string> = {};
        try {
          collectFiles(outputDir, outputDir, files);
        } catch {}

        const doneEvent = JSON.stringify({
          type: "done",
          exitCode: code,
          files: Object.keys(files),
          fileCount: Object.keys(files).length,
          outputDir,
        });
        safeEnqueue(controller, encoder.encode(`data: ${doneEvent}\n\n`));
        safeClose(controller);
      });

      p.on("error", (err) => {
        const errorEvent = JSON.stringify({
          type: "error",
          message: err.message,
        });
        safeEnqueue(controller, encoder.encode(`data: ${errorEvent}\n\n`));
        safeClose(controller);
      });
    },
    cancel() {
      closed = true;
      try { proc?.kill(); } catch {}
    },
  });
}

export function writeGeneratedSite(files: Record<string, string>, outputDir: string) {
  fs.mkdirSync(outputDir, { recursive: true });
  for (const [filePath, content] of Object.entries(files)) {
    const fullPath = path.join(outputDir, filePath);
    fs.mkdirSync(path.dirname(fullPath), { recursive: true });
    fs.writeFileSync(fullPath, content, "utf-8");
  }
}
