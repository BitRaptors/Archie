import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Textarea } from '@/components/ui/textarea';
import { Avatar, AvatarImage, AvatarFallback } from '@/components/ui/avatar';
import { getPublicAvatarUrl } from '@/utils/supabaseUtils';
import { cn } from '@/lib/utils';
import type { Character } from '@/models/character';

interface MentionInputProps {
  value: string;
  onChange: (value: string) => void;
  characters: Character[];
  placeholder?: string;
  rows?: number;
  className?: string;
}

export default function MentionInput({
  value,
  onChange,
  characters,
  placeholder,
  rows = 3,
  className,
}: MentionInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const [showDropdown, setShowDropdown] = useState(false);
  const [mentionFilter, setMentionFilter] = useState('');
  const [mentionStart, setMentionStart] = useState(-1);
  const [selectedIndex, setSelectedIndex] = useState(0);

  const filteredChars = characters.filter(c =>
    c.name.toLowerCase().includes(mentionFilter.toLowerCase())
  );

  // Detect @ trigger
  const handleChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newValue = e.target.value;
    const cursorPos = e.target.selectionStart || 0;
    onChange(newValue);

    // Check if we're in a mention context
    const textBeforeCursor = newValue.slice(0, cursorPos);
    const lastAt = textBeforeCursor.lastIndexOf('@');

    if (lastAt !== -1) {
      const textAfterAt = textBeforeCursor.slice(lastAt + 1);
      // Only show dropdown if no space before @ (or start of text) and no closing }
      const charBeforeAt = lastAt > 0 ? newValue[lastAt - 1] : ' ';
      if ((charBeforeAt === ' ' || charBeforeAt === '\n' || lastAt === 0) && !textAfterAt.includes('}')) {
        setMentionStart(lastAt);
        setMentionFilter(textAfterAt);
        setShowDropdown(true);
        setSelectedIndex(0);
        return;
      }
    }

    setShowDropdown(false);
  }, [onChange]);

  // Select a character from dropdown
  const selectCharacter = useCallback((char: Character) => {
    if (mentionStart === -1 || !textareaRef.current) return;

    const cursorPos = textareaRef.current.selectionStart || 0;
    const before = value.slice(0, mentionStart);
    const after = value.slice(cursorPos);
    const mention = `@{${char.name}} `;
    const newValue = before + mention + after;

    onChange(newValue);
    setShowDropdown(false);

    // Restore cursor position
    setTimeout(() => {
      if (textareaRef.current) {
        const newPos = mentionStart + mention.length;
        textareaRef.current.selectionStart = newPos;
        textareaRef.current.selectionEnd = newPos;
        textareaRef.current.focus();
      }
    }, 0);
  }, [mentionStart, value, onChange]);

  // Keyboard navigation in dropdown
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (!showDropdown || filteredChars.length === 0) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(prev => Math.min(prev + 1, filteredChars.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(prev => Math.max(prev - 1, 0));
    } else if (e.key === 'Enter' || e.key === 'Tab') {
      e.preventDefault();
      selectCharacter(filteredChars[selectedIndex]);
    } else if (e.key === 'Escape') {
      setShowDropdown(false);
    }
  }, [showDropdown, filteredChars, selectedIndex, selectCharacter]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node) &&
          textareaRef.current && !textareaRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="relative">
      <Textarea
        ref={textareaRef}
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        placeholder={placeholder || 'Type @ to mention a character...'}
        rows={rows}
        className={className}
      />

      {/* Mention dropdown */}
      {showDropdown && filteredChars.length > 0 && (
        <div
          ref={dropdownRef}
          className="absolute z-50 mt-1 w-64 bg-popover border rounded-md shadow-lg max-h-48 overflow-y-auto"
        >
          {filteredChars.map((char, i) => (
            <button
              key={char.id}
              className={cn(
                "w-full text-left px-3 py-2 flex items-center gap-2 text-sm hover:bg-accent transition-colors",
                i === selectedIndex && "bg-accent"
              )}
              onMouseDown={(e) => {
                e.preventDefault(); // Prevent textarea blur
                selectCharacter(char);
              }}
              onMouseEnter={() => setSelectedIndex(i)}
            >
              <Avatar className="w-6 h-6">
                <AvatarImage src={getPublicAvatarUrl(char.avatar_url) || ''} alt={char.name} />
                <AvatarFallback className="text-[9px]">{char.name.slice(0, 2).toUpperCase()}</AvatarFallback>
              </Avatar>
              <span>{char.name}</span>
            </button>
          ))}
        </div>
      )}

      {showDropdown && filteredChars.length === 0 && mentionFilter && (
        <div className="absolute z-50 mt-1 w-64 bg-popover border rounded-md shadow-lg p-3 text-sm text-muted-foreground">
          No characters matching "{mentionFilter}"
        </div>
      )}
    </div>
  );
}

/**
 * Renders text with @{Name} mentions as styled inline elements.
 * Use this for displaying bio text with clickable mentions.
 */
export function renderMentionText(
  text: string,
  characters: Character[],
  onCharacterClick?: (characterId: string) => void,
): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  const regex = /@\{([^}]+)\}/g;
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(text)) !== null) {
    // Text before the mention
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }

    const mentionName = match[1];
    const char = characters.find(c => c.name === mentionName);

    if (char && onCharacterClick) {
      parts.push(
        <button
          key={`mention-${match.index}`}
          onClick={() => onCharacterClick(char.id)}
          className="inline-flex items-center gap-0.5 px-1 py-0 rounded bg-primary/10 text-primary font-medium hover:bg-primary/20 transition-colors text-sm"
        >
          @{mentionName}
        </button>
      );
    } else {
      parts.push(
        <span key={`mention-${match.index}`} className="inline-flex items-center px-1 py-0 rounded bg-muted text-sm font-medium">
          @{mentionName}
        </span>
      );
    }

    lastIndex = match.index + match[0].length;
  }

  // Remaining text
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts;
}
