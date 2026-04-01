"use client";

import { useState, useEffect } from "react";
import ClaudeTerminal from "./ClaudeTerminal";

interface GeneratePanelProps {
  onSiteReady: (siteDir: string, sessionId?: string, provider?: string) => void;
  onFileChange: () => void;
}

export default function GeneratePanel({ onSiteReady, onFileChange }: GeneratePanelProps) {
  const [prompt, setPrompt] = useState("");
  const [generating, setGenerating] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [provider, setProvider] = useState<string>("");
  const [result, setResult] = useState<{
    previewUrl: string;
    fileCount: number;
    files: string[];
    outputDir: string;
  } | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/settings")
      .then((r) => r.json())
      .then((s) => setProvider(s.ai_provider || "gemini"))
      .catch(() => {});
  }, []);

  const generate = async () => {
    setError("");
    setResult(null);

    if (provider === "claude") {
      setStreaming(true);
      return;
    }

    // Gemini path
    setGenerating(true);
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
        const dirName = data.outputDir.split("/").pop() || data.outputDir;
        onSiteReady(dirName, undefined, "gemini");
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="rounded-[var(--radius-lg)] bg-[var(--surface)] p-4 shadow-[0_1px_3px_rgba(0,0,0,0.2)]">
      <div className="mb-3 flex items-center gap-2">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-[var(--text-secondary)]">
          <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
        </svg>
        <h3 className="text-sm font-bold text-[var(--text)]">Generate</h3>
        {provider && (
          <span className="ml-auto rounded-full bg-[var(--bg-elevated)] px-2 py-0.5 text-[10px] font-medium text-[var(--text-muted)]">
            {provider}
          </span>
        )}
      </div>

      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder="Additional guidance... e.g. 'Dark theme, focus on developer experience, include code snippets'"
        rows={3}
        className="w-full rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg)] px-3.5 py-2.5 text-sm resize-none placeholder:text-[var(--text-muted)]"
      />

      <button
        onClick={generate}
        disabled={generating || streaming}
        className="mt-3 w-full rounded-full bg-[var(--accent)] py-3 text-sm font-bold text-white shadow-[0_2px_16px_var(--accent-glow)] transition-all duration-200 hover:bg-[var(--accent-hover)] hover:shadow-[0_4px_24px_var(--accent-glow)] hover:scale-[1.01] active:scale-[0.99] disabled:opacity-40 disabled:shadow-none disabled:hover:scale-100"
      >
        {generating || streaming ? (
          <span className="flex items-center justify-center gap-2">
            <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Generating...
          </span>
        ) : (
          <span className="flex items-center justify-center gap-2">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
            </svg>
            Generate Landing Page
          </span>
        )}
      </button>

      {streaming && (
        <ClaudeTerminal
          userPrompt={prompt}
          onComplete={(r) => {
            setStreaming(false);
            setResult(r);
            const dirName = r.outputDir.split("/").pop() || r.outputDir;
            onSiteReady(dirName, r.sessionId, "claude");
          }}
          onError={(msg) => {
            setStreaming(false);
            setError(msg);
          }}
          onFileChange={onFileChange}
        />
      )}

      {error && (
        <div className="mt-3 rounded-[var(--radius-md)] bg-red-500/10 p-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-3 rounded-[var(--radius-md)] bg-[var(--success-subtle)] p-3.5">
          <div className="flex items-center gap-2">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[var(--success)]/20">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--success)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </span>
            <p className="text-sm font-semibold text-[var(--success)]">Site generated!</p>
            <span className="ml-auto text-xs text-[var(--text-muted)]">{result.fileCount} files</span>
          </div>
          <div className="mt-2 flex flex-wrap gap-1">
            {result.files.map((f) => (
              <span key={f} className="rounded-full bg-[var(--bg)]/50 px-2 py-0.5 text-[10px] font-medium text-[var(--text-muted)]">
                {f}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
