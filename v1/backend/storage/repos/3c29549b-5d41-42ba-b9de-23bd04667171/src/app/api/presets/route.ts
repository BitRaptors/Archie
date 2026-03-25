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
  const preset = db.prepare("SELECT category FROM presets WHERE id = ?").get(id) as { category: string } | undefined;
  if (preset) {
    db.prepare("UPDATE presets SET is_active = 0 WHERE category = ?").run(preset.category);
  }
  db.prepare("UPDATE presets SET is_active = ? WHERE id = ?").run(is_active ? 1 : 0, id);
  const all = db.prepare("SELECT * FROM presets ORDER BY category, name").all();
  return NextResponse.json(all);
}
