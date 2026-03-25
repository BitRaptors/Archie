import { getDb } from "@/lib/db";
import { NextRequest, NextResponse } from "next/server";

export async function DELETE(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const db = getDb();
  db.prepare("DELETE FROM pins WHERE id = ?").run(id);
  return NextResponse.json({ ok: true });
}
