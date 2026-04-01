import React, { useEffect, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '@/api/client';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { ExclamationTriangleIcon } from '@radix-ui/react-icons';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import type { Story, StoryPageProgress, DebugPromptEntry } from '@/models/story';
import { toast } from 'sonner';

function DebugPromptBlock({ label, entry }: { label: string; entry: DebugPromptEntry }) {
  return (
    <div className="space-y-1">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</h4>
      <div className="text-xs text-muted-foreground">
        Model: <span className="font-mono">{entry.model}</span> | Temp: {entry.temperature}
      </div>
      <details className="group">
        <summary className="cursor-pointer text-xs font-medium text-blue-600 hover:text-blue-800">System prompt</summary>
        <pre className="mt-1 max-h-48 overflow-auto rounded bg-muted p-2 text-xs whitespace-pre-wrap">{entry.system}</pre>
      </details>
      <details className="group">
        <summary className="cursor-pointer text-xs font-medium text-blue-600 hover:text-blue-800">User prompt</summary>
        <pre className="mt-1 max-h-48 overflow-auto rounded bg-muted p-2 text-xs whitespace-pre-wrap">{entry.user}</pre>
      </details>
    </div>
  );
}

function PageDebugPanel({ page, storyDebugPrompts }: { page: StoryPageProgress; storyDebugPrompts?: Record<string, DebugPromptEntry> | null }) {
  const [open, setOpen] = useState(false);
  const debugPrompts = page.debug_prompts;
  const hasDebug = debugPrompts && Object.keys(debugPrompts).length > 0;
  const showOutline = page.page === 1 && storyDebugPrompts?.outline;

  if (!hasDebug && !page.image_prompt && !showOutline) return null;

  return (
    <div className="mt-2">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setOpen(!open)}
        className="text-xs gap-1 text-muted-foreground hover:text-foreground"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 20h.01"/><path d="M8.5 21c0-2 3.5-3 3.5-5.5 0-1.5-1-2.5-2.5-2.5S7 14 7 15.5"/><circle cx="12" cy="8" r="2"/><path d="M17 3c-4 0-8 4-8 4"/><path d="M7 3c4 0 8 4 8 4"/></svg>
        {open ? 'Hide' : 'Show'} Debug
      </Button>
      {open && (
        <div className="mt-2 space-y-3 rounded-lg border border-dashed border-muted-foreground/30 bg-muted/30 p-3">
          {showOutline && storyDebugPrompts?.outline && (
            <DebugPromptBlock label="Outline (story-level)" entry={storyDebugPrompts.outline} />
          )}
          {debugPrompts?.page_text && (
            <DebugPromptBlock label="Page Text Generation" entry={debugPrompts.page_text} />
          )}
          {debugPrompts && Object.entries(debugPrompts)
            .filter(([key]) => key.startsWith('consistency_check_'))
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([key, entry]) => (
              <div key={key} className="space-y-1">
                <DebugPromptBlock label={`Consistency Check #${entry.attempt || key.split('_').pop()}`} entry={entry} />
                <div className="text-xs">
                  <span className={`font-semibold ${entry.passed ? 'text-green-600' : 'text-red-600'}`}>
                    {entry.passed ? 'PASSED' : 'FAILED'}
                  </span>
                </div>
                {entry.response && (
                  <details className="group">
                    <summary className="cursor-pointer text-xs font-medium text-blue-600 hover:text-blue-800">LLM Response</summary>
                    <pre className="mt-1 max-h-48 overflow-auto rounded bg-muted p-2 text-xs whitespace-pre-wrap">{entry.response}</pre>
                  </details>
                )}
              </div>
            ))
          }
          {debugPrompts?.image_prompt && (
            <DebugPromptBlock label="Image Prompt Generation" entry={debugPrompts.image_prompt} />
          )}
          {page.image_prompt && (
            <div className="space-y-1">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Generated Image Prompt</h4>
              <pre className="overflow-auto rounded bg-muted p-2 text-xs whitespace-pre-wrap">{page.image_prompt}</pre>
            </div>
          )}
          {page.characters_on_page && page.characters_on_page.length > 0 && (
            <div className="space-y-1">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Characters on page</h4>
              <p className="text-xs">{page.characters_on_page.join(', ')}</p>
            </div>
          )}
          {page.avatar_urls && Object.keys(page.avatar_urls).length > 0 && (
            <div className="space-y-1">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Reference Avatars</h4>
              <div className="flex flex-wrap gap-2">
                {Object.entries(page.avatar_urls).map(([name, url]) => (
                  <div key={name} className="flex flex-col items-center gap-1">
                    <img src={url} alt={name} className="h-12 w-12 rounded-full object-cover border bg-muted" />
                    <span className="text-[10px] text-muted-foreground">{name}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function StoryViewerPage() {
  console.log("%%% StoryViewerPage Mounted %%%");
  const { storyId } = useParams<{ storyId: string }>();
  const [story, setStory] = useState<Story | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStory = useCallback(async () => {
    if (!storyId) return;
    console.log(`Fetching story ${storyId}...`);
    setLoading(true);
    setError(null);
    try {
      const data = await api.fetchStory(storyId);
      setStory(data);
    } catch (err: any) {
      console.error("Error fetching story:", err);
      setError(err.message || 'Failed to load story.');
      toast.error("Failed to load story details.");
    } finally {
      setLoading(false);
    }
  }, [storyId]);

  useEffect(() => {
    fetchStory();
  }, [fetchStory]);

  if (loading) {
    return (
      <div className="container mx-auto p-4 space-y-4">
        <Skeleton className="h-8 w-3/4 mb-4" />
        <div className="space-y-6">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="flex flex-col md:flex-row gap-4 items-center">
              <Skeleton className="h-40 w-full md:w-1/3 aspect-square" />
              <Skeleton className="h-20 w-full md:w-2/3" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto p-4">
        <Alert variant="destructive">
          <ExclamationTriangleIcon className="h-4 w-4" />
          <AlertTitle>Error Loading Story</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </div>
    );
  }

  if (!story) {
    return <div className="container mx-auto p-4">Story not found.</div>;
  }

  return (
    <div className="container mx-auto p-4 max-w-4xl">
      <h1 className="text-3xl font-bold mb-6 text-center">{story.title}</h1>

      <div className="space-y-8">
        {story.pages.map((page: StoryPageProgress, index) => (
          <Card key={index} className="overflow-hidden">
            <CardContent className="p-4 md:p-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6 items-center">
                <div className="order-1">
                  {page.image_url ? (
                    <img
                      src={page.image_url}
                      alt={`Illustration for page ${index + 1}`}
                      className="rounded-lg object-cover aspect-square w-full bg-muted"
                    />
                  ) : (
                    <div className="rounded-lg aspect-square w-full bg-muted flex items-center justify-center">
                      <p className="text-sm text-muted-foreground">(No image generated for this page)</p>
                    </div>
                  )}
                </div>
                <div className="order-2">
                  <p className="text-base leading-relaxed">{page.text}</p>
                </div>
              </div>
              <PageDebugPanel page={page} storyDebugPrompts={story.debug_prompts} />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}