import React, { useState, useEffect, useRef, useCallback } from 'react';
import type { Prompt, PromptUpdate } from '@/models/prompt';
import { PROMPT_VARIABLES, AVAILABLE_PROVIDERS, AVAILABLE_MODELS } from '@/lib/promptVariables';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Save } from 'lucide-react';

interface PromptEditorProps {
  prompt: Prompt;
  onSave: (update: PromptUpdate) => Promise<void>;
  saving: boolean;
}

interface MentionState {
  active: boolean;
  query: string;
  field: 'system_prompt' | 'user_prompt';
  startPos: number;
}

function renderHighlightedText(text: string, variables: string[]): React.ReactNode {
  if (!variables.length) return text;

  const pattern = new RegExp(`@(${variables.join('|')})`, 'g');
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    parts.push(
      <span
        key={`${match.index}-${match[1]}`}
        className="bg-blue-100 text-blue-800 px-1 rounded text-sm font-mono"
      >
        @{match[1]}
      </span>
    );
    lastIndex = pattern.lastIndex;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts;
}

export default function PromptEditor({ prompt, onSave, saving }: PromptEditorProps) {
  const [name, setName] = useState(prompt.name);
  const [description, setDescription] = useState(prompt.description ?? '');
  const [provider, setProvider] = useState(prompt.provider);
  const [model, setModel] = useState(prompt.model);
  const [temperature, setTemperature] = useState<string>(
    prompt.temperature !== null ? String(prompt.temperature) : ''
  );
  const [maxTokens, setMaxTokens] = useState<string>(
    prompt.max_tokens !== null ? String(prompt.max_tokens) : ''
  );
  const [systemPrompt, setSystemPrompt] = useState(prompt.system_prompt);
  const [userPrompt, setUserPrompt] = useState(prompt.user_prompt);
  const [mention, setMention] = useState<MentionState>({
    active: false,
    query: '',
    field: 'system_prompt',
    startPos: 0,
  });

  const systemRef = useRef<HTMLTextAreaElement>(null);
  const userRef = useRef<HTMLTextAreaElement>(null);

  const slugVariables = PROMPT_VARIABLES[prompt.slug] ?? [];
  const variableNames = slugVariables.map((v) => v.name);

  // Reset form when prompt changes
  useEffect(() => {
    setName(prompt.name);
    setDescription(prompt.description ?? '');
    setProvider(prompt.provider);
    setModel(prompt.model);
    setTemperature(prompt.temperature !== null ? String(prompt.temperature) : '');
    setMaxTokens(prompt.max_tokens !== null ? String(prompt.max_tokens) : '');
    setSystemPrompt(prompt.system_prompt);
    setUserPrompt(prompt.user_prompt);
    setMention({ active: false, query: '', field: 'system_prompt', startPos: 0 });
  }, [prompt.id]);

  // Reset model when provider changes (if current model is not in new provider)
  useEffect(() => {
    const models = AVAILABLE_MODELS[provider] ?? [];
    if (!models.find((m) => m.value === model)) {
      setModel(models[0]?.value ?? '');
    }
  }, [provider]);

  const filteredVariables = mention.active
    ? variableNames.filter((v) =>
        v.toLowerCase().includes(mention.query.toLowerCase())
      )
    : [];

  const handleTextareaChange = useCallback(
    (
      value: string,
      field: 'system_prompt' | 'user_prompt',
      setter: (val: string) => void,
      ref: React.RefObject<HTMLTextAreaElement | null>
    ) => {
      setter(value);
      const textarea = ref.current;
      if (!textarea) return;

      const cursorPos = textarea.selectionStart;
      // Look backwards from cursor for an @
      const textBeforeCursor = value.slice(0, cursorPos);
      const atIndex = textBeforeCursor.lastIndexOf('@');

      if (atIndex >= 0) {
        const textAfterAt = textBeforeCursor.slice(atIndex + 1);
        // Only show menu if there's no space after @ (user is still typing the variable name)
        if (!textAfterAt.includes(' ') && !textAfterAt.includes('\n')) {
          setMention({
            active: true,
            query: textAfterAt,
            field,
            startPos: atIndex,
          });
          return;
        }
      }
      setMention((prev) => ({ ...prev, active: false }));
    },
    []
  );

  const insertVariable = useCallback(
    (varName: string) => {
      const ref = mention.field === 'system_prompt' ? systemRef : userRef;
      const setter = mention.field === 'system_prompt' ? setSystemPrompt : setUserPrompt;
      const currentValue = mention.field === 'system_prompt' ? systemPrompt : userPrompt;

      const textarea = ref.current;
      if (!textarea) return;

      const before = currentValue.slice(0, mention.startPos);
      const cursorPos = textarea.selectionStart;
      const after = currentValue.slice(cursorPos);
      const newValue = `${before}@${varName}${after}`;

      setter(newValue);
      setMention({ active: false, query: '', field: mention.field, startPos: 0 });

      // Restore focus and cursor
      requestAnimationFrame(() => {
        textarea.focus();
        const newCursorPos = before.length + varName.length + 1;
        textarea.setSelectionRange(newCursorPos, newCursorPos);
      });
    },
    [mention, systemPrompt, userPrompt]
  );

  const handleSave = async () => {
    const update: PromptUpdate = {
      name,
      description: description || null,
      system_prompt: systemPrompt,
      user_prompt: userPrompt,
      provider,
      model,
      temperature: temperature !== '' ? parseFloat(temperature) : null,
      max_tokens: maxTokens !== '' ? parseInt(maxTokens, 10) : null,
      available_variables: variableNames,
    };
    await onSave(update);
  };

  const models = AVAILABLE_MODELS[provider] ?? [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">{prompt.slug}</h2>
          <p className="text-sm text-muted-foreground">
            Version {prompt.version} {prompt.is_active && '(active)'}
          </p>
        </div>
        <Button onClick={handleSave} disabled={saving}>
          <Save className="mr-2 h-4 w-4" />
          {saving ? 'Saving...' : 'Save Changes'}
        </Button>
      </div>

      {/* Name & Description */}
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="prompt-name">Name</Label>
          <Input
            id="prompt-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Prompt name"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="prompt-description">Description</Label>
          <Input
            id="prompt-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optional description"
          />
        </div>
      </div>

      {/* Provider, Model, Temperature, Max Tokens */}
      <div className="grid grid-cols-4 gap-4">
        <div className="space-y-2">
          <Label>Provider</Label>
          <Select value={provider} onValueChange={setProvider}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {AVAILABLE_PROVIDERS.map((p) => (
                <SelectItem key={p.value} value={p.value}>
                  {p.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>Model</Label>
          <Select value={model} onValueChange={setModel}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {models.map((m) => (
                <SelectItem key={m.value} value={m.value}>
                  {m.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="temperature">Temperature</Label>
          <Input
            id="temperature"
            type="number"
            min={0}
            max={2}
            step={0.1}
            value={temperature}
            onChange={(e) => setTemperature(e.target.value)}
            placeholder="0.0 - 2.0"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="max-tokens">Max Tokens</Label>
          <Input
            id="max-tokens"
            type="number"
            min={1}
            value={maxTokens}
            onChange={(e) => setMaxTokens(e.target.value)}
            placeholder="e.g. 4096"
          />
        </div>
      </div>

      {/* System Prompt */}
      <div className="space-y-2 relative">
        <Label htmlFor="system-prompt">System Prompt</Label>
        <Textarea
          ref={systemRef}
          id="system-prompt"
          value={systemPrompt}
          onChange={(e) =>
            handleTextareaChange(e.target.value, 'system_prompt', setSystemPrompt, systemRef)
          }
          className="min-h-[200px] font-mono text-sm"
          placeholder="Enter system prompt... Use @variable_name for variables"
        />
        {mention.active && mention.field === 'system_prompt' && filteredVariables.length > 0 && (
          <div className="absolute z-50 mt-1 w-72 bg-popover border rounded-md shadow-lg p-1 max-h-48 overflow-y-auto">
            {filteredVariables.map((v) => (
              <button
                key={v}
                type="button"
                className="w-full text-left px-3 py-1.5 text-sm rounded hover:bg-accent hover:text-accent-foreground font-mono"
                onMouseDown={(e) => {
                  e.preventDefault();
                  insertVariable(v);
                }}
              >
                @{v}
              </button>
            ))}
          </div>
        )}
        <div className="p-3 bg-muted/50 rounded-md text-sm whitespace-pre-wrap min-h-[60px]">
          {renderHighlightedText(systemPrompt, variableNames)}
        </div>
      </div>

      {/* User Prompt */}
      <div className="space-y-2 relative">
        <Label htmlFor="user-prompt">User Prompt</Label>
        <Textarea
          ref={userRef}
          id="user-prompt"
          value={userPrompt}
          onChange={(e) =>
            handleTextareaChange(e.target.value, 'user_prompt', setUserPrompt, userRef)
          }
          className="min-h-[200px] font-mono text-sm"
          placeholder="Enter user prompt... Use @variable_name for variables"
        />
        {mention.active && mention.field === 'user_prompt' && filteredVariables.length > 0 && (
          <div className="absolute z-50 mt-1 w-72 bg-popover border rounded-md shadow-lg p-1 max-h-48 overflow-y-auto">
            {filteredVariables.map((v) => (
              <button
                key={v}
                type="button"
                className="w-full text-left px-3 py-1.5 text-sm rounded hover:bg-accent hover:text-accent-foreground font-mono"
                onMouseDown={(e) => {
                  e.preventDefault();
                  insertVariable(v);
                }}
              >
                @{v}
              </button>
            ))}
          </div>
        )}
        <div className="p-3 bg-muted/50 rounded-md text-sm whitespace-pre-wrap min-h-[60px]">
          {renderHighlightedText(userPrompt, variableNames)}
        </div>
      </div>

      {/* Available Variables */}
      {slugVariables.length > 0 && (
        <div className="space-y-2">
          <Label>Available Variables for "{prompt.slug}"</Label>
          <div className="flex flex-wrap gap-2">
            {slugVariables.map((v) => (
              <Badge
                key={v.name}
                variant="secondary"
                className="cursor-help font-mono text-xs"
                title={`${v.description}\nSample: ${v.sample}`}
              >
                @{v.name}
              </Badge>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
