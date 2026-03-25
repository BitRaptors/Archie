"use client";

interface Pin {
  id: number;
  url: string;
  title: string;
  description: string;
  thumbnail: string | null;
}

interface Props {
  pin: Pin;
  onDelete: (id: number) => void;
}

export default function PinCard({ pin, onDelete }: Props) {
  return (
    <div className="group relative mb-4 break-inside-avoid overflow-hidden rounded-[var(--radius-lg)] bg-[var(--surface)] shadow-[0_1px_3px_rgba(0,0,0,0.3)] transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_8px_30px_rgba(0,0,0,0.4)]">
      {/* Image / placeholder */}
      <div className="relative overflow-hidden">
        {pin.thumbnail ? (
          <>
            <img
              src={pin.thumbnail}
              alt={pin.title || pin.url}
              className="w-full object-cover transition-transform duration-500 group-hover:scale-105"
              loading="lazy"
            />
            {/* Hover overlay */}
            <div className="absolute inset-0 bg-black/0 transition-colors duration-300 group-hover:bg-black/20" />
          </>
        ) : (
          <div className="flex h-44 items-center justify-center bg-[var(--bg-elevated)]">
            <div className="flex flex-col items-center gap-2">
              <div className="h-8 w-8 animate-pulse rounded-full bg-[var(--surface-hover)]" />
              <span className="text-xs text-[var(--text-muted)] animate-pulse">Capturing...</span>
            </div>
          </div>
        )}

        {/* Delete button — appears on hover */}
        <button
          onClick={() => onDelete(pin.id)}
          className="absolute right-2 top-2 flex h-8 w-8 items-center justify-center rounded-full bg-black/70 text-white opacity-0 backdrop-blur-sm transition-all duration-200 hover:bg-[var(--accent)] hover:scale-110 group-hover:opacity-100"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>

        {/* Save-style button — Pinterest feel */}
        <div className="absolute bottom-2 right-2 opacity-0 transition-all duration-200 group-hover:opacity-100">
          <a
            href={pin.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 rounded-full bg-white/90 px-3 py-1.5 text-[11px] font-semibold text-gray-900 shadow-lg backdrop-blur-sm transition-all hover:bg-white hover:scale-105"
          >
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
              <polyline points="15 3 21 3 21 9" />
              <line x1="10" y1="14" x2="21" y2="3" />
            </svg>
            Visit
          </a>
        </div>
      </div>

      {/* Content */}
      <div className="p-3">
        {pin.title && (
          <h3 className="text-sm font-semibold leading-snug text-[var(--text)]">{pin.title}</h3>
        )}
        <p className="mt-0.5 text-xs text-[var(--text-muted)] truncate">{new URL(pin.url).hostname}</p>
        {pin.description && (
          <p className="mt-1.5 text-xs leading-relaxed text-[var(--text-secondary)] line-clamp-2">{pin.description}</p>
        )}
      </div>
    </div>
  );
}
