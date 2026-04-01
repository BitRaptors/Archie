"use client";

import { useEffect, useState } from "react";

interface RepoContent {
  name: string;
  description: string;
  language: string;
  topics: string[];
  stars: number;
  readme: string;
  packageJson: string;
  fileTree: string[];
}

export default function GitHubPanel() {
  const [repoUrl, setRepoUrl] = useState("");
  const [token, setToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [repo, setRepo] = useState<RepoContent | null>(null);
  const [showReadme, setShowReadme] = useState(false);

  useEffect(() => {
    fetch("/api/settings")
      .then((r) => r.json())
      .then((s: Record<string, string>) => {
        if (s.github_repo) setRepoUrl(s.github_repo);
        if (s.github_token) setToken(s.github_token);
      });
  }, []);

  const connect = async () => {
    if (!repoUrl.trim()) return;
    setLoading(true);
    setError("");
    setRepo(null);

    await fetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ github_repo: repoUrl.trim(), github_token: token }),
    });

    try {
      const res = await fetch("/api/github", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repoUrl: repoUrl.trim() }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Failed to fetch repo");
      } else {
        setRepo(data);
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const disconnect = async () => {
    setRepo(null);
    setRepoUrl("");
    await fetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ github_repo: "" }),
    });
  };

  return (
    <div className="rounded-[var(--radius-lg)] bg-[var(--surface)] p-4 shadow-[0_1px_3px_rgba(0,0,0,0.2)]">
      <div className="mb-3 flex items-center gap-2">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" className="text-[var(--text-secondary)]">
          <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
        </svg>
        <h3 className="text-sm font-bold text-[var(--text)]">GitHub Source</h3>
      </div>

      {repo ? (
        <div>
          <div className="rounded-[var(--radius-md)] bg-[var(--success-subtle)] p-3.5">
            <div className="flex items-start justify-between">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-bold truncate">{repo.name}</p>
                  <span className="inline-flex h-2 w-2 rounded-full bg-[var(--success)]" />
                </div>
                {repo.description && (
                  <p className="mt-1 text-xs leading-relaxed text-[var(--text-secondary)] line-clamp-2">{repo.description}</p>
                )}
              </div>
            </div>
            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {repo.language && (
                <span className="rounded-full bg-[var(--bg)]/60 px-2.5 py-0.5 text-[10px] font-medium text-[var(--text-secondary)]">
                  {repo.language}
                </span>
              )}
              {repo.stars > 0 && (
                <span className="flex items-center gap-1 rounded-full bg-[var(--bg)]/60 px-2.5 py-0.5 text-[10px] font-medium text-[var(--text-secondary)]">
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
                  {repo.stars.toLocaleString()}
                </span>
              )}
              {repo.topics.slice(0, 3).map((t) => (
                <span key={t} className="rounded-full bg-[var(--bg)]/60 px-2.5 py-0.5 text-[10px] font-medium text-[var(--text-secondary)]">
                  {t}
                </span>
              ))}
            </div>
          </div>

          <div className="mt-3 space-y-1.5">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-muted)]">AI context</p>
            <div className="flex flex-wrap gap-1.5">
              {repo.readme && (
                <button
                  onClick={() => setShowReadme(!showReadme)}
                  className="flex items-center gap-1 rounded-full bg-[var(--bg-elevated)] px-2.5 py-1 text-[11px] font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--text)]"
                >
                  README
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className={`transition-transform ${showReadme ? "rotate-180" : ""}`}>
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </button>
              )}
              {repo.packageJson && (
                <span className="rounded-full bg-[var(--bg-elevated)] px-2.5 py-1 text-[11px] font-medium text-[var(--text-secondary)]">
                  package.json
                </span>
              )}
              <span className="rounded-full bg-[var(--bg-elevated)] px-2.5 py-1 text-[11px] font-medium text-[var(--text-secondary)]">
                {repo.fileTree.length} files
              </span>
            </div>
          </div>

          {showReadme && repo.readme && (
            <pre className="mt-2 max-h-40 overflow-auto rounded-[var(--radius-md)] bg-[var(--bg)] p-3 text-[11px] leading-relaxed text-[var(--text-muted)] whitespace-pre-wrap">
              {repo.readme.slice(0, 2000)}
              {repo.readme.length > 2000 && "\n..."}
            </pre>
          )}

          <button
            onClick={disconnect}
            className="mt-3 w-full rounded-full border border-[var(--border)] py-2 text-xs font-medium text-[var(--text-muted)] transition-all hover:border-red-500/30 hover:text-red-400 hover:bg-red-500/5"
          >
            Disconnect
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">Repository</label>
            <input
              type="text"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              placeholder="https://github.com/owner/repo"
              className="w-full rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg)] px-3.5 py-2.5 text-sm placeholder:text-[var(--text-muted)]"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">Token</label>
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="ghp_..."
              className="w-full rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg)] px-3.5 py-2.5 text-sm placeholder:text-[var(--text-muted)]"
            />
          </div>

          {error && (
            <div className="rounded-[var(--radius-md)] bg-red-500/10 p-3 text-xs text-red-400">
              {error}
            </div>
          )}

          <button
            onClick={connect}
            disabled={loading || !repoUrl.trim()}
            className="w-full rounded-full bg-[var(--accent)] py-2.5 text-sm font-semibold text-white shadow-[0_2px_12px_var(--accent-glow)] transition-all hover:bg-[var(--accent-hover)] hover:shadow-[0_4px_20px_var(--accent-glow)] disabled:opacity-40 disabled:shadow-none"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Connecting...
              </span>
            ) : "Connect & Fetch"}
          </button>
          <p className="text-[11px] leading-relaxed text-[var(--text-muted)]">
            Token is optional for public repos. Content is used as marketing source for AI generation.
          </p>
        </div>
      )}
    </div>
  );
}
