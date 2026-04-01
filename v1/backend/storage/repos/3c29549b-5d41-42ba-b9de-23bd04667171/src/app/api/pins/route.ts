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
