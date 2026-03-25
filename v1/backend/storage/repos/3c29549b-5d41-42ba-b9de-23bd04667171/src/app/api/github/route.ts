import { getDb } from "@/lib/db";
import { getRepoContent } from "@/lib/github";
import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  const { repoUrl } = await req.json();
  const db = getDb();
  const settings = db.prepare("SELECT value FROM settings WHERE key = 'github_token'").get() as
    | { value: string }
    | undefined;
  const token = settings?.value || null;
  try {
    const content = await getRepoContent(token, repoUrl);
    return NextResponse.json(content);
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
