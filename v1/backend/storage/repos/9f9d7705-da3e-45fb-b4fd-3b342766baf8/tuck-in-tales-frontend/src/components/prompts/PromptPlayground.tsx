import React, { useState, useEffect } from 'react';
import type { Prompt, PromptTestRequest, PromptTestResponse } from '@/models/prompt';
import { PROMPT_VARIABLES } from '@/lib/promptVariables';
import { api } from '@/api/client';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { ChevronDown, ChevronRight, Play, Loader2 } from 'lucide-react';

interface PromptPlaygroundProps {
  prompt: Prompt;
}

function substituteVariables(template: string, values: Record<string, string>): string {
  let result = template;
  for (const [key, value] of Object.entries(values)) {
    result = result.replaceAll(`@${key}`, value);
  }
  return result;
}

export default function PromptPlayground({ prompt }: PromptPlaygroundProps) {
  const [expanded, setExpanded] = useState(false);
  const [variableValues, setVariableValues] = useState<Record<string, string>>({});
  const [testResult, setTestResult] = useState<PromptTestResponse | null>(null);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const slugVariables = PROMPT_VARIABLES[prompt.slug] ?? [];

  // Reset variable values when prompt changes
  useEffect(() => {
    const defaults: Record<string, string> = {};
    for (const v of slugVariables) {
      defaults[v.name] = v.sample;
    }
    setVariableValues(defaults);
    setTestResult(null);
    setError(null);
  }, [prompt.id, prompt.slug]);

  const renderedSystemPrompt = substituteVariables(prompt.system_prompt, variableValues);
  const renderedUserPrompt = substituteVariables(prompt.user_prompt, variableValues);

  const handleTest = async () => {
    setTesting(true);
    setError(null);
    setTestResult(null);

    const request: PromptTestRequest = {
      system_prompt: renderedSystemPrompt,
      user_prompt: renderedUserPrompt,
      provider: prompt.provider,
      model: prompt.model,
      temperature: prompt.temperature ?? undefined,
      max_tokens: prompt.max_tokens,
    };

    try {
      const result = await api.testPrompt(request);
      setTestResult(result);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Test failed';
      setError(message);
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="border rounded-lg">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 hover:bg-muted/50 transition-colors"
      >
        <span className="font-semibold text-sm">Test Prompt</span>
        {expanded ? (
          <ChevronDown className="h-4 w-4" />
        ) : (
          <ChevronRight className="h-4 w-4" />
        )}
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-4 border-t pt-4">
          {/* Variable Inputs */}
          {slugVariables.length > 0 && (
            <div className="space-y-3">
              <Label className="text-sm font-medium">Variable Values</Label>
              <div className="grid grid-cols-1 gap-3">
                {slugVariables.map((v) => (
                  <div key={v.name} className="space-y-1">
                    <Label htmlFor={`var-${v.name}`} className="text-xs font-mono text-muted-foreground">
                      @{v.name} - {v.description}
                    </Label>
                    <Input
                      id={`var-${v.name}`}
                      value={variableValues[v.name] ?? ''}
                      onChange={(e) =>
                        setVariableValues((prev) => ({
                          ...prev,
                          [v.name]: e.target.value,
                        }))
                      }
                      className="font-mono text-sm"
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Rendered Previews */}
          <div className="space-y-3">
            <Label className="text-sm font-medium">Rendered System Prompt</Label>
            <pre className="p-3 bg-muted/50 rounded-md text-xs font-mono whitespace-pre-wrap max-h-48 overflow-y-auto">
              {renderedSystemPrompt}
            </pre>
          </div>

          <div className="space-y-3">
            <Label className="text-sm font-medium">Rendered User Prompt</Label>
            <pre className="p-3 bg-muted/50 rounded-md text-xs font-mono whitespace-pre-wrap max-h-48 overflow-y-auto">
              {renderedUserPrompt}
            </pre>
          </div>

          {/* Run Test Button */}
          <Button onClick={handleTest} disabled={testing} className="w-full">
            {testing ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Running...
              </>
            ) : (
              <>
                <Play className="mr-2 h-4 w-4" />
                Run Test
              </>
            )}
          </Button>

          {/* Error */}
          {error && (
            <div className="p-3 bg-destructive/10 text-destructive rounded-md text-sm">
              {error}
            </div>
          )}

          {/* Result */}
          {testResult && (
            <div className="space-y-2">
              <Label className="text-sm font-medium">
                Result ({testResult.provider} / {testResult.model})
              </Label>
              <pre className="p-3 bg-muted rounded-md text-xs font-mono whitespace-pre-wrap max-h-96 overflow-y-auto">
                {testResult.response}
              </pre>
              {testResult.usage && (
                <p className="text-xs text-muted-foreground">
                  Usage: {JSON.stringify(testResult.usage)}
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
