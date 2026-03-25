import { NextRequest } from "next/server";
import path from "path";
import fs from "fs";

const MIME_TYPES: Record<string, string> = {
  ".html": "text/html",
  ".css": "text/css",
  ".js": "application/javascript",
  ".mjs": "application/javascript",
  ".json": "application/json",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".ttf": "font/ttf",
  ".eot": "application/vnd.ms-fontobject",
  ".webp": "image/webp",
  ".mp4": "video/mp4",
  ".webm": "video/webm",
};

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const segments = (await params).path;
  if (!segments || segments.length === 0) {
    return new Response("Not found", { status: 404 });
  }

  // First segment is the site directory name, rest is the file path
  const siteDir = segments[0];
  let filePath = segments.slice(1).join("/") || "index.html";

  // Prevent directory traversal
  if (siteDir.includes("..") || filePath.includes("..")) {
    return new Response("Forbidden", { status: 403 });
  }

  const fullPath = path.join(process.cwd(), "output", siteDir, filePath);

  // If path is a directory, serve index.html from it
  if (fs.existsSync(fullPath) && fs.statSync(fullPath).isDirectory()) {
    filePath = path.join(filePath, "index.html");
    const indexPath = path.join(process.cwd(), "output", siteDir, filePath);
    if (!fs.existsSync(indexPath)) {
      return new Response("Not found", { status: 404 });
    }
    const ext = path.extname(filePath).toLowerCase();
    const contentType = MIME_TYPES[ext] || "application/octet-stream";
    const body = fs.readFileSync(indexPath);
    return new Response(body, {
      headers: {
        "Content-Type": contentType,
        "Cache-Control": "no-cache, no-store, must-revalidate",
      },
    });
  }

  if (!fs.existsSync(fullPath)) {
    return new Response("Not found", { status: 404 });
  }

  const ext = path.extname(fullPath).toLowerCase();
  const contentType = MIME_TYPES[ext] || "application/octet-stream";
  const body = fs.readFileSync(fullPath);

  return new Response(body, {
    headers: {
      "Content-Type": contentType,
      "Cache-Control": "no-cache, no-store, must-revalidate",
    },
  });
}
