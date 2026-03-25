"use client";

import { useEffect, useState } from "react";

interface Preset {
  id: number;
  name: string;
  category: string;
  value: string;
  is_active: number;
}

export default function PresetsPanel() {
  const [presets, setPresets] = useState<Preset[]>([]);

  useEffect(() => {
    fetch("/api/presets").then((r) => r.json()).then(setPresets);
  }, []);

  const toggle = async (id: number, active: boolean) => {
    const res = await fetch("/api/presets", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, is_active: active }),
    });
    setPresets(await res.json());
  };

  const categories = [...new Set(presets.map((p) => p.category))];

  const categoryLabels: Record<string, string> = {
    style: "Style",
    layout: "Layout",
    tone: "Tone",
    framework: "Output Format",
  };

  const categoryIcons: Record<string, React.ReactNode> = {
    framework: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>,
    layout: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg>,
    style: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="13.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="10.5" r="2.5"/><circle cx="8.5" cy="7.5" r="2.5"/><circle cx="6.5" cy="12.5" r="2.5"/><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12a10 10 0 0 0 5 8.66"/></svg>,
    tone: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>,
  };

  return (
    <div className="rounded-[var(--radius-lg)] bg-[var(--surface)] p-4 shadow-[0_1px_3px_rgba(0,0,0,0.2)]">
      <div className="mb-3 flex items-center gap-2">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-[var(--text-secondary)]">
          <line x1="4" y1="21" x2="4" y2="14" /><line x1="4" y1="10" x2="4" y2="3" /><line x1="12" y1="21" x2="12" y2="12" /><line x1="12" y1="8" x2="12" y2="3" /><line x1="20" y1="21" x2="20" y2="16" /><line x1="20" y1="12" x2="20" y2="3" /><line x1="1" y1="14" x2="7" y2="14" /><line x1="9" y1="8" x2="15" y2="8" /><line x1="17" y1="16" x2="23" y2="16" />
        </svg>
        <h3 className="text-sm font-bold text-[var(--text)]">Presets</h3>
      </div>
      <div className="space-y-4">
        {categories.map((cat) => (
          <div key={cat}>
            <div className="mb-2 flex items-center gap-1.5 text-[var(--text-muted)]">
              {categoryIcons[cat]}
              <p className="text-[11px] font-semibold uppercase tracking-widest">
                {categoryLabels[cat] || cat}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {presets
                .filter((p) => p.category === cat)
                .map((p) => (
                  <button
                    key={p.id}
                    onClick={() => toggle(p.id, !p.is_active)}
                    className={`rounded-full px-3.5 py-1.5 text-xs font-medium transition-all duration-200 ${
                      p.is_active
                        ? "bg-[var(--accent)] text-white shadow-[0_2px_8px_var(--accent-glow)]"
                        : "bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text)]"
                    }`}
                  >
                    {p.name}
                  </button>
                ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
