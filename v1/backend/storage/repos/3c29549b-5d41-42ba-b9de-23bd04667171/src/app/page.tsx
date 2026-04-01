"use client";

import { useState, useCallback, useEffect } from "react";
import PinBoard from "@/components/PinBoard";
import GitHubPanel from "@/components/GitHubPanel";
import PresetsPanel from "@/components/PresetsPanel";
import GeneratePanel from "@/components/GeneratePanel";
import PreviewFrame from "@/components/PreviewFrame";
import RefinementChat from "@/components/RefinementChat";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

function loadSession(): { siteDir: string | null; sessionId?: string; provider: string } {
  if (typeof window === "undefined") return { siteDir: null, provider: "gemini" };
  try {
    const saved = sessionStorage.getItem("pinlaunch_session");
    if (saved) return JSON.parse(saved);
  } catch {}
  return { siteDir: null, provider: "gemini" };
}

export default function Home() {
  const [siteDir, setSiteDir] = useState<string | null>(() => loadSession().siteDir);
  const [sessionId, setSessionId] = useState<string | undefined>(() => loadSession().sessionId);
  const [provider, setProvider] = useState<string>(() => loadSession().provider);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [refinementMessages, setRefinementMessages] = useState<ChatMessage[]>([]);

  // Persist session to sessionStorage
  useEffect(() => {
    try {
      sessionStorage.setItem("pinlaunch_session", JSON.stringify({ siteDir, sessionId, provider }));
    } catch {}
  }, [siteDir, sessionId, provider]);

  const handleSiteReady = useCallback((dir: string, sid?: string, prov?: string) => {
    setSiteDir(dir);
    setSessionId(sid);
    if (prov) setProvider(prov);
    setRefreshTrigger((n) => n + 1);
    setRefinementMessages([]);
  }, []);

  const handleFileChange = useCallback(() => {
    setRefreshTrigger((n) => n + 1);
  }, []);

  const handleRefinementMessage = useCallback((msg: ChatMessage) => {
    setRefinementMessages((prev) => [...prev, msg]);
  }, []);

  // Setup mode
  if (!siteDir) {
    return (
      <div className="mx-auto max-w-[1400px]">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_340px]">
          <div>
            <PinBoard />
          </div>
          <div className="space-y-4">
            <GitHubPanel />
            <PresetsPanel />
            <GeneratePanel onSiteReady={handleSiteReady} onFileChange={handleFileChange} />
          </div>
        </div>
      </div>
    );
  }

  // Preview mode
  return (
    <div className="flex gap-5" style={{ height: "calc(100vh - 90px)" }}>
      {/* Left panel */}
      <div className="w-[380px] shrink-0 overflow-y-auto space-y-4 pr-1">
        <PinBoard />
        <GitHubPanel />
        <PresetsPanel />
        <GeneratePanel onSiteReady={handleSiteReady} onFileChange={handleFileChange} />
        <RefinementChat
          siteDir={siteDir}
          sessionId={sessionId}
          provider={provider}
          messages={refinementMessages}
          onMessage={handleRefinementMessage}
          onFileChange={handleFileChange}
        />
      </div>

      {/* Right panel — preview */}
      <div className="flex-1 rounded-[var(--radius-lg)] border border-[var(--border)] overflow-hidden shadow-[0_4px_24px_rgba(0,0,0,0.3)]">
        <PreviewFrame siteDir={siteDir} refreshTrigger={refreshTrigger} />
      </div>
    </div>
  );
}
