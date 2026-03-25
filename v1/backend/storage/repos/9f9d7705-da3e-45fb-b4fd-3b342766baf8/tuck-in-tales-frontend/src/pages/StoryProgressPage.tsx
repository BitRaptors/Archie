import { useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { ExclamationTriangleIcon, CheckCircledIcon } from '@radix-ui/react-icons';
import { Loader2, RotateCcw } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { useStoryStream } from '@/hooks/useStoryStream';
import { api } from '@/api/client';
import type { DebugPromptEntry } from '@/models/story';

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

export default function StoryProgressPage() {
  const { storyId } = useParams<{ storyId: string }>();
  const navigate = useNavigate();
  const pageRefs = useRef<Record<number, HTMLDivElement | null>>({});

  const {
    statusMessage,
    pages,
    outlineDebug,
    outlineRawResponse,
    isComplete,
    isFailed,
    error,
    isConnected,
  } = useStoryStream(storyId);

  const [retrying, setRetrying] = useState(false);

  const handleRetry = async () => {
    if (!storyId) return;
    setRetrying(true);
    try {
      await api.retryStory(storyId);
      // Reload the page to reconnect to the SSE stream
      window.location.reload();
    } catch (err) {
      console.error('Retry failed:', err);
      setRetrying(false);
    }
  };

  const totalPages = pages.length;
  const pagesWithImage = pages.filter(p => p.imageUrl).length;
  const progressValue = totalPages > 0 ? (pagesWithImage / totalPages) * 100 : 0;

  const renderStatus = () => {
    if (isComplete) {
      return (
        <div className="flex items-center space-x-2 text-green-600">
          <CheckCircledIcon className="h-5 w-5" />
          <span className="font-semibold">Story Generation Complete!</span>
          <Button variant="link" size="sm" onClick={() => navigate(`/stories/${storyId}`)}>
            View Story
          </Button>
        </div>
      );
    }
    if (isFailed) {
      return (
        <Alert variant="destructive" className="mb-4">
          <ExclamationTriangleIcon className="h-4 w-4" />
          <AlertTitle>Generation Failed</AlertTitle>
          <AlertDescription className="flex items-center justify-between">
            <span>{error || 'An error occurred during generation.'}</span>
            <Button
              variant="outline"
              size="sm"
              disabled={retrying}
              onClick={handleRetry}
              className="ml-4 shrink-0"
            >
              {retrying ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <RotateCcw className="h-4 w-4 mr-1" />}
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      );
    }
    if (error && !isFailed) {
      return (
        <Alert variant="destructive" className="mb-4">
          <ExclamationTriangleIcon className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      );
    }

    return (
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        {isConnected && <Loader2 className="h-4 w-4 animate-spin" />}
        <span className="text-sm font-medium">{statusMessage}</span>
        {totalPages > 0 && (
          <>
            <Progress value={progressValue} className="w-full sm:w-1/3 flex-grow" />
            <span className="text-xs text-muted-foreground">{pagesWithImage} / {totalPages} Pages Complete</span>
          </>
        )}
      </div>
    );
  };

  const renderOutline = () => {
    if (pages.length === 0) return null;
    const outlinePages = pages.filter(p => p.description);
    if (outlinePages.length === 0) return null;

    return (
      <Card className="my-4 bg-muted/30">
        <CardHeader><CardTitle className="text-base">Story Outline</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <ul className="list-disc pl-5 space-y-1 text-sm">
            {outlinePages.map(page => (
              <li key={page.page}><strong>Page {page.page}:</strong> {page.description}</li>
            ))}
          </ul>
          {(outlineDebug || outlineRawResponse) && (
            <div className="mt-3 rounded-lg border border-dashed border-muted-foreground/30 bg-muted/30 p-3 space-y-3">
              {outlineDebug && <DebugPromptBlock label="Outline Generation" entry={outlineDebug} />}
              {outlineRawResponse && (
                <div className="space-y-1">
                  <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">LLM Response</h4>
                  <pre className="max-h-48 overflow-auto rounded bg-muted p-2 text-xs whitespace-pre-wrap">{outlineRawResponse}</pre>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    );
  };

  const renderPages = () => {
    if (pages.length === 0 && !isComplete) {
      return <p className="text-sm text-muted-foreground text-center my-4">Waiting for story pages...</p>;
    }

    return pages.map(page => (
      <div key={page.page} ref={el => { pageRefs.current[page.page] = el; }}>
        <Card className="my-4 overflow-hidden">
          <CardHeader>
            <CardTitle>Page {page.page}</CardTitle>
            {page.description && <CardDescription>{page.description}</CardDescription>}
          </CardHeader>
          <CardContent className="space-y-4">
            {page.text ? (
              <p className="text-sm whitespace-pre-wrap">{page.text}</p>
            ) : (
              !isComplete && !isFailed ? (
                <Skeleton className="h-20 w-full" />
              ) : (
                <p className="text-sm text-muted-foreground italic">Content generation pending or failed.</p>
              )
            )}
            {/* Debug: Characters on page */}
            {page.charactersOnPage && page.charactersOnPage.length > 0 && (
              <div className="text-xs text-muted-foreground">
                <span className="font-semibold uppercase tracking-wide">Characters:</span>{' '}
                {page.charactersOnPage.join(', ')}
              </div>
            )}
            {/* Debug: Prompts used for this page */}
            {(page.debugPrompts || page.imagePrompt) && (
              <div className="rounded-lg border border-dashed border-muted-foreground/30 bg-muted/30 p-3 space-y-3">
                {page.debugPrompts?.page_text && (
                  <DebugPromptBlock label="Page Text Generation" entry={page.debugPrompts.page_text} />
                )}
                {page.debugPrompts && Object.entries(page.debugPrompts)
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
                {page.debugPrompts?.image_prompt && (
                  <DebugPromptBlock label="Image Prompt Generation" entry={page.debugPrompts.image_prompt} />
                )}
                {page.imagePrompt && (
                  <div className="space-y-1">
                    <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Generated Image Prompt</h4>
                    <pre className="overflow-auto rounded bg-muted p-2 text-xs whitespace-pre-wrap">{page.imagePrompt}</pre>
                  </div>
                )}
                {page.avatarUrls && Object.keys(page.avatarUrls).length > 0 && (
                  <div className="space-y-1">
                    <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Reference Avatars</h4>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(page.avatarUrls).map(([name, url]) => (
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
            {page.imageUrl ? (
              <img
                src={page.imageUrl}
                alt={`Illustration for page ${page.page}`}
                className="rounded-md border aspect-video sm:aspect-square object-contain w-full max-w-md mx-auto block bg-muted"
                loading="lazy"
              />
            ) : page.text ? (
              <div className="flex justify-center">
                {!isComplete && !isFailed ? (
                  <Skeleton className="h-64 w-full max-w-md rounded-md bg-muted" />
                ) : (
                  <p className="text-sm text-muted-foreground italic">Image generation pending or failed.</p>
                )}
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>
    ));
  };

  return (
    <div className="container mx-auto p-4 max-w-3xl">
      <Card>
        <CardHeader>
          <CardTitle>Story Generation Progress</CardTitle>
          <CardDescription>Tracking story ID: {storyId || 'N/A'}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="mb-4 sticky top-16 sm:top-0 bg-background/95 backdrop-blur py-3 z-10 border-b">
            {renderStatus()}
          </div>
          {renderOutline()}
          <div className="space-y-4">
            {renderPages()}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
