"use client";

import { useEffect, useState } from "react";
import Masonry from "react-masonry-css";
import PinCard from "./PinCard";
import AddPinModal from "./AddPinModal";

interface Pin {
  id: number;
  url: string;
  title: string;
  description: string;
  thumbnail: string | null;
}

export default function PinBoard() {
  const [pins, setPins] = useState<Pin[]>([]);
  const [showAdd, setShowAdd] = useState(false);

  const fetchPins = () => {
    fetch("/api/pins").then((r) => r.json()).then(setPins);
  };

  useEffect(() => { fetchPins(); }, []);

  const addPin = async (data: { url: string; title: string; description: string }) => {
    const res = await fetch("/api/pins", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    const pin = await res.json();
    setPins((prev) => [pin, ...prev]);

    // Trigger screenshot in background
    fetch("/api/screenshot", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: data.url, pinId: pin.id }),
    })
      .then((r) => { if (r.ok) fetchPins(); })
      .catch(() => {});
  };

  const deletePin = async (id: number) => {
    await fetch(`/api/pins/${id}`, { method: "DELETE" });
    setPins((prev) => prev.filter((p) => p.id !== id));
  };

  const breakpoints = { default: 4, 1024: 3, 768: 2, 480: 1 };

  return (
    <div>
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight">Inspiration Board</h2>
          <p className="mt-0.5 text-sm text-[var(--text-muted)]">
            {pins.length > 0 ? `${pins.length} pin${pins.length === 1 ? "" : "s"} saved` : "Collect designs that inspire you"}
          </p>
        </div>
        <button
          onClick={() => setShowAdd(true)}
          className="flex items-center gap-1.5 rounded-full bg-[var(--accent)] px-5 py-2.5 text-sm font-semibold text-white shadow-[0_2px_12px_var(--accent-glow)] transition-all duration-200 hover:bg-[var(--accent-hover)] hover:shadow-[0_4px_20px_var(--accent-glow)] hover:scale-[1.02] active:scale-[0.98]"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Add Pin
        </button>
      </div>

      {pins.length === 0 ? (
        <div
          className="flex flex-col items-center justify-center rounded-[var(--radius-xl)] border-2 border-dashed border-[var(--border-hover)] py-20 transition-colors hover:border-[var(--accent)]/30 cursor-pointer"
          onClick={() => setShowAdd(true)}
        >
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-[var(--surface)]">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="1.5" strokeLinecap="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
          </div>
          <p className="mt-3 text-base font-medium text-[var(--text-secondary)]">Add your first pin</p>
          <p className="mt-1 text-sm text-[var(--text-muted)]">Save websites that inspire your landing page</p>
        </div>
      ) : (
        <Masonry
          breakpointCols={breakpoints}
          className="flex -ml-4 w-auto"
          columnClassName="pl-4 bg-clip-padding"
        >
          {pins.map((pin) => (
            <PinCard key={pin.id} pin={pin} onDelete={deletePin} />
          ))}
        </Masonry>
      )}

      {showAdd && <AddPinModal onAdd={addPin} onClose={() => setShowAdd(false)} />}
    </div>
  );
}
