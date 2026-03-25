import { NextRequest, NextResponse } from "next/server";
import puppeteer from "puppeteer";
import path from "path";
import fs from "fs";
import { getDb } from "@/lib/db";

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

    // Try networkidle2 first; fall back to domcontentloaded + delay for heavy JS sites
    try {
      await page.goto(url, { waitUntil: "networkidle2", timeout: 15000 });
    } catch {
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
      await new Promise((r) => setTimeout(r, 3000));
    }

    await page.screenshot({ path: filepath, type: "png" });
    await browser.close();

    const db = getDb();
    db.prepare("UPDATE pins SET thumbnail = ? WHERE id = ?").run(`/thumbnails/${filename}`, pinId);

    return NextResponse.json({ thumbnail: `/thumbnails/${filename}` });
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
