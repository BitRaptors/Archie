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
    { name: "Minimal", category: "style", value: "Clean, minimal design with lots of whitespace. Simple typography." },
    { name: "Bold & Vibrant", category: "style", value: "Bold colors, large typography, energetic feel." },
    { name: "Corporate", category: "style", value: "Professional, trustworthy, clean layout with subtle colors." },
    { name: "Startup", category: "style", value: "Modern, gradient backgrounds, rounded cards, friendly tone." },
    { name: "Hero + Features", category: "layout", value: "Large hero section, then feature grid, then CTA." },
    { name: "Story Flow", category: "layout", value: "Narrative scroll: problem, solution, how it works, testimonials, CTA." },
    { name: "Product Focus", category: "layout", value: "Product screenshot hero, benefits sidebar, comparison table, pricing." },
    { name: "Professional", category: "tone", value: "Formal, authoritative, data-driven language." },
    { name: "Casual & Friendly", category: "tone", value: "Conversational, approachable, uses 'you' language." },
    { name: "Technical", category: "tone", value: "Developer-focused, precise, shows code examples." },
    { name: "Plain HTML/CSS", category: "framework", value: "Single index.html with inline CSS and vanilla JS." },
    { name: "Tailwind", category: "framework", value: "Single HTML file using Tailwind CSS via CDN." },
    { name: "React (Vite)", category: "framework", value: "Vite + React project with Tailwind." },
  ];

  const insert = db.prepare("INSERT INTO presets (name, category, value) VALUES (?, ?, ?)");
  for (const p of presets) {
    insert.run(p.name, p.category, p.value);
  }
}
