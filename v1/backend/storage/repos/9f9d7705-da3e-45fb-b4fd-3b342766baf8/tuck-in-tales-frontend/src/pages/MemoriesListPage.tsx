import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { format } from 'date-fns';
import { PlusIcon, TrashIcon, MagnifyingGlassIcon, ChevronDownIcon, ChevronUpIcon } from '@radix-ui/react-icons';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import {
  Card, CardContent,
} from "@/components/ui/card";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from '@/api/client';
import { CATEGORY_LABELS, CATEGORY_COLORS, type Memory, type MemoryCategory } from '@/models/memory';
import type { Character } from '@/models/character';
import { getPublicAvatarUrl, getPublicMemoryPhotoUrl } from '@/utils/supabaseUtils';
import { toast } from 'sonner';

const STATUS_COLORS: Record<string, string> = {
  CONFIRMED: 'bg-green-100 text-green-800',
  ANALYZED: 'bg-blue-100 text-blue-800',
  ANALYZING: 'bg-yellow-100 text-yellow-800',
  PENDING: 'bg-gray-100 text-gray-800',
  FAILED: 'bg-red-100 text-red-800',
};

export default function MemoriesListPage() {
  const navigate = useNavigate();
  const [memories, setMemories] = useState<Memory[]>([]);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<Memory[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [memoriesData, charsData] = await Promise.all([
        api.fetchMemories(),
        api.fetchCharacters(),
      ]);
      setMemories(memoriesData);
      setCharacters(charsData);
    } catch (err) {
      toast.error('Failed to load data.');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (memoryId: string) => {
    try {
      await api.deleteMemory(memoryId);
      setMemories(prev => prev.filter(m => m.id !== memoryId));
      toast.success('Memory deleted.');
    } catch (err) {
      toast.error('Failed to delete memory.');
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) { setSearchResults(null); return; }
    setSearching(true);
    try {
      const results = await api.searchMemories({ query: searchQuery });
      setSearchResults(results);
    } catch (err) {
      toast.error('Search failed.');
    } finally {
      setSearching(false);
    }
  };

  const clearSearch = () => { setSearchQuery(''); setSearchResults(null); };

  const getLinkedChars = (memory: Memory): Character[] => {
    if (!memory.linked_character_ids?.length) return [];
    return characters.filter(c => memory.linked_character_ids.includes(c.id));
  };

  const displayMemories = searchResults ?? memories;

  if (loading) {
    return (
      <div className="container mx-auto p-4 max-w-2xl space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-10 w-full" />
        {[1, 2, 3].map(i => <Skeleton key={i} className="h-32 w-full" />)}
      </div>
    );
  }

  return (
    <div className="container mx-auto p-4 max-w-2xl space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Memories</h1>
        <Button onClick={() => navigate('/memories')}>
          <PlusIcon className="mr-2 h-4 w-4" /> New Memory
        </Button>
      </div>

      {/* Search */}
      <div className="flex gap-2">
        <Input placeholder="Search memories..." value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()} />
        <Button variant="outline" onClick={handleSearch} disabled={searching}>
          <MagnifyingGlassIcon className="h-4 w-4" />
        </Button>
        {searchResults && <Button variant="ghost" onClick={clearSearch}>Clear</Button>}
      </div>

      {searchResults && (
        <p className="text-sm text-muted-foreground">
          {searchResults.length} result{searchResults.length !== 1 ? 's' : ''} found
        </p>
      )}

      {/* Memory list */}
      {displayMemories.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center">
            <p className="text-muted-foreground">
              {searchResults ? 'No memories match your search.' : 'No memories yet. Start by adding your first memory!'}
            </p>
            {!searchResults && (
              <Button className="mt-4" onClick={() => navigate('/memories')}>
                <PlusIcon className="mr-2 h-4 w-4" /> Add Memory
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {displayMemories.map((memory) => {
            const linkedChars = getLinkedChars(memory);
            const isExpanded = expandedId === memory.id;
            const hasPhotos = memory.photo_paths.length > 0;
            const hasDetails = hasPhotos || linkedChars.length > 0 || memory.text;

            return (
              <Card key={memory.id} className="group overflow-hidden">
                {/* Compact card - always visible */}
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    {/* Photo thumbnail (first photo if available) */}
                    {hasPhotos && (
                      <img
                        src={getPublicMemoryPhotoUrl(memory.photo_paths[0]) || ''}
                        alt=""
                        className="w-16 h-16 rounded-md object-cover flex-shrink-0"
                      />
                    )}

                    <div className="flex-1 min-w-0 space-y-1.5">
                      {/* Date + status */}
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm text-muted-foreground">
                          {format(new Date(memory.date + 'T00:00:00'), 'yyyy-MM-dd')}
                        </span>
                        <Badge variant="outline" className={STATUS_COLORS[memory.analysis_status] || ''}>
                          {memory.analysis_status}
                        </Badge>
                        {hasPhotos && (
                          <span className="text-xs text-muted-foreground">
                            {memory.photo_paths.length} photo{memory.photo_paths.length !== 1 ? 's' : ''}
                          </span>
                        )}
                      </div>

                      {/* Summary or text */}
                      <p className="text-sm">
                        {memory.summary || memory.text || '(Photo-only memory)'}
                      </p>

                      {/* Categories + linked characters in a row */}
                      <div className="flex items-center gap-2 flex-wrap">
                        {memory.categories.map((cat) => (
                          <Badge key={cat} variant="secondary"
                            className={`text-xs ${CATEGORY_COLORS[cat as MemoryCategory] || ''}`}>
                            {CATEGORY_LABELS[cat as MemoryCategory] || cat}
                          </Badge>
                        ))}

                        {/* Linked character avatars */}
                        {linkedChars.length > 0 && (
                          <div className="flex -space-x-1.5 ml-1">
                            {linkedChars.map((char) => (
                              <Avatar key={char.id} className="w-6 h-6 border-2 border-background">
                                <AvatarImage src={getPublicAvatarUrl(char.avatar_url) || ''} alt={char.name} />
                                <AvatarFallback className="text-[9px]">
                                  {char.name.slice(0, 2).toUpperCase()}
                                </AvatarFallback>
                              </Avatar>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-1 flex-shrink-0">
                      {hasDetails && (
                        <Button variant="ghost" size="sm"
                          onClick={() => setExpandedId(isExpanded ? null : memory.id)}>
                          {isExpanded
                            ? <ChevronUpIcon className="h-4 w-4" />
                            : <ChevronDownIcon className="h-4 w-4" />}
                        </Button>
                      )}
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button variant="ghost" size="sm"
                            className="opacity-0 group-hover:opacity-100 transition-opacity text-destructive">
                            <TrashIcon className="h-4 w-4" />
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Delete Memory?</AlertDialogTitle>
                            <AlertDialogDescription>
                              This will permanently delete this memory and any associated photos.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction onClick={() => handleDelete(memory.id)}>Delete</AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </div>
                  </div>
                </CardContent>

                {/* Expanded details */}
                {isExpanded && (
                  <div className="border-t px-4 pb-4 pt-3 space-y-3 bg-muted/30">
                    {/* Original text (if summary differs) */}
                    {memory.text && memory.summary && memory.text !== memory.summary && (
                      <div>
                        <p className="text-xs font-medium text-muted-foreground mb-1">Original text</p>
                        <p className="text-sm">{memory.text}</p>
                      </div>
                    )}

                    {/* All photos */}
                    {hasPhotos && (
                      <div>
                        <p className="text-xs font-medium text-muted-foreground mb-1.5">Photos</p>
                        <div className="grid grid-cols-3 gap-2">
                          {memory.photo_paths.map((path, i) => (
                            <img key={i}
                              src={getPublicMemoryPhotoUrl(path) || ''}
                              alt={`Memory photo ${i + 1}`}
                              className="w-full h-28 object-cover rounded-md"
                            />
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Linked characters */}
                    {linkedChars.length > 0 && (
                      <div>
                        <p className="text-xs font-medium text-muted-foreground mb-1.5">Characters</p>
                        <div className="flex flex-wrap gap-2">
                          {linkedChars.map((char) => (
                            <button key={char.id}
                              onClick={() => navigate(`/characters/${char.id}`)}
                              className="flex items-center gap-2 px-2 py-1.5 rounded-md bg-background border hover:bg-accent transition-colors">
                              <Avatar className="w-7 h-7">
                                <AvatarImage src={getPublicAvatarUrl(char.avatar_url) || ''} alt={char.name} />
                                <AvatarFallback className="text-[10px]">
                                  {char.name.slice(0, 2).toUpperCase()}
                                </AvatarFallback>
                              </Avatar>
                              <span className="text-sm font-medium">{char.name}</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
