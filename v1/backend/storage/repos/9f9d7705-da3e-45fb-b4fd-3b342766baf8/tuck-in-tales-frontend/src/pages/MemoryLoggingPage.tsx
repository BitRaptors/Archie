import React, { useState, useCallback, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import { format } from 'date-fns';
import { UploadIcon, Cross1Icon, CalendarIcon, CheckIcon, ReloadIcon, Pencil1Icon, PlusIcon, PersonIcon } from '@radix-ui/react-icons';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle,
} from "@/components/ui/card";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Calendar } from "@/components/ui/calendar";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { api } from '@/api/client';
import { useMemoryStream } from '@/hooks/useMemoryStream';
import { CATEGORY_LABELS, CATEGORY_COLORS, type MemoryCategory, type NewCharacterDetection, type PhotoAnalysisResult } from '@/models/memory';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';
import { useAvatarStream } from '@/hooks/useAvatarStream';
import MentionInput from '@/components/MentionInput';
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { getPublicAvatarUrl } from '@/utils/supabaseUtils';

type FileWithPreview = File & { preview: string };
type Step = 'input' | 'analysis' | 'confirm' | 'generating' | 'done';

// Track avatar generation progress per character
interface CharacterGenProgress {
  id: string;
  name: string;
  status: 'pending' | 'generating' | 'complete' | 'error';
  message: string;
  avatarUrl: string | null;
}

// Editable new character state
interface EditableNewCharacter {
  name: string;
  bio: string;
  photoIndices: number[]; // which memory photos this character appears in
}

// Sub-component: watches SSE for a single character's avatar generation
function AvatarGenRow({ char, onUpdate }: {
  char: CharacterGenProgress;
  onUpdate: (updated: CharacterGenProgress) => void;
}) {
  const { statusMessage, avatarUrl, isComplete, error, isConnected } = useAvatarStream(char.id, true);

  useEffect(() => {
    if (isConnected && char.status === 'pending') {
      onUpdate({ ...char, status: 'generating', message: 'Starting...' });
    }
  }, [isConnected]);

  useEffect(() => {
    if (statusMessage && char.status !== 'complete') {
      onUpdate({ ...char, status: 'generating', message: statusMessage });
    }
  }, [statusMessage]);

  useEffect(() => {
    if (isComplete && avatarUrl) {
      onUpdate({ ...char, status: 'complete', message: 'Avatar ready!', avatarUrl });
    } else if (isComplete && !avatarUrl) {
      onUpdate({ ...char, status: 'complete', message: 'Done (no avatar generated)' });
    }
  }, [isComplete, avatarUrl]);

  useEffect(() => {
    if (error) {
      onUpdate({ ...char, status: 'error', message: error });
    }
  }, [error]);

  return (
    <div className="flex items-center gap-3 p-3 bg-muted rounded-md">
      {/* Avatar preview or placeholder */}
      <Avatar className="w-12 h-12">
        {char.avatarUrl || avatarUrl ? (
          <AvatarImage src={getPublicAvatarUrl(char.avatarUrl || avatarUrl) || ''} />
        ) : null}
        <AvatarFallback className="text-sm">{char.name.slice(0, 2).toUpperCase()}</AvatarFallback>
      </Avatar>

      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium">{char.name}</p>
        <p className="text-xs text-muted-foreground truncate">
          {char.status === 'generating' && <><ReloadIcon className="inline h-3 w-3 animate-spin mr-1" /></>}
          {statusMessage || char.message}
        </p>
      </div>

      {/* Status indicator */}
      <div className="flex-shrink-0">
        {char.status === 'complete' && (
          <div className="w-6 h-6 rounded-full bg-green-100 flex items-center justify-center">
            <CheckIcon className="h-4 w-4 text-green-600" />
          </div>
        )}
        {char.status === 'error' && (
          <div className="w-6 h-6 rounded-full bg-red-100 flex items-center justify-center">
            <Cross1Icon className="h-3 w-3 text-red-600" />
          </div>
        )}
        {(char.status === 'pending' || char.status === 'generating') && (
          <ReloadIcon className="h-4 w-4 animate-spin text-muted-foreground" />
        )}
      </div>
    </div>
  );
}

export default function MemoryLoggingPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>('input');

  // Input
  const [memoryText, setMemoryText] = useState('');
  const [memoryDate, setMemoryDate] = useState(format(new Date(), 'yyyy-MM-dd'));
  const [files, setFiles] = useState<FileWithPreview[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [familyCharacters, setFamilyCharacters] = useState<Array<{id: string; name: string; avatar_url?: string | null}>>([]);

  // Load family characters for MentionInput
  useEffect(() => {
    api.fetchCharacters().then(chars => setFamilyCharacters(chars)).catch(() => {});
  }, []);

  // Memory ID
  const [memoryId, setMemoryId] = useState<string | null>(null);

  // Confirm state
  const [editCategories, setEditCategories] = useState<string[]>([]);
  const [editSummary, setEditSummary] = useState('');
  const [editLinkedCharIds, setEditLinkedCharIds] = useState<string[]>([]);
  const [newCharacters, setNewCharacters] = useState<EditableNewCharacter[]>([]);
  const [photoTagging, setPhotoTagging] = useState<Record<number, string[]>>({}); // photo_index -> character names
  const [confirming, setConfirming] = useState(false);
  const [charGenProgress, setCharGenProgress] = useState<CharacterGenProgress[]>([]);

  // Modal
  const [editingCharIndex, setEditingCharIndex] = useState<number | null>(null);
  const [modalName, setModalName] = useState('');
  const [modalBio, setModalBio] = useState('');
  const [modalPhotoIndices, setModalPhotoIndices] = useState<number[]>([]);

  // "Ki ez?" input per photo for unknowns
  const [unknownNameInputs, setUnknownNameInputs] = useState<Record<string, string>>({});

  // Stream
  const {
    analysisText, textAnalysis, photoResults, isConnected, isComplete, error, statusMessage, startStream,
  } = useMemoryStream(memoryId);

  // When text analysis arrives, populate confirm state
  useEffect(() => {
    if (textAnalysis && step === 'analysis') {
      setEditCategories(textAnalysis.categories || []);
      setEditSummary(textAnalysis.summary || '');
      setEditLinkedCharIds((textAnalysis.linked_characters || []).map(c => c.id));

      const detected = (textAnalysis.new_characters || []).map(c => ({
        name: c.name,
        bio: c.guessed_bio || '',
        photoIndices: [],
      }));
      setNewCharacters(detected);
    }
  }, [textAnalysis, step]);

  // When photo results arrive, build initial photo tagging (per-person index array)
  useEffect(() => {
    if (photoResults.length > 0) {
      setPhotoTagging(prev => {
        const tagging = { ...prev };
        for (const pr of photoResults) {
          if (!tagging[pr.photo_index]) {
            // Each index corresponds to a detected_people entry
            tagging[pr.photo_index] = pr.detected_people.map(p =>
              p.name.startsWith('unknown') ? '' : p.name
            );
          }
        }
        return tagging;
      });
    }
  }, [photoResults]);

  // When all analysis is done, move to confirm
  useEffect(() => {
    if (isComplete && step === 'analysis') {
      setStep('confirm');
    }
  }, [isComplete, step]);

  // Dropzone
  const onDrop = useCallback((acceptedFiles: File[]) => {
    const withPreviews = acceptedFiles.map(file =>
      Object.assign(file, { preview: URL.createObjectURL(file) })
    );
    setFiles(prev => [...prev, ...withPreviews]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/jpeg': ['.jpg', '.jpeg'], 'image/png': ['.png'], 'image/webp': ['.webp'] },
    maxSize: 5 * 1024 * 1024,
  });

  const removeFile = (index: number) => {
    setFiles(prev => {
      const f = [...prev];
      URL.revokeObjectURL(f[index].preview);
      f.splice(index, 1);
      return f;
    });
  };

  // Submit
  const handleSubmit = async () => {
    if (!memoryText.trim() && files.length === 0) {
      toast.error('Add text or at least one photo.');
      return;
    }
    setSubmitting(true);
    try {
      const memory = await api.createMemory(memoryText.trim() || null, memoryDate, files);
      setMemoryId(memory.id);
      setStep('analysis');
      startStream();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to create memory.');
    } finally {
      setSubmitting(false);
    }
  };

  // Category toggle
  const toggleCategory = (cat: string) => {
    setEditCategories(prev => prev.includes(cat) ? prev.filter(c => c !== cat) : [...prev, cat]);
  };

  // Open character edit modal
  const openCharModal = (index: number) => {
    const char = newCharacters[index];
    setEditingCharIndex(index);
    setModalName(char.name);
    setModalBio(char.bio);
    setModalPhotoIndices([...char.photoIndices]);
  };

  // Save character modal
  const saveCharModal = () => {
    if (editingCharIndex === null) return;
    setNewCharacters(prev => {
      const updated = [...prev];
      updated[editingCharIndex] = {
        name: modalName,
        bio: modalBio,
        photoIndices: modalPhotoIndices,
      };
      return updated;
    });
    setEditingCharIndex(null);
  };

  // Remove new character
  const removeNewChar = (index: number) => {
    setNewCharacters(prev => prev.filter((_, i) => i !== index));
  };

  // Toggle photo assignment in modal
  const toggleModalPhoto = (photoIndex: number) => {
    setModalPhotoIndices(prev =>
      prev.includes(photoIndex) ? prev.filter(i => i !== photoIndex) : [...prev, photoIndex]
    );
  };

  // Confirm memory
  const handleConfirm = async () => {
    if (!memoryId) return;
    setConfirming(true);
    try {
      // 1. Create new characters if any, collect their IDs
      const createdChars: Array<{ id: string; name: string; hasPhoto: boolean }> = [];
      if (newCharacters.length > 0) {
        const chars = newCharacters.map(c => {
          let photoIndex: number | undefined = c.photoIndices[0];
          if (photoIndex === undefined) {
            for (const [pi, personNames] of Object.entries(photoTagging)) {
              if (personNames.some(n => n === c.name)) {
                photoIndex = parseInt(pi);
                break;
              }
            }
          }
          // Find face_x for this character from photoResults
          let faceX: number | undefined;
          if (photoIndex !== undefined) {
            const pr = photoResults.find(r => r.photo_index === photoIndex);
            if (pr) {
              // Find by tagged name in photoTagging
              const taggedNames = photoTagging[photoIndex] || [];
              const personIdx = taggedNames.indexOf(c.name);
              if (personIdx !== -1 && pr.detected_people[personIdx]?.face_x != null) {
                faceX = pr.detected_people[personIdx].face_x;
              }
            }
          }
          return { name: c.name, bio: c.bio || undefined, photo_index: photoIndex, face_x: faceX };
        });
        const result = await api.createCharactersFromMemory(memoryId, { characters: chars });
        if (result.characters) {
          for (let i = 0; i < result.characters.length; i++) {
            const c = result.characters[i];
            if (c.id) {
              createdChars.push({
                id: c.id,
                name: c.name || chars[i]?.name || 'Character',
                hasPhoto: !!(c.photo_paths?.length),
              });
            }
          }
        }
      }

      // 2. Confirm memory - include both original linked chars AND newly created ones
      const createdCharIds = createdChars.map(c => c.id);
      const allLinkedIds = [...new Set([...editLinkedCharIds, ...createdCharIds])];
      await api.confirmMemory(memoryId, {
        categories: editCategories,
        summary: editSummary || null,
        linked_character_ids: allLinkedIds,
      });
      toast.success('Memory saved!');

      // 3. If any created characters have photos, show avatar generation progress
      const charsWithPhotos = createdChars.filter(c => c.hasPhoto);
      if (charsWithPhotos.length > 0) {
        setCharGenProgress(charsWithPhotos.map(c => ({
          id: c.id,
          name: c.name,
          status: 'pending',
          message: 'Waiting...',
          avatarUrl: null,
        })));
        setStep('generating');
      } else {
        setStep('done');
      }
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to save.');
    } finally {
      setConfirming(false);
    }
  };

  // Apply suggestion (bio update etc.)
  const handleApplySuggestion = async (index: number) => {
    if (!memoryId) return;
    try {
      const result = await api.applySuggestion(memoryId, { suggestion_index: index, approved: true });
      toast.success(result.message || 'Suggestion applied!');
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to apply suggestion.');
    }
  };

  // Reset
  const handleReset = () => {
    setStep('input');
    setMemoryText('');
    setMemoryDate(format(new Date(), 'yyyy-MM-dd'));
    setFiles([]);
    setMemoryId(null);
    setEditCategories([]);
    setEditSummary('');
    setEditLinkedCharIds([]);
    setNewCharacters([]);
    setPhotoTagging({});
    setUnknownNameInputs({});
  };

  // All known + new character names for photo tagging
  const allCharacterNames = [
    ...(textAnalysis?.linked_characters || []).map(c => c.name),
    ...newCharacters.map(c => c.name),
  ];

  return (
    <div className="container mx-auto p-4 max-w-2xl space-y-4">
      <h1 className="text-2xl font-bold">Memories</h1>

      {/* STEP 1: INPUT */}
      {step === 'input' && (
        <Card>
          <CardHeader>
            <CardTitle>New Memory</CardTitle>
            <CardDescription>Describe a memory, event, or upload photos. At least one is required.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="memoryText">What happened?</Label>
              <Textarea
                id="memoryText"
                placeholder="e.g., Felix, Dani and Zsuzsi had a great time playing together..."
                value={memoryText}
                onChange={(e) => setMemoryText(e.target.value)}
                rows={4}
              />
            </div>

            <div className="space-y-2">
              <Label>Date</Label>
              <Popover>
                <PopoverTrigger asChild>
                  <Button variant="outline" className="w-full justify-start text-left font-normal">
                    <CalendarIcon className="mr-2 h-4 w-4" />
                    {memoryDate ? format(new Date(memoryDate + 'T00:00:00'), 'yyyy-MM-dd') : 'Pick a date'}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0" align="start">
                  <Calendar
                    mode="single"
                    selected={memoryDate ? new Date(memoryDate + 'T00:00:00') : undefined}
                    onSelect={(date: Date | undefined) => { if (date) setMemoryDate(format(date, 'yyyy-MM-dd')); }}
                    initialFocus
                  />
                </PopoverContent>
              </Popover>
            </div>

            <div className="space-y-2">
              <Label>Photos (optional)</Label>
              <div
                {...getRootProps()}
                className={cn(
                  "border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors",
                  isDragActive ? "border-primary bg-primary/10" : "border-muted-foreground/50 hover:border-primary/50"
                )}
              >
                <input {...getInputProps()} />
                <UploadIcon className="mx-auto h-8 w-8 text-muted-foreground mb-2" />
                {isDragActive ? <p>Drop photos here...</p> : <p>Drag & drop photos here, or click to select</p>}
              </div>
              {files.length > 0 && (
                <div className="grid grid-cols-3 gap-2 mt-2">
                  {files.map((file, i) => (
                    <div key={i} className="relative group">
                      <img src={file.preview} alt={`Preview ${i + 1}`} className="w-full h-24 object-cover rounded-md" />
                      <button type="button" onClick={() => removeFile(i)}
                        className="absolute top-1 right-1 bg-destructive text-destructive-foreground rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                        <Cross1Icon className="h-3 w-3" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </CardContent>
          <CardFooter>
            <Button onClick={handleSubmit} disabled={submitting || (!memoryText.trim() && files.length === 0)} className="w-full">
              {submitting ? <><ReloadIcon className="mr-2 h-4 w-4 animate-spin" /> Submitting...</> : 'Analyze Memory'}
            </Button>
          </CardFooter>
        </Card>
      )}

      {/* STEP 2: ANALYSIS (streamed) */}
      {step === 'analysis' && (
        <Card>
          <CardHeader>
            <CardTitle>Analyzing Memory...</CardTitle>
            <CardDescription>{statusMessage || 'Processing your memory...'}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {analysisText && (
              <div className="space-y-2">
                <Label className="text-sm font-medium">Text Analysis</Label>
                <div className="text-sm bg-muted p-3 rounded-md whitespace-pre-wrap font-mono text-xs">
                  {analysisText}
                  {isConnected && <span className="animate-pulse">|</span>}
                </div>
              </div>
            )}

            {textAnalysis && textAnalysis.new_characters && textAnalysis.new_characters.length > 0 && (
              <div className="space-y-2">
                <Label className="text-sm font-medium">New characters detected</Label>
                <div className="flex flex-wrap gap-2">
                  {textAnalysis.new_characters.map((c, i) => (
                    <Badge key={i} variant="default" className="bg-purple-100 text-purple-800">
                      <PersonIcon className="mr-1 h-3 w-3" /> {c.name}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {photoResults.length > 0 && (
              <div className="space-y-2">
                <Label className="text-sm font-medium">Photo Analysis</Label>
                {photoResults.map((pr, i) => (
                  <div key={i} className="bg-muted p-3 rounded-md space-y-1">
                    <p className="text-sm">{pr.description}</p>
                    {pr.detected_people.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {pr.detected_people.map((p, j) => (
                          <Badge key={j} variant={p.is_known ? "secondary" : "outline"} className="text-xs">
                            {p.name.startsWith('unknown') ? '?' : p.name}
                            {p.confidence !== 'high' && ` (${p.confidence})`}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {isConnected && !analysisText && !photoResults.length && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <ReloadIcon className="h-4 w-4 animate-spin" /> Waiting for analysis...
              </div>
            )}

            {error && <p className="text-sm text-destructive">{error}</p>}
          </CardContent>
        </Card>
      )}

      {/* STEP 3: CONFIRM / EDIT */}
      {step === 'confirm' && (
        <div className="space-y-4">
          {/* Summary + Categories */}
          <Card>
            <CardHeader>
              <CardTitle>Review & Confirm</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label className="text-sm font-medium">Categories</Label>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(CATEGORY_LABELS).map(([key, label]) => {
                    const isActive = editCategories.includes(key);
                    return (
                      <Badge key={key} variant={isActive ? "default" : "outline"}
                        className={cn("cursor-pointer transition-colors", isActive && CATEGORY_COLORS[key as MemoryCategory])}
                        onClick={() => toggleCategory(key)}>
                        {isActive && <CheckIcon className="mr-1 h-3 w-3" />}
                        {label}
                      </Badge>
                    );
                  })}
                </div>
              </div>

              <Separator />

              <div className="space-y-2">
                <Label htmlFor="editSummary">Summary</Label>
                <Textarea id="editSummary" value={editSummary} onChange={(e) => setEditSummary(e.target.value)} rows={3} />
              </div>

              {textAnalysis?.linked_characters && textAnalysis.linked_characters.length > 0 && (
                <div className="space-y-2">
                  <Label className="text-sm font-medium">Recognized Characters</Label>
                  <div className="flex flex-wrap gap-2">
                    {textAnalysis.linked_characters.map((c) => (
                      <Badge key={c.id} variant="secondary">{c.name}</Badge>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* New Characters */}
          {(newCharacters.length > 0 || photoResults.some(pr => pr.detected_people.some(p => p.name.startsWith('unknown')))) && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">New Characters</CardTitle>
                <CardDescription>
                  {newCharacters.length > 0
                    ? `${newCharacters.length} new character(s) detected. Edit details and create them.`
                    : 'Name unknown people from the photos to create characters.'}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {newCharacters.map((char, i) => (
                  <div key={i} className="flex items-center justify-between p-3 bg-muted rounded-md">
                    <div className="flex-1">
                      <p className="font-medium">{char.name}</p>
                      {char.bio && <p className="text-sm text-muted-foreground">{char.bio}</p>}
                      {char.photoIndices.length > 0 && (
                        <p className="text-xs text-muted-foreground mt-1">
                          {char.photoIndices.length} photo{char.photoIndices.length !== 1 ? 's' : ''} assigned
                        </p>
                      )}
                    </div>
                    <div className="flex gap-1">
                      <Button size="sm" variant="ghost" onClick={() => openCharModal(i)}>
                        <Pencil1Icon className="h-4 w-4" />
                      </Button>
                      <Button size="sm" variant="ghost" className="text-destructive" onClick={() => removeNewChar(i)}>
                        <Cross1Icon className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))}

              </CardContent>
            </Card>
          )}

          {/* Photo Tagging */}
          {files.length > 0 && photoResults.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Who's in the photos?</CardTitle>
                <CardDescription>Confirm or change who each person is.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {files.map((file, photoIndex) => {
                  const result = photoResults.find(pr => pr.photo_index === photoIndex);
                  if (!result) return null;
                  const people = result.detected_people || [];

                  return (
                    <div key={photoIndex} className="border rounded-lg overflow-hidden">
                      {/* Photo with face-positioned tags */}
                      <div className="relative">
                        <img src={file.preview} alt={`Photo ${photoIndex + 1}`}
                          className="w-full h-64 object-cover" />

                        {/* Face tags positioned on the photo */}
                        {people.map((person, personIdx) => {
                          const tagKey = `${photoIndex}-${personIdx}`;
                          const currentName = photoTagging[photoIndex]?.[personIdx] ??
                            (person.name.startsWith('unknown') ? '' : person.name);
                          if (currentName === '__ignored__') return null;
                          const isUnknown = !currentName;

                          // Position: use LLM-provided face_x/face_y, or distribute evenly
                          const faceX = person.face_x ?? (people.length === 1 ? 50 : 20 + (60 / (people.length - 1)) * personIdx);
                          const faceY = person.face_y ?? 35;

                          // Clamp tag label position so it doesn't overflow
                          const labelX = Math.max(10, Math.min(90, faceX));

                          return (
                            <Popover key={tagKey}>
                              <PopoverTrigger asChild>
                                <button
                                  className="absolute flex flex-col items-center gap-0.5 cursor-pointer group"
                                  style={{
                                    left: `${labelX}%`,
                                    top: `${Math.min(85, faceY + 15)}%`,
                                    transform: 'translate(-50%, 0)',
                                    zIndex: 10,
                                  }}
                                >
                                  {/* Arrow pointing up to the face */}
                                  <svg width="8" height="6" viewBox="0 0 8 6" className="drop-shadow-md -mb-0.5">
                                    <polygon points="4,0 0,6 8,6" fill="white" fillOpacity="0.95" />
                                  </svg>
                                  {/* Name label + dismiss button */}
                                  <span className={cn(
                                    "relative inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full text-[11px] font-medium shadow-md transition-all whitespace-nowrap",
                                    "group-hover:scale-105",
                                    isUnknown
                                      ? "bg-white/80 text-gray-500 border border-dashed border-gray-400 backdrop-blur-sm"
                                      : "bg-white/95 text-gray-900 backdrop-blur-sm shadow-lg"
                                  )}>
                                    {isUnknown ? 'Ki ez?' : currentName}
                                    <span
                                      className="hidden group-hover:inline-flex items-center justify-center w-4 h-4 -mr-1 rounded-full hover:bg-red-100 transition-colors"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        setPhotoTagging(prev => {
                                          const arr = [...(prev[photoIndex] || [])];
                                          arr[personIdx] = '__ignored__';
                                          return { ...prev, [photoIndex]: arr };
                                        });
                                      }}
                                    >
                                      <Cross1Icon className="h-2.5 w-2.5 text-red-500" />
                                    </span>
                                  </span>
                                </button>
                              </PopoverTrigger>
                              <PopoverContent className="w-52 p-1" align="center" side="bottom">
                                <div className="space-y-0.5">
                                  {person.visual_note && (
                                    <p className="px-2 py-1.5 text-xs text-muted-foreground italic">
                                      {person.visual_note}
                                    </p>
                                  )}
                                  <Separator />
                                  {/* Known characters */}
                                  {(textAnalysis?.linked_characters || []).map((c) => (
                                    <button key={c.id}
                                      className={cn(
                                        "w-full text-left px-2 py-1.5 text-sm rounded-sm hover:bg-accent flex items-center gap-2",
                                        currentName === c.name && "bg-accent font-medium"
                                      )}
                                      onClick={() => {
                                        setPhotoTagging(prev => {
                                          const arr = [...(prev[photoIndex] || [])];
                                          arr[personIdx] = c.name;
                                          return { ...prev, [photoIndex]: arr };
                                        });
                                      }}>
                                      {currentName === c.name && <CheckIcon className="h-3 w-3 text-green-600" />}
                                      {c.name}
                                    </button>
                                  ))}
                                  {/* New characters */}
                                  {newCharacters.length > 0 && <>
                                    <Separator />
                                    <p className="px-2 py-1 text-xs text-muted-foreground">New</p>
                                  </>}
                                  {newCharacters.map((nc, ncIdx) => (
                                    <button key={`new-${ncIdx}`}
                                      className={cn(
                                        "w-full text-left px-2 py-1.5 text-sm rounded-sm hover:bg-accent flex items-center gap-2",
                                        currentName === nc.name && "bg-accent font-medium"
                                      )}
                                      onClick={() => {
                                        setPhotoTagging(prev => {
                                          const arr = [...(prev[photoIndex] || [])];
                                          arr[personIdx] = nc.name;
                                          return { ...prev, [photoIndex]: arr };
                                        });
                                        setNewCharacters(prev => prev.map((c, i) =>
                                          i === ncIdx && !c.photoIndices.includes(photoIndex)
                                            ? { ...c, photoIndices: [...c.photoIndices, photoIndex] }
                                            : c
                                        ));
                                      }}>
                                      {currentName === nc.name && <CheckIcon className="h-3 w-3 text-green-600" />}
                                      <Badge variant="outline" className="text-xs bg-purple-50 border-purple-200">{nc.name}</Badge>
                                    </button>
                                  ))}
                                  {/* Add new name inline */}
                                  <Separator />
                                  <div className="p-1">
                                    <div className="flex gap-1">
                                      <Input
                                        placeholder="New name..."
                                        className="h-7 text-xs"
                                        value={unknownNameInputs[tagKey] || ''}
                                        onChange={(e) => setUnknownNameInputs(prev => ({ ...prev, [tagKey]: e.target.value }))}
                                        onKeyDown={(e) => {
                                          if (e.key === 'Enter') {
                                            const name = unknownNameInputs[tagKey]?.trim();
                                            if (!name) return;
                                            setNewCharacters(prev => {
                                              if (prev.some(c => c.name.toLowerCase() === name.toLowerCase())) return prev;
                                              return [...prev, { name, bio: '', photoIndices: [photoIndex] }];
                                            });
                                            setPhotoTagging(prev => {
                                              const arr = [...(prev[photoIndex] || [])];
                                              arr[personIdx] = name;
                                              return { ...prev, [photoIndex]: arr };
                                            });
                                            setUnknownNameInputs(prev => ({ ...prev, [tagKey]: '' }));
                                          }
                                        }}
                                      />
                                      <Button size="sm" variant="outline" className="h-7 text-xs px-2"
                                        onClick={() => {
                                          const name = unknownNameInputs[tagKey]?.trim();
                                          if (!name) return;
                                          setNewCharacters(prev => {
                                            if (prev.some(c => c.name.toLowerCase() === name.toLowerCase())) return prev;
                                            return [...prev, { name, bio: '', photoIndices: [photoIndex] }];
                                          });
                                          setPhotoTagging(prev => {
                                            const arr = [...(prev[photoIndex] || [])];
                                            arr[personIdx] = name;
                                            return { ...prev, [photoIndex]: arr };
                                          });
                                          setUnknownNameInputs(prev => ({ ...prev, [tagKey]: '' }));
                                        }}>
                                        <PlusIcon className="h-3 w-3" />
                                      </Button>
                                    </div>
                                  </div>
                                </div>
                              </PopoverContent>
                            </Popover>
                          );
                        })}
                      </div>
                      {/* Description below photo */}
                      <div className="p-3">
                        <p className="text-sm text-muted-foreground">{result.description}</p>
                      </div>
                    </div>
                  );
                })}
              </CardContent>
            </Card>
          )}

          {/* Suggestions (bio updates etc.) */}
          {textAnalysis?.suggestions && textAnalysis.suggestions.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Suggestions</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {textAnalysis.suggestions.map((s, i) => (
                  <div key={i} className="flex items-center justify-between p-3 bg-muted rounded-md">
                    <div>
                      <p className="text-sm font-medium">
                        {s.type === 'update_character_bio' && `Update ${s.character_name}'s bio`}
                        {s.type === 'update_character_visual' && `Update ${s.character_name}'s appearance`}
                        {s.type === 'update_character_avatar' && `Regenerate ${s.character_name}'s avatar`}
                      </p>
                      {s.data?.bio_addition && <p className="text-xs text-muted-foreground">+ {s.data.bio_addition}</p>}
                    </div>
                    <Button size="sm" variant="outline" onClick={() => handleApplySuggestion(i)}>Apply</Button>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Confirm / Discard */}
          <div className="flex gap-2">
            <Button onClick={handleConfirm} disabled={confirming} className="flex-1">
              {confirming ? <><ReloadIcon className="mr-2 h-4 w-4 animate-spin" /> Saving...</> : 'Confirm & Save Memory'}
            </Button>
            <Button variant="ghost" onClick={handleReset}>Discard</Button>
          </div>
        </div>
      )}

      {/* STEP: GENERATING AVATARS */}
      {step === 'generating' && charGenProgress.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Generating Avatars...</CardTitle>
            <CardDescription>Creating visual descriptions and avatars for new characters.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {charGenProgress.map((char) => (
              <AvatarGenRow key={char.id} char={char} onUpdate={(updated) => {
                setCharGenProgress(prev => {
                  const next = prev.map(c => c.id === updated.id ? updated : c);
                  // If all done/error, auto-transition after a short delay
                  if (next.every(c => c.status === 'complete' || c.status === 'error')) {
                    setTimeout(() => setStep('done'), 1500);
                  }
                  return next;
                });
              }} />
            ))}
          </CardContent>
          <CardFooter>
            <Button variant="ghost" onClick={() => setStep('done')} className="w-full">
              Skip & Continue
            </Button>
          </CardFooter>
        </Card>
      )}

      {/* STEP 4: DONE */}
      {step === 'done' && (
        <Card>
          <CardHeader>
            <CardTitle>Memory Saved!</CardTitle>
            <CardDescription>Your memory has been saved and will personalize future stories.</CardDescription>
          </CardHeader>
          <CardFooter className="flex gap-2">
            <Button onClick={handleReset} className="flex-1">Add Another Memory</Button>
            <Button variant="outline" onClick={() => navigate('/memories/list')} className="flex-1">View All Memories</Button>
          </CardFooter>
        </Card>
      )}

      {/* NEW CHARACTER MODAL */}
      <Dialog open={editingCharIndex !== null} onOpenChange={(open) => { if (!open) setEditingCharIndex(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Character</DialogTitle>
            <DialogDescription>Edit the details for this new character.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Name</Label>
              <Input value={modalName} onChange={(e) => setModalName(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Bio</Label>
              <MentionInput
                value={modalBio}
                onChange={setModalBio}
                characters={[
                  ...familyCharacters,
                  ...newCharacters.map((c, i) => ({ id: `new-${i}`, name: c.name, avatar_url: null })),
                ] as any}
                placeholder="Short description... Use @ to mention other characters"
                rows={3}
              />
            </div>
            {files.length > 0 && (
              <div className="space-y-2">
                <Label>Assign to photo(s)</Label>
                <div className="grid grid-cols-4 gap-2">
                  {files.map((file, i) => (
                    <div key={i}
                      className={cn(
                        "relative cursor-pointer rounded-md overflow-hidden border-2 transition-all",
                        modalPhotoIndices.includes(i) ? "border-green-500 ring-2 ring-green-300" : "border-muted hover:border-muted-foreground/50"
                      )}
                      onClick={() => toggleModalPhoto(i)}>
                      <img src={file.preview} alt={`Photo ${i + 1}`} className="w-full h-16 object-cover" />
                      {modalPhotoIndices.includes(i) && (
                        <div className="absolute top-1 right-1 bg-green-500 rounded-full p-0.5">
                          <CheckIcon className="h-3 w-3 text-white" />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setEditingCharIndex(null)}>Cancel</Button>
            <Button onClick={saveCharModal} disabled={!modalName.trim()}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
