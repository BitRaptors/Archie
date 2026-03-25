"use client";

import { useState } from "react";

interface PreviewFrameProps {
  siteDir: string;
  refreshTrigger: number;
}

const VIEWPORTS = [
  { label: "Desktop", width: "100%", icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg> },
  { label: "Tablet", width: "768px", icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="4" y="2" width="16" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg> },
  { label: "Mobile", width: "375px", icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="5" y="2" width="14" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg> },
] as const;

export default function PreviewFrame({ siteDir, refreshTrigger }: PreviewFrameProps) {
  const [viewport, setViewport] = useState(0);

  const src = `/api/preview/${siteDir}/?t=${refreshTrigger}`;
  const vp = VIEWPORTS[viewport];

  return (
    <div className="flex h-full flex-col bg-[var(--bg)]">
      {/* Toolbar */}
      <div className="flex items-center gap-1 border-b border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        {/* Viewport toggles */}
        <div className="flex rounded-full bg-[var(--bg-elevated)] p-0.5">
          {VIEWPORTS.map((v, i) => (
            <button
              key={v.label}
              onClick={() => setViewport(i)}
              className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-all duration-200 ${
                viewport === i
                  ? "bg-[var(--surface-hover)] text-[var(--text)] shadow-sm"
                  : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
              }`}
              title={v.label}
            >
              {v.icon}
              <span className="hidden sm:inline">{v.label}</span>
            </button>
          ))}
        </div>

        {/* URL display */}
        <div className="mx-3 flex-1 rounded-full bg-[var(--bg-elevated)] px-3 py-1.5">
          <span className="text-xs text-[var(--text-muted)] font-mono truncate block">/api/preview/{siteDir}/</span>
        </div>

        <div className="flex items-center gap-1">
          {/* Refresh */}
          <button
            onClick={() => {
              const iframe = document.querySelector<HTMLIFrameElement>("#preview-iframe");
              if (iframe) iframe.src = `/api/preview/${siteDir}/?t=${Date.now()}`;
            }}
            className="flex h-8 w-8 items-center justify-center rounded-full text-[var(--text-muted)] transition-all hover:bg-[var(--surface-hover)] hover:text-[var(--text)]"
            title="Refresh"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="23 4 23 10 17 10" />
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
            </svg>
          </button>

          {/* Open in new tab */}
          <a
            href={`/api/preview/${siteDir}/`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex h-8 w-8 items-center justify-center rounded-full text-[var(--text-muted)] transition-all hover:bg-[var(--surface-hover)] hover:text-[var(--text)]"
            title="Open in new tab"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
              <polyline points="15 3 21 3 21 9" />
              <line x1="10" y1="14" x2="21" y2="3" />
            </svg>
          </a>
        </div>
      </div>

      {/* Iframe container */}
      <div className="flex-1 flex items-start justify-center overflow-auto bg-neutral-900/50">
        <iframe
          id="preview-iframe"
          src={src}
          style={{ width: vp.width, height: "100%", maxWidth: "100%" }}
          className="bg-white transition-[width] duration-300 ease-out"
          title="Site Preview"
        />
      </div>
    </div>
  );
}
