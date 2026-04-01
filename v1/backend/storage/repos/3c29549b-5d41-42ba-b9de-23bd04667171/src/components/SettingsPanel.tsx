"use client";

import { useEffect, useState } from "react";

interface Props {
  onClose: () => void;
}

interface HealthStatus {
  ok: boolean;
  detail: string;
}

export default function SettingsPanel({ onClose }: Props) {
  const [settings, setSettings] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [health, setHealth] = useState<Record<string, HealthStatus> | null>(null);

  useEffect(() => {
    fetch("/api/settings").then((r) => r.json()).then(setSettings);
    fetch("/api/health").then((r) => r.json()).then(setHealth);
  }, []);

  const update = (key: string, value: string) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  };

  const save = async () => {
    setSaving(true);
    await fetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    });
    setSaving(false);
    onClose();
  };

  const fields = [
    { key: "gemini_api_key", label: "Gemini API Key", type: "password" },
    { key: "ai_provider", label: "AI Provider", type: "select", options: ["gemini", "claude"] },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-md" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-[var(--radius-xl)] bg-[var(--surface)] p-6 shadow-[0_24px_80px_rgba(0,0,0,0.5)]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-5 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[var(--bg-elevated)]">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--text-secondary)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
          </div>
          <div>
            <h2 className="text-lg font-bold">Settings</h2>
            <p className="text-sm text-[var(--text-muted)]">Configure your AI providers</p>
          </div>
          <button
            onClick={onClose}
            className="ml-auto flex h-8 w-8 items-center justify-center rounded-full text-[var(--text-muted)] transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--text)]"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Provider Status */}
        <div className="mb-5 space-y-2">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-[var(--text-muted)]">Provider Status</p>
          {health === null ? (
            <div className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
              <svg className="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Checking...
            </div>
          ) : (
            <div className="space-y-2">
              <StatusRow label="Claude Code" status={health.claude} />
              <StatusRow label="Gemini API" status={health.gemini} />
            </div>
          )}
        </div>

        <div className="mb-5 border-t border-[var(--border)]" />

        <div className="space-y-4">
          {fields.map((f) => (
            <div key={f.key}>
              <label className="mb-1.5 block text-sm font-medium text-[var(--text-secondary)]">{f.label}</label>
              {f.type === "select" ? (
                <select
                  value={settings[f.key] || ""}
                  onChange={(e) => update(f.key, e.target.value)}
                  className="w-full rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg)] px-3.5 py-2.5 text-sm"
                >
                  {f.options?.map((o) => (
                    <option key={o} value={o}>{o}</option>
                  ))}
                </select>
              ) : (
                <input
                  type={f.type}
                  value={settings[f.key] || ""}
                  onChange={(e) => update(f.key, e.target.value)}
                  className="w-full rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--bg)] px-3.5 py-2.5 text-sm"
                />
              )}
            </div>
          ))}
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="rounded-full px-5 py-2.5 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-hover)]"
          >
            Cancel
          </button>
          <button
            onClick={save}
            disabled={saving}
            className="rounded-full bg-[var(--accent)] px-6 py-2.5 text-sm font-semibold text-white shadow-[0_2px_12px_var(--accent-glow)] transition-all hover:bg-[var(--accent-hover)] hover:shadow-[0_4px_20px_var(--accent-glow)] disabled:opacity-50 disabled:shadow-none"
          >
            {saving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </div>
    </div>
  );
}

function StatusRow({ label, status }: { label: string; status?: HealthStatus }) {
  if (!status) return null;
  return (
    <div className="flex items-center gap-3 rounded-[var(--radius-md)] bg-[var(--bg)] px-3.5 py-2.5">
      <span
        className={`inline-flex h-2.5 w-2.5 rounded-full ${
          status.ok ? "bg-[var(--success)] shadow-[0_0_6px_var(--success)]" : "bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.5)]"
        }`}
      />
      <span className="text-sm font-medium">{label}</span>
      <span className={`ml-auto text-xs font-medium ${status.ok ? "text-[var(--success)]" : "text-red-400"}`}>
        {status.detail}
      </span>
    </div>
  );
}
