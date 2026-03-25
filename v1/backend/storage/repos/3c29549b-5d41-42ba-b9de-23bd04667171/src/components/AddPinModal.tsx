"use client";

import { useState, useEffect, useRef } from "react";

interface Props {
  onAdd: (pin: { url: string; title: string; description: string }) => void;
  onClose: () => void;
}

export default function AddPinModal({ onAdd, onClose }: Props) {
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const submit = () => {
    if (!url.trim()) return;
    onAdd({ url: url.trim(), title: title.trim(), description: description.trim() });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-md" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-[var(--radius-xl)] bg-[var(--surface)] p-6 shadow-[0_24px_80px_rgba(0,0,0,0.5)]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-5 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[var(--accent-subtle)]">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
              <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
            </svg>
          </div>
          <div>
            <h2 className="text-lg font-bold">Add inspiration</h2>
            <p className="text-sm text-[var(--text-muted)]">Pin a website you love</p>
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-[var(--text-secondary)]">URL</label>
            <input
              ref={inputRef}
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submit()}
              placeholder="https://example.com"
              className="w-full rounded-[var(--radius-md)] border border-[var(--border-hover)] bg-[var(--bg)] px-4 py-2.5 text-sm placeholder:text-[var(--text-muted)]"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-[var(--text-secondary)]">Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="What you like about this site"
              className="w-full rounded-[var(--radius-md)] border border-[var(--border-hover)] bg-[var(--bg)] px-4 py-2.5 text-sm placeholder:text-[var(--text-muted)]"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-[var(--text-secondary)]">Notes</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Color scheme, layout, typography..."
              rows={2}
              className="w-full rounded-[var(--radius-md)] border border-[var(--border-hover)] bg-[var(--bg)] px-4 py-2.5 text-sm resize-none placeholder:text-[var(--text-muted)]"
            />
          </div>
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="rounded-full px-5 py-2.5 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-hover)]"
          >
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={!url.trim()}
            className="rounded-full bg-[var(--accent)] px-6 py-2.5 text-sm font-semibold text-white shadow-[0_2px_12px_var(--accent-glow)] transition-all hover:bg-[var(--accent-hover)] hover:shadow-[0_4px_20px_var(--accent-glow)] disabled:opacity-40 disabled:shadow-none"
          >
            Save Pin
          </button>
        </div>
      </div>
    </div>
  );
}
