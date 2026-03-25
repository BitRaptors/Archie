# Landing Page Builder (Pinterest-style) — MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a locally-running open-source app where users collect inspiration sites on a Pinterest-like board, connect a GitHub repo for marketing content, configure generation via presets/switches, then one-click generate a landing page using AI (Gemini or Claude).

**Architecture:** Next.js 14 app with App Router. SQLite (via better-sqlite3) for local persistence. Puppeteer for capturing website thumbnails. Octokit for GitHub repo access. AI generation via user's choice of Gemini API or Anthropic Claude SDK. Generated output is a static site written to disk, served via a local dev server, and auto-opened in browser.

**Tech Stack:**
- **Frontend:** Next.js 14 (App Router), React 18, Tailwind CSS, react-masonry-css
- **Storage:** better-sqlite3 (local SQLite file)
- **Screenshots:** Puppeteer
- **GitHub:** @octokit/rest
- **AI:** @google/generative-ai (Gemini), @anthropic-ai/sdk (Claude)
- **Preview:** serve (static file server)

---

## Task 0: Project Bootstrap

**Files:**
- Create: `package.json`, `tsconfig.json`, `tailwind.config.ts`, `next.config.ts`, `.gitignore`, `.env.example`
- Create: `src/app/layout.tsx`, `src/app/page.tsx`, `src/app/globals.css`
- Create: `src/lib/db.ts` (SQLite setup)

**Step 1: Initialize the project**

Run:
```bash
npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir --no-import-alias --use-npm
```
Expected: Next.js project scaffolded in current directory.

**Step 2: Install all MVP dependencies**

Run:
```bash
npm install better-sqlite3 puppeteer @octokit/rest @google/generative-ai @anthropic-ai/sdk react-masonry-css serve
npm install -D @types/better-sqlite3
```

**Step 3: Create `.env.example`**

```env
GEMINI_API_KEY=
ANTHROPIC_API_KEY=
GITHUB_TOKEN=
```

**Step 4: Create `src/lib/db.ts`** — SQLite setup with schema

```typescript
import Database from "better-sqlite3";
import path from "path";

const DB_PATH = path.join(process.cwd(), "data", "builder.db");

let db: Database.Database | null = null;

export function getDb(): Database.Database {
  if (!db) {
    const fs = require("fs");
    fs.mkdirSync(path.dirname(DB_PATH), { recursive: true });
    db = new Database(DB_PATH);
    db.pragma("journal_mode = WAL");
    db.exec(`
      CREATE TABLE IF NOT EXISTS pins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT NOT NULL,
        title TEXT,
        description TEXT,
        thumbnail TEXT,
        created_at TEXT DEFAULT (datetime('now'))
      );
      CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS presets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        value TEXT NOT NULL,
        is_active INTEGER DEFAULT 0
      );
    `);
    seedPresets(db);
  }
  return db;
}

function seedPresets(db: Database.Database) {
  const count = db.prepare("SELECT COUNT(*) as c FROM presets").get() as { c: number };
  if (count.c > 0) return;

  const presets = [
    // Style presets
    { name: "Minimal", category: "style", value: "Clean, minimal design with lots of whitespace. Simple typography." },
    { name: "Bold & Vibrant", category: "style", value: "Bold colors, large typography, energetic feel." },
    { name: "Corporate", category: "style", value: "Professional, trustworthy, clean layout with subtle colors." },
    { name: "Startup", category: "style", value: "Modern, gradient backgrounds, rounded cards, friendly tone." },
    // Layout presets
    { name: "Hero + Features", category: "layout", value: "Large hero section, then feature grid, then CTA." },
    { name: "Story Flow", category: "layout", value: "Narrative scroll: problem, solution, how it works, testimonials, CTA." },
    { name: "Product Focus", category: "layout", value: "Product screenshot hero, benefits sidebar, comparison table, pricing." },
    // Tone presets
    { name: "Professional", category: "tone", value: "Formal, authoritative, data-driven language." },
    { name: "Casual & Friendly", category: "tone", value: "Conversational, approachable, uses 'you' language." },
    { name: "Technical", category: "tone", value: "Developer-focused, precise, shows code examples." },
    // Framework presets
    { name: "Plain HTML/CSS", category: "framework", value: "Single index.html with inline CSS and vanilla JS." },
    { name: "Tailwind", category: "framework", value: "Single HTML file using Tailwind CSS via CDN." },
    { name: "React (Vite)", category: "framework", value: "Vite + React project with Tailwind." },
  ];

  const insert = db.prepare("INSERT INTO presets (name, category, value) VALUES (?, ?, ?)");
  for (const p of presets) {
    insert.run(p.name, p.category, p.value);
  }
}
```

**Step 5: Add `data/` to `.gitignore`**

Append to `.gitignore`:
```
data/
.env
```

**Step 6: Commit**

```bash
git init
git add -A
git commit -m "chore: bootstrap Next.js project with dependencies and SQLite setup"
```

---

## Task 1: Pin Board API (CRUD)

**Files:**
- Create: `src/app/api/pins/route.ts`
- Create: `src/app/api/pins/[id]/route.ts`
- Test: manual via curl (API routes)

**Step 1: Create GET/POST `/api/pins`**

```typescript
// src/app/api/pins/route.ts
import { getDb } from "@/lib/db";
import { NextRequest, NextResponse } from "next/server";

export async function GET() {
  const db = getDb();
  const pins = db.prepare("SELECT * FROM pins ORDER BY created_at DESC").all();
  return NextResponse.json(pins);
}

export async function POST(req: NextRequest) {
  const { url, title, description } = await req.json();
  if (!url) {
    return NextResponse.json({ error: "url is required" }, { status: 400 });
  }
  const db = getDb();
  const result = db
    .prepare("INSERT INTO pins (url, title, description) VALUES (?, ?, ?)")
    .run(url, title || null, description || null);
  const pin = db.prepare("SELECT * FROM pins WHERE id = ?").get(result.lastInsertRowid);
  return NextResponse.json(pin, { status: 201 });
}
```

**Step 2: Create DELETE `/api/pins/[id]`**

```typescript
// src/app/api/pins/[id]/route.ts
import { getDb } from "@/lib/db";
import { NextRequest, NextResponse } from "next/server";

export async function DELETE(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const db = getDb();
  db.prepare("DELETE FROM pins WHERE id = ?").run(id);
  return NextResponse.json({ ok: true });
}
```

**Step 3: Run dev server and test**

Run: `npm run dev` then in another terminal:
```bash
curl -X POST http://localhost:3000/api/pins -H 'Content-Type: application/json' -d '{"url":"https://example.com","title":"Test"}'
curl http://localhost:3000/api/pins
```
Expected: Pin created and listed.

**Step 4: Commit**

```bash
git add src/app/api/pins/
git commit -m "feat: add pins CRUD API routes"
```

---

## Task 2: Screenshot Capture API

**Files:**
- Create: `src/app/api/screenshot/route.ts`
- Create: `public/thumbnails/.gitkeep`

**Step 1: Create screenshot endpoint**

```typescript
// src/app/api/screenshot/route.ts
import { NextRequest, NextResponse } from "next/server";
import puppeteer from "puppeteer";
import path from "path";
import fs from "fs";

export async function POST(req: NextRequest) {
  const { url, pinId } = await req.json();
  if (!url || !pinId) {
    return NextResponse.json({ error: "url and pinId required" }, { status: 400 });
  }

  const thumbnailDir = path.join(process.cwd(), "public", "thumbnails");
  fs.mkdirSync(thumbnailDir, { recursive: true });

  const filename = `pin-${pinId}.png`;
  const filepath = path.join(thumbnailDir, filename);

  try {
    const browser = await puppeteer.launch({ headless: true });
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 800 });
    await page.goto(url, { waitUntil: "networkidle2", timeout: 15000 });
    await page.screenshot({ path: filepath, type: "png" });
    await browser.close();

    // Update pin with thumbnail path
    const { getDb } = require("@/lib/db");
    const db = getDb();
    db.prepare("UPDATE pins SET thumbnail = ? WHERE id = ?").run(`/thumbnails/${filename}`, pinId);

    return NextResponse.json({ thumbnail: `/thumbnails/${filename}` });
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
```

**Step 2: Add `public/thumbnails/` to `.gitignore`**

Append: `public/thumbnails/`

**Step 3: Commit**

```bash
git add src/app/api/screenshot/ public/thumbnails/.gitkeep .gitignore
git commit -m "feat: add screenshot capture API using Puppeteer"
```

---

## Task 3: Settings & Presets API

**Files:**
- Create: `src/app/api/settings/route.ts`
- Create: `src/app/api/presets/route.ts`

**Step 1: Create settings API (GitHub token, API keys)**

```typescript
// src/app/api/settings/route.ts
import { getDb } from "@/lib/db";
import { NextRequest, NextResponse } from "next/server";

export async function GET() {
  const db = getDb();
  const rows = db.prepare("SELECT * FROM settings").all() as { key: string; value: string }[];
  const settings: Record<string, string> = {};
  for (const row of rows) {
    settings[row.key] = row.value;
  }
  return NextResponse.json(settings);
}

export async function PUT(req: NextRequest) {
  const body = await req.json();
  const db = getDb();
  const upsert = db.prepare(
    "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value"
  );
  for (const [key, value] of Object.entries(body)) {
    upsert.run(key, value as string);
  }
  return NextResponse.json({ ok: true });
}
```

**Step 2: Create presets API (list + toggle active)**

```typescript
// src/app/api/presets/route.ts
import { getDb } from "@/lib/db";
import { NextRequest, NextResponse } from "next/server";

export async function GET() {
  const db = getDb();
  const presets = db.prepare("SELECT * FROM presets ORDER BY category, name").all();
  return NextResponse.json(presets);
}

export async function PUT(req: NextRequest) {
  const { id, is_active } = await req.json();
  const db = getDb();
  // For single-select categories: deactivate others in same category first
  const preset = db.prepare("SELECT category FROM presets WHERE id = ?").get(id) as { category: string } | undefined;
  if (preset) {
    db.prepare("UPDATE presets SET is_active = 0 WHERE category = ?").run(preset.category);
  }
  db.prepare("UPDATE presets SET is_active = ? WHERE id = ?").run(is_active ? 1 : 0, id);
  const all = db.prepare("SELECT * FROM presets ORDER BY category, name").all();
  return NextResponse.json(all);
}
```

**Step 3: Commit**

```bash
git add src/app/api/settings/ src/app/api/presets/
git commit -m "feat: add settings and presets API routes"
```

---

## Task 4: GitHub Repo Content API

**Files:**
- Create: `src/app/api/github/route.ts`
- Create: `src/lib/github.ts`

**Step 1: Create GitHub helper**

```typescript
// src/lib/github.ts
import { Octokit } from "@octokit/rest";

export async function getRepoContent(token: string, repoUrl: string) {
  const octokit = new Octokit({ auth: token });

  // Parse "owner/repo" or full URL
  const match = repoUrl.match(/(?:github\.com\/)?([^/]+)\/([^/\s]+)/);
  if (!match) throw new Error("Invalid repo format. Use owner/repo or full GitHub URL.");
  const owner = match[1];
  const repo = match[2].replace(/\.git$/, "");

  // Get repo info
  const { data: repoData } = await octokit.repos.get({ owner, repo });

  // Get README
  let readme = "";
  try {
    const { data } = await octokit.repos.getReadme({ owner, repo });
    readme = Buffer.from(data.content, "base64").toString("utf-8");
  } catch {}

  // Get package.json if exists
  let packageJson = "";
  try {
    const { data } = await octokit.repos.getContent({ owner, repo, path: "package.json" });
    if ("content" in data) {
      packageJson = Buffer.from(data.content, "base64").toString("utf-8");
    }
  } catch {}

  // Get file tree (top-level + one level deep for src/)
  const { data: tree } = await octokit.git.getTree({
    owner,
    repo,
    tree_sha: repoData.default_branch,
    recursive: "1",
  });
  const paths = tree.tree
    .filter((t) => t.type === "blob")
    .map((t) => t.path)
    .slice(0, 200);

  return {
    name: repoData.name,
    description: repoData.description || "",
    language: repoData.language || "",
    topics: repoData.topics || [],
    stars: repoData.stargazers_count,
    readme,
    packageJson,
    fileTree: paths,
  };
}
```

**Step 2: Create API route**

```typescript
// src/app/api/github/route.ts
import { getDb } from "@/lib/db";
import { getRepoContent } from "@/lib/github";
import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  const { repoUrl } = await req.json();
  const db = getDb();
  const settings = db.prepare("SELECT value FROM settings WHERE key = 'github_token'").get() as
    | { value: string }
    | undefined;
  if (!settings?.value) {
    return NextResponse.json({ error: "GitHub token not configured" }, { status: 400 });
  }
  try {
    const content = await getRepoContent(settings.value, repoUrl);
    return NextResponse.json(content);
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
```

**Step 3: Commit**

```bash
git add src/lib/github.ts src/app/api/github/
git commit -m "feat: add GitHub repo content extraction API"
```

---

## Task 5: AI Generation Engine

**Files:**
- Create: `src/lib/generate.ts`
- Create: `src/app/api/generate/route.ts`

**Step 1: Create the generation prompt builder**

```typescript
// src/lib/generate.ts
import { GoogleGenerativeAI } from "@google/generative-ai";
import Anthropic from "@anthropic-ai/sdk";
import fs from "fs";
import path from "path";

interface GenerateInput {
  pins: { url: string; title: string; description: string }[];
  repoContent: {
    name: string;
    description: string;
    readme: string;
    language: string;
    topics: string[];
  } | null;
  userPrompt: string;
  presets: { category: string; name: string; value: string }[];
}

function buildPrompt(input: GenerateInput): string {
  const sections: string[] = [];

  sections.push("# Task\nGenerate a complete, production-quality landing page. Output ONLY the code files, no explanation.");

  // Presets as context
  if (input.presets.length > 0) {
    const grouped: Record<string, string> = {};
    for (const p of input.presets) {
      grouped[p.category] = `${p.name}: ${p.value}`;
    }
    sections.push("# Design Configuration\n" + Object.entries(grouped).map(([k, v]) => `- **${k}:** ${v}`).join("\n"));
  }

  // Inspiration sites
  if (input.pins.length > 0) {
    sections.push(
      "# Inspiration Sites (match the look and feel of these)\n" +
        input.pins.map((p) => `- ${p.url}${p.title ? ` — ${p.title}` : ""}${p.description ? `: ${p.description}` : ""}`).join("\n")
    );
  }

  // Repo content as marketing source
  if (input.repoContent) {
    const rc = input.repoContent;
    sections.push(
      `# Product Information (use this as marketing content source)\n` +
        `**Product:** ${rc.name}\n` +
        `**Description:** ${rc.description}\n` +
        `**Language:** ${rc.language}\n` +
        `**Topics:** ${rc.topics.join(", ")}\n` +
        `\n## README\n${rc.readme.slice(0, 8000)}`
    );
  }

  // User guidance
  if (input.userPrompt) {
    sections.push(`# Additional Guidance\n${input.userPrompt}`);
  }

  sections.push(
    "# Output Format\n" +
      "Respond with ONLY a JSON object where keys are file paths and values are file contents.\n" +
      'Example: {"index.html": "<!DOCTYPE html>...", "style.css": "body { ... }"}\n' +
      "Make the page fully self-contained. Use CDN links for any external libraries.\n" +
      "Include responsive design. Make it look polished and professional."
  );

  return sections.join("\n\n");
}

export async function generateWithGemini(apiKey: string, input: GenerateInput): Promise<Record<string, string>> {
  const genAI = new GoogleGenerativeAI(apiKey);
  const model = genAI.getGenerativeModel({ model: "gemini-2.5-pro-preview-06-05" });
  const prompt = buildPrompt(input);
  const result = await model.generateContent(prompt);
  const text = result.response.text();
  return parseGeneratedFiles(text);
}

export async function generateWithClaude(apiKey: string, input: GenerateInput): Promise<Record<string, string>> {
  const client = new Anthropic({ apiKey });
  const prompt = buildPrompt(input);
  const message = await client.messages.create({
    model: "claude-sonnet-4-6-20250514",
    max_tokens: 16000,
    messages: [{ role: "user", content: prompt }],
  });
  const text = message.content[0].type === "text" ? message.content[0].text : "";
  return parseGeneratedFiles(text);
}

function parseGeneratedFiles(text: string): Record<string, string> {
  // Try to extract JSON from the response (might be wrapped in markdown code blocks)
  const jsonMatch = text.match(/```(?:json)?\s*\n?([\s\S]*?)\n?```/) || [null, text];
  const jsonStr = jsonMatch[1] || text;

  try {
    const parsed = JSON.parse(jsonStr.trim());
    if (typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed;
    }
  } catch {}

  // Fallback: treat entire response as index.html
  return { "index.html": text };
}

export function writeGeneratedSite(files: Record<string, string>, outputDir: string) {
  fs.mkdirSync(outputDir, { recursive: true });
  for (const [filePath, content] of Object.entries(files)) {
    const fullPath = path.join(outputDir, filePath);
    fs.mkdirSync(path.dirname(fullPath), { recursive: true });
    fs.writeFileSync(fullPath, content, "utf-8");
  }
}
```

**Step 2: Create generation API route**

```typescript
// src/app/api/generate/route.ts
import { getDb } from "@/lib/db";
import { generateWithGemini, generateWithClaude, writeGeneratedSite } from "@/lib/generate";
import { getRepoContent } from "@/lib/github";
import { NextRequest, NextResponse } from "next/server";
import path from "path";
import { exec } from "child_process";

export async function POST(req: NextRequest) {
  const { userPrompt, provider } = await req.json();
  const db = getDb();

  // Gather all context
  const pins = db.prepare("SELECT url, title, description FROM pins").all() as any[];
  const activePresets = db
    .prepare("SELECT category, name, value FROM presets WHERE is_active = 1")
    .all() as any[];
  const settingsRows = db.prepare("SELECT key, value FROM settings").all() as { key: string; value: string }[];
  const settings: Record<string, string> = {};
  for (const row of settingsRows) settings[row.key] = row.value;

  // Get repo content if configured
  let repoContent = null;
  if (settings.github_repo && settings.github_token) {
    try {
      repoContent = await getRepoContent(settings.github_token, settings.github_repo);
    } catch {}
  }

  const input = { pins, repoContent, userPrompt: userPrompt || "", presets: activePresets };

  let files: Record<string, string>;
  try {
    const chosenProvider = provider || settings.ai_provider || "gemini";
    if (chosenProvider === "claude") {
      if (!settings.anthropic_api_key) {
        return NextResponse.json({ error: "Anthropic API key not configured" }, { status: 400 });
      }
      files = await generateWithClaude(settings.anthropic_api_key, input);
    } else {
      if (!settings.gemini_api_key) {
        return NextResponse.json({ error: "Gemini API key not configured" }, { status: 400 });
      }
      files = await generateWithGemini(settings.gemini_api_key, input);
    }
  } catch (error: any) {
    return NextResponse.json({ error: `Generation failed: ${error.message}` }, { status: 500 });
  }

  // Write files to output directory
  const outputDir = path.join(process.cwd(), "output", `site-${Date.now()}`);
  writeGeneratedSite(files, outputDir);

  // Start local server and open browser
  const port = 4321;
  exec(`npx serve "${outputDir}" -l ${port} --no-clipboard`, (err) => {
    if (err) console.error("serve error:", err);
  });
  exec(`open http://localhost:${port}`);

  return NextResponse.json({
    outputDir,
    fileCount: Object.keys(files).length,
    files: Object.keys(files),
    previewUrl: `http://localhost:${port}`,
  });
}
```

**Step 3: Add `output/` to `.gitignore`**

**Step 4: Commit**

```bash
git add src/lib/generate.ts src/app/api/generate/ .gitignore
git commit -m "feat: add AI generation engine with Gemini and Claude support"
```

---

## Task 6: Frontend — Layout Shell & Settings Panel

**Files:**
- Modify: `src/app/layout.tsx`
- Modify: `src/app/page.tsx`
- Modify: `src/app/globals.css`
- Create: `src/components/SettingsPanel.tsx`
- Create: `src/components/Header.tsx`

**Step 1: Update `globals.css` with design tokens**

Replace the default content of `src/app/globals.css` with:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --bg: #0a0a0a;
  --surface: #141414;
  --surface-hover: #1e1e1e;
  --border: #2a2a2a;
  --text: #ededed;
  --text-muted: #888;
  --accent: #e11d48;
  --accent-hover: #f43f5e;
}

body {
  background: var(--bg);
  color: var(--text);
}
```

**Step 2: Create Header component**

```typescript
// src/components/Header.tsx
"use client";

import { useState } from "react";
import SettingsPanel from "./SettingsPanel";

export default function Header() {
  const [settingsOpen, setSettingsOpen] = useState(false);

  return (
    <>
      <header className="sticky top-0 z-50 border-b border-[var(--border)] bg-[var(--bg)]/80 backdrop-blur-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <h1 className="text-xl font-bold tracking-tight">
            <span className="text-[var(--accent)]">Pin</span>Launch
          </h1>
          <button
            onClick={() => setSettingsOpen(true)}
            className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--text-muted)] hover:border-[var(--accent)] hover:text-[var(--text)] transition-colors"
          >
            Settings
          </button>
        </div>
      </header>
      {settingsOpen && <SettingsPanel onClose={() => setSettingsOpen(false)} />}
    </>
  );
}
```

**Step 3: Create SettingsPanel component**

```typescript
// src/components/SettingsPanel.tsx
"use client";

import { useEffect, useState } from "react";

interface Props {
  onClose: () => void;
}

export default function SettingsPanel({ onClose }: Props) {
  const [settings, setSettings] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch("/api/settings").then((r) => r.json()).then(setSettings);
  }, []);

  const update = (key: string, value: string) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  };

  const save = async () => {
    setSaving(true);
    await fetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    });
    setSaving(false);
    onClose();
  };

  const fields = [
    { key: "github_token", label: "GitHub Token", type: "password" },
    { key: "github_repo", label: "GitHub Repo", type: "text", placeholder: "owner/repo" },
    { key: "gemini_api_key", label: "Gemini API Key", type: "password" },
    { key: "anthropic_api_key", label: "Anthropic API Key", type: "password" },
    { key: "ai_provider", label: "AI Provider", type: "select", options: ["gemini", "claude"] },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="mb-4 text-lg font-semibold">Settings</h2>
        <div className="space-y-3">
          {fields.map((f) => (
            <div key={f.key}>
              <label className="mb-1 block text-sm text-[var(--text-muted)]">{f.label}</label>
              {f.type === "select" ? (
                <select
                  value={settings[f.key] || ""}
                  onChange={(e) => update(f.key, e.target.value)}
                  className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm"
                >
                  {f.options?.map((o) => (
                    <option key={o} value={o}>{o}</option>
                  ))}
                </select>
              ) : (
                <input
                  type={f.type}
                  value={settings[f.key] || ""}
                  onChange={(e) => update(f.key, e.target.value)}
                  placeholder={f.placeholder}
                  className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm"
                />
              )}
            </div>
          ))}
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-lg px-4 py-2 text-sm text-[var(--text-muted)] hover:text-[var(--text)]"
          >
            Cancel
          </button>
          <button
            onClick={save}
            disabled={saving}
            className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--accent-hover)] disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
```

**Step 4: Update layout.tsx**

```typescript
// src/app/layout.tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Header from "@/components/Header";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "PinLaunch — AI Landing Page Builder",
  description: "Collect inspiration, connect your repo, generate landing pages with AI",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={inter.className}>
        <Header />
        <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
```

**Step 5: Commit**

```bash
git add src/app/layout.tsx src/app/globals.css src/components/
git commit -m "feat: add layout shell, header, and settings panel"
```

---

## Task 7: Frontend — Pinterest Board Component

**Files:**
- Create: `src/components/PinBoard.tsx`
- Create: `src/components/PinCard.tsx`
- Create: `src/components/AddPinModal.tsx`

**Step 1: Create PinCard component**

```typescript
// src/components/PinCard.tsx
"use client";

interface Pin {
  id: number;
  url: string;
  title: string;
  description: string;
  thumbnail: string | null;
}

interface Props {
  pin: Pin;
  onDelete: (id: number) => void;
}

export default function PinCard({ pin, onDelete }: Props) {
  return (
    <div className="group relative mb-4 break-inside-avoid rounded-xl border border-[var(--border)] bg-[var(--surface)] overflow-hidden hover:border-[var(--accent)]/50 transition-colors">
      {pin.thumbnail ? (
        <img
          src={pin.thumbnail}
          alt={pin.title || pin.url}
          className="w-full object-cover"
          loading="lazy"
        />
      ) : (
        <div className="flex h-40 items-center justify-center bg-[var(--bg)] text-[var(--text-muted)] text-sm">
          Loading preview...
        </div>
      )}
      <div className="p-3">
        {pin.title && <h3 className="text-sm font-medium truncate">{pin.title}</h3>}
        <a
          href={pin.url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-1 block text-xs text-[var(--text-muted)] truncate hover:text-[var(--accent)]"
        >
          {pin.url}
        </a>
        {pin.description && (
          <p className="mt-1.5 text-xs text-[var(--text-muted)] line-clamp-2">{pin.description}</p>
        )}
      </div>
      <button
        onClick={() => onDelete(pin.id)}
        className="absolute right-2 top-2 rounded-full bg-black/60 p-1.5 text-white opacity-0 group-hover:opacity-100 transition-opacity hover:bg-[var(--accent)]"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M18 6L6 18M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}
```

**Step 2: Create AddPinModal component**

```typescript
// src/components/AddPinModal.tsx
"use client";

import { useState } from "react";

interface Props {
  onAdd: (pin: { url: string; title: string; description: string }) => void;
  onClose: () => void;
}

export default function AddPinModal({ onAdd, onClose }: Props) {
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");

  const submit = () => {
    if (!url.trim()) return;
    onAdd({ url: url.trim(), title: title.trim(), description: description.trim() });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="mb-4 text-lg font-semibold">Add Inspiration</h2>
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-sm text-[var(--text-muted)]">URL *</label>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com"
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm"
              autoFocus
            />
          </div>
          <div>
            <label className="mb-1 block text-sm text-[var(--text-muted)]">Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="What you like about this site"
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm text-[var(--text-muted)]">Notes</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Color scheme, layout, typography..."
              rows={2}
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm resize-none"
            />
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-lg px-4 py-2 text-sm text-[var(--text-muted)]">
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={!url.trim()}
            className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--accent-hover)] disabled:opacity-50"
          >
            Add Pin
          </button>
        </div>
      </div>
    </div>
  );
}
```

**Step 3: Create PinBoard component (masonry layout)**

```typescript
// src/components/PinBoard.tsx
"use client";

import { useEffect, useState } from "react";
import Masonry from "react-masonry-css";
import PinCard from "./PinCard";
import AddPinModal from "./AddPinModal";

interface Pin {
  id: number;
  url: string;
  title: string;
  description: string;
  thumbnail: string | null;
}

export default function PinBoard() {
  const [pins, setPins] = useState<Pin[]>([]);
  const [showAdd, setShowAdd] = useState(false);

  const fetchPins = () => {
    fetch("/api/pins").then((r) => r.json()).then(setPins);
  };

  useEffect(() => { fetchPins(); }, []);

  const addPin = async (data: { url: string; title: string; description: string }) => {
    const res = await fetch("/api/pins", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    const pin = await res.json();
    setPins((prev) => [pin, ...prev]);

    // Trigger screenshot in background
    fetch("/api/screenshot", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: data.url, pinId: pin.id }),
    }).then(() => fetchPins());
  };

  const deletePin = async (id: number) => {
    await fetch(`/api/pins/${id}`, { method: "DELETE" });
    setPins((prev) => prev.filter((p) => p.id !== id));
  };

  const breakpoints = { default: 4, 1024: 3, 768: 2, 480: 1 };

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Inspiration Board</h2>
        <button
          onClick={() => setShowAdd(true)}
          className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--accent-hover)]"
        >
          + Add Pin
        </button>
      </div>

      {pins.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[var(--border)] py-20 text-[var(--text-muted)]">
          <p className="text-lg">No pins yet</p>
          <p className="mt-1 text-sm">Add websites that inspire your landing page design</p>
        </div>
      ) : (
        <Masonry
          breakpointCols={breakpoints}
          className="flex -ml-4 w-auto"
          columnClassName="pl-4 bg-clip-padding"
        >
          {pins.map((pin) => (
            <PinCard key={pin.id} pin={pin} onDelete={deletePin} />
          ))}
        </Masonry>
      )}

      {showAdd && <AddPinModal onAdd={addPin} onClose={() => setShowAdd(false)} />}
    </div>
  );
}
```

**Step 4: Commit**

```bash
git add src/components/PinBoard.tsx src/components/PinCard.tsx src/components/AddPinModal.tsx
git commit -m "feat: add Pinterest-style masonry board with pin cards"
```

---

## Task 8: Frontend — Presets Panel & Generation Controls

**Files:**
- Create: `src/components/PresetsPanel.tsx`
- Create: `src/components/GeneratePanel.tsx`

**Step 1: Create PresetsPanel**

```typescript
// src/components/PresetsPanel.tsx
"use client";

import { useEffect, useState } from "react";

interface Preset {
  id: number;
  name: string;
  category: string;
  value: string;
  is_active: number;
}

export default function PresetsPanel() {
  const [presets, setPresets] = useState<Preset[]>([]);

  useEffect(() => {
    fetch("/api/presets").then((r) => r.json()).then(setPresets);
  }, []);

  const toggle = async (id: number, active: boolean) => {
    const res = await fetch("/api/presets", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, is_active: active }),
    });
    setPresets(await res.json());
  };

  const categories = [...new Set(presets.map((p) => p.category))];

  const categoryLabels: Record<string, string> = {
    style: "Style",
    layout: "Layout",
    tone: "Tone",
    framework: "Output Format",
  };

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-[var(--text-muted)]">
        Presets
      </h3>
      <div className="space-y-4">
        {categories.map((cat) => (
          <div key={cat}>
            <p className="mb-2 text-xs font-medium text-[var(--text-muted)]">
              {categoryLabels[cat] || cat}
            </p>
            <div className="flex flex-wrap gap-2">
              {presets
                .filter((p) => p.category === cat)
                .map((p) => (
                  <button
                    key={p.id}
                    onClick={() => toggle(p.id, !p.is_active)}
                    className={`rounded-lg border px-3 py-1.5 text-xs transition-colors ${
                      p.is_active
                        ? "border-[var(--accent)] bg-[var(--accent)]/10 text-[var(--accent)]"
                        : "border-[var(--border)] text-[var(--text-muted)] hover:border-[var(--text-muted)]"
                    }`}
                  >
                    {p.name}
                  </button>
                ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

**Step 2: Create GeneratePanel**

```typescript
// src/components/GeneratePanel.tsx
"use client";

import { useState } from "react";

export default function GeneratePanel() {
  const [prompt, setPrompt] = useState("");
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState<{
    previewUrl: string;
    fileCount: number;
    files: string[];
    outputDir: string;
  } | null>(null);
  const [error, setError] = useState("");

  const generate = async () => {
    setGenerating(true);
    setError("");
    setResult(null);

    try {
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ userPrompt: prompt }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Generation failed");
      } else {
        setResult(data);
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-[var(--text-muted)]">
        Generate
      </h3>
      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder="Additional guidance for the AI (optional)... e.g. 'Focus on developer experience, include code snippets, dark theme'"
        rows={3}
        className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm resize-none mb-3"
      />
      <button
        onClick={generate}
        disabled={generating}
        className="w-full rounded-lg bg-[var(--accent)] py-3 text-sm font-semibold text-white hover:bg-[var(--accent-hover)] disabled:opacity-50 transition-colors"
      >
        {generating ? (
          <span className="flex items-center justify-center gap-2">
            <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Generating...
          </span>
        ) : (
          "Generate Landing Page"
        )}
      </button>

      {error && (
        <div className="mt-3 rounded-lg border border-red-900 bg-red-950/50 p-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-3 rounded-lg border border-green-900 bg-green-950/50 p-3 text-sm text-green-400">
          <p className="font-medium">Site generated! ({result.fileCount} files)</p>
          <p className="mt-1 text-xs text-[var(--text-muted)]">
            Files: {result.files.join(", ")}
          </p>
          <a
            href={result.previewUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 inline-block text-[var(--accent)] hover:underline"
          >
            Open Preview →
          </a>
        </div>
      )}
    </div>
  );
}
```

**Step 3: Commit**

```bash
git add src/components/PresetsPanel.tsx src/components/GeneratePanel.tsx
git commit -m "feat: add presets panel and generation controls"
```

---

## Task 9: Frontend — Main Page Assembly

**Files:**
- Modify: `src/app/page.tsx`

**Step 1: Wire everything together**

```typescript
// src/app/page.tsx
import PinBoard from "@/components/PinBoard";
import PresetsPanel from "@/components/PresetsPanel";
import GeneratePanel from "@/components/GeneratePanel";

export default function Home() {
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
      <div>
        <PinBoard />
      </div>
      <div className="space-y-4">
        <PresetsPanel />
        <GeneratePanel />
      </div>
    </div>
  );
}
```

**Step 2: Run and verify**

Run: `npm run dev`
Expected: App loads at `http://localhost:3000` with pin board on left, presets + generate on right.

**Step 3: Commit**

```bash
git add src/app/page.tsx
git commit -m "feat: assemble main page with board, presets, and generate panel"
```

---

## Task 10: Polish & Final Integration Testing

**Step 1: Verify full flow**

1. Open `http://localhost:3000`
2. Click Settings → add a Gemini or Anthropic API key, add GitHub token + repo
3. Add 2-3 inspiration site pins → thumbnails should appear
4. Select presets (one per category)
5. Type optional guidance in the text area
6. Click "Generate Landing Page"
7. Wait for generation → browser opens with the generated site

**Step 2: Fix any issues found during manual testing**

**Step 3: Final commit**

```bash
git add -A
git commit -m "chore: polish and finalize MVP"
```

---

## Summary: File Tree

```
pinterest_dev/
├── src/
│   ├── app/
│   │   ├── api/
│   │   │   ├── pins/
│   │   │   │   ├── route.ts          (GET, POST)
│   │   │   │   └── [id]/route.ts     (DELETE)
│   │   │   ├── screenshot/route.ts   (POST)
│   │   │   ├── settings/route.ts     (GET, PUT)
│   │   │   ├── presets/route.ts      (GET, PUT)
│   │   │   ├── github/route.ts       (POST)
│   │   │   └── generate/route.ts     (POST)
│   │   ├── globals.css
│   │   ├── layout.tsx
│   │   └── page.tsx
│   ├── components/
│   │   ├── Header.tsx
│   │   ├── SettingsPanel.tsx
│   │   ├── PinBoard.tsx
│   │   ├── PinCard.tsx
│   │   ├── AddPinModal.tsx
│   │   ├── PresetsPanel.tsx
│   │   └── GeneratePanel.tsx
│   └── lib/
│       ├── db.ts
│       ├── github.ts
│       └── generate.ts
├── data/                (SQLite, gitignored)
├── output/              (generated sites, gitignored)
├── public/thumbnails/   (screenshots, gitignored)
└── .env.example
```
