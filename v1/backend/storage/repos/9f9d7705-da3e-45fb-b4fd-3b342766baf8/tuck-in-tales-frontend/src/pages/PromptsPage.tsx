import React, { useState, useEffect } from 'react';
import type { Prompt, PromptUpdate } from '@/models/prompt';
import { api } from '@/api/client';
import PromptEditor from '@/components/prompts/PromptEditor';
import PromptPlayground from '@/components/prompts/PromptPlayground';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { FileText } from 'lucide-react';

export default function PromptsPage() {
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadPrompts();
  }, []);

  const loadPrompts = async () => {
    setLoading(true);
    try {
      const data = await api.fetchPrompts();
      setPrompts(data);
      if (data.length > 0 && !selectedId) {
        setSelectedId(data[0].id);
      }
    } catch (err) {
      console.error('Failed to fetch prompts:', err);
      toast.error('Failed to load prompts');
    } finally {
      setLoading(false);
    }
  };

  const selectedPrompt = prompts.find((p) => p.id === selectedId) ?? null;

  const handleSave = async (update: PromptUpdate) => {
    if (!selectedPrompt) return;
    setSaving(true);
    try {
      const updated = await api.updatePrompt(selectedPrompt.slug, update);
      // Replace the old version with the new one (different ID due to versioning)
      setPrompts((prev) =>
        prev.map((p) => (p.slug === updated.slug ? updated : p))
      );
      setSelectedId(updated.id);
      toast.success('Prompt saved successfully');
    } catch (err) {
      console.error('Failed to save prompt:', err);
      toast.error('Failed to save prompt');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex h-[calc(100vh-3rem)] -m-6">
      {/* Sidebar - Prompt List */}
      <div className="w-64 border-r bg-muted/20 flex flex-col overflow-hidden">
        <div className="p-4 border-b">
          <h1 className="text-lg font-semibold">Prompts</h1>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {loading ? (
            Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))
          ) : prompts.length === 0 ? (
            <p className="text-sm text-muted-foreground p-2">No prompts found</p>
          ) : (
            prompts.map((prompt) => (
              <Button
                key={prompt.id}
                variant={selectedId === prompt.id ? 'secondary' : 'ghost'}
                className="w-full justify-start text-left h-auto py-2 px-3"
                onClick={() => setSelectedId(prompt.id)}
              >
                <div className="flex flex-col items-start gap-0.5 min-w-0">
                  <div className="flex items-center gap-2 w-full">
                    <FileText className="h-3.5 w-3.5 flex-shrink-0" />
                    <span className="text-sm font-medium truncate">{prompt.slug}</span>
                  </div>
                  <div className="flex items-center gap-1 pl-5.5">
                    <span className="text-xs text-muted-foreground">v{prompt.version}</span>
                    {prompt.is_active && (
                      <Badge variant="secondary" className="text-[10px] px-1 py-0 h-4">
                        active
                      </Badge>
                    )}
                  </div>
                </div>
              </Button>
            ))
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {loading ? (
          <div className="space-y-4">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-48 w-full" />
          </div>
        ) : selectedPrompt ? (
          <div className="max-w-4xl space-y-6">
            <PromptEditor
              prompt={selectedPrompt}
              onSave={handleSave}
              saving={saving}
            />
            <PromptPlayground prompt={selectedPrompt} />
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <p>Select a prompt from the sidebar</p>
          </div>
        )}
      </div>
    </div>
  );
}
