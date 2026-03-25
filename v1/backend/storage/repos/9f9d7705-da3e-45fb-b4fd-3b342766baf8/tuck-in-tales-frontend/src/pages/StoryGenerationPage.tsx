import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { v4 as uuidv4 } from 'uuid';
import { api } from '@/api/client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { ExclamationTriangleIcon } from '@radix-ui/react-icons';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { getPublicAvatarUrl } from '@/utils/supabaseUtils';
import { cn } from "@/lib/utils";

// Interface for family details needed here
interface FamilyDetails {
  default_language?: string | null;
}

// Updated Character interface for this page
interface CharacterSummary {
  id: string;
  name: string;
  avatar_url?: string | null; // Add avatar_url
}

export default function StoryGenerationPage() {
  const [characters, setCharacters] = useState<CharacterSummary[]>([]);
  const [selectedCharacterIds, setSelectedCharacterIds] = useState<Set<string>>(new Set());
  const [prompt, setPrompt] = useState('');
  const [numPages, setNumPages] = useState<string>('');
  const [loadingCharacters, setLoadingCharacters] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [familyDetails, setFamilyDetails] = useState<FamilyDetails | null>(null);
  const [loadingFamily, setLoadingFamily] = useState(true);
  const navigate = useNavigate();

  // Fetch characters on mount
  useEffect(() => {
    const fetchChars = async () => {
      setLoadingCharacters(true);
      setError(null);
      try {
        const fetchedCharacters = await api.fetchCharacters();
        // Map to include id, name, and avatar_url
        setCharacters(fetchedCharacters.map((c: any) => ({ 
            id: c.id, 
            name: c.name,
            avatar_url: c.avatar_url // Make sure backend returns this
        }))); 
      } catch (err: any) {
        console.error("Error fetching characters:", err);
        setError(err.response?.data?.detail || err.message || 'Failed to load characters.');
        toast.error("Failed to load characters for selection.");
      } finally {
        setLoadingCharacters(false);
      }
    };
    fetchChars();
  }, []);

  // --- Fetch family details --- 
  useEffect(() => {
    const fetchFamily = async () => {
      setLoadingFamily(true);
      try {
        const data = await api.fetchFamilyDetails();
        // We only need default_language, but store the relevant part
        if (data) {
             setFamilyDetails({ default_language: data.default_language });
        } else {
             setFamilyDetails(null);
        }
      } catch (err) {
        console.error("Error fetching family details on generation page:", err);
        // Non-critical error, generation can proceed with default language
        // Optionally show a non-blocking warning toast
        // toast.warning("Couldn't fetch family language settings.");
         setFamilyDetails(null); // Ensure it's null on error
      } finally {
        setLoadingFamily(false);
      }
    };

    fetchFamily();
  }, []); // Fetch once on mount
  // --------------------------

  // Handle card click for selection
  const handleCharacterSelect = (characterId: string) => {
    setSelectedCharacterIds(prev => {
      const newSet = new Set(prev);
      if (newSet.has(characterId)) {
        newSet.delete(characterId);
      } else {
        newSet.add(characterId);
      }
      return newSet;
    });
  };

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedCharacterIds.size === 0) {
      toast.error("Please select at least one character.");
      return;
    }

    setSubmitting(true);
    setError(null);

    // Determine language: use family default if available and not null/empty
    const storyLanguage = familyDetails?.default_language || undefined;

    const parsedNumPages = numPages ? parseInt(numPages, 10) : undefined;
    const requestData = {
      character_ids: Array.from(selectedCharacterIds),
      prompt: prompt || undefined,
      language: storyLanguage, // Pass the determined language
      target_age: undefined, // Add target age selection later if needed
      num_pages: (parsedNumPages && parsedNumPages >= 1 && parsedNumPages <= 20) ? parsedNumPages : undefined,
    };

    try {
      console.log("Submitting story generation request:", requestData);
      // API call now returns { message, story_id }
      const response = await api.generateStory(requestData);
      
      console.log("Received response from /stories/generate:", response);

      // Extract story_id (check if response is valid)
      const storyId = response?.story_id;
      
      toast.success(response?.message || "Story creation initiated!"); // Updated message
      
      // Navigate using the story_id from the response
      if (storyId) {
        // Navigate to the viewer/progress page for the new story ID
        navigate(`/stories/${storyId}`); 
      } else {
         // Handle case where story_id wasn't returned (error)
         console.error("Backend did not return a story ID.", response);
         throw new Error("Backend did not return a story ID.");
      }

    } catch (err: any) {
      console.error("Error triggering story generation:", err);
      const errorMsg = err.response?.data?.detail || err.message || 'Failed to start story generation.';
      setError(errorMsg);
      toast.error(`Error: ${errorMsg}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="container mx-auto p-4 max-w-3xl"> {/* Constrain width */}
      <Card>
        <CardHeader>
          <CardTitle>Generate New Story</CardTitle>
          <CardDescription>Select characters and add an optional prompt to guide the story.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Character Selection */}
            <div className="space-y-2">
              <Label className="text-lg font-semibold">Select Characters</Label>
              {loadingCharacters ? (
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
                    {[...Array(4)].map((_, i) => (
                        <Skeleton key={i} className="h-32 w-full" />
                    ))}
                </div>
              ) : error && characters.length === 0 ? (
                 <Alert variant="destructive">
                   <ExclamationTriangleIcon className="h-4 w-4" />
                   <AlertTitle>Error Loading Characters</AlertTitle>
                   <AlertDescription>{error}</AlertDescription>
                 </Alert>
              ) : characters.length === 0 ? (
                <p className="text-sm text-muted-foreground">No characters found in your family yet.</p>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4 pt-2">
                  {characters.map((char) => {
                    const isSelected = selectedCharacterIds.has(char.id);
                    const avatarSrc = getPublicAvatarUrl(char.avatar_url);
                    return (
                      <Card 
                        key={char.id} 
                        className={cn(
                          "cursor-pointer transition-all duration-150 ease-in-out",
                          "flex flex-col items-center p-3 text-center",
                          isSelected 
                            ? "border-primary border-2 ring-2 ring-primary/30" 
                            : "border",
                          submitting ? "opacity-50 cursor-not-allowed" : "hover:shadow-md"
                        )}
                        onClick={() => !submitting && handleCharacterSelect(char.id)}
                      >
                        <Avatar className="h-16 w-16 mb-2">
                          <AvatarImage src={avatarSrc || undefined} alt={char.name} className="object-cover" />
                          <AvatarFallback className="text-xl">
                              {char.name?.charAt(0).toUpperCase() || 'C'}
                          </AvatarFallback>
                        </Avatar>
                        <p className="text-sm font-medium truncate w-full">{char.name}</p>
                      </Card>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Optional Prompt */}
            <div className="space-y-2">
              <Label htmlFor="prompt" className="text-lg font-semibold">Optional Prompt</Label>
              <Textarea
                id="prompt"
                placeholder="e.g., A story about finding a hidden treasure... (leave blank for a random story)"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                rows={4}
                maxLength={1000} // Match backend model
                disabled={submitting}
              />
              <p className="text-xs text-muted-foreground">Max 1000 characters. If left blank, a random story will be generated based on the selected characters.</p>
            </div>

            {/* Number of Pages */}
            <div className="space-y-2">
              <Label htmlFor="numPages" className="text-lg font-semibold">Number of Pages</Label>
              <Input
                id="numPages"
                type="number"
                placeholder="Leave empty for default (3-5)"
                value={numPages}
                onChange={(e) => setNumPages(e.target.value)}
                min={1}
                max={20}
                disabled={submitting}
                className="max-w-[200px]"
              />
              <p className="text-xs text-muted-foreground">Optional. If left empty, the story will have 3-5 pages.</p>
            </div>

            {/* Submission Error */}
            {error && !loadingCharacters && (
              <Alert variant="destructive">
                <ExclamationTriangleIcon className="h-4 w-4" />
                <AlertTitle>Submission Error</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {/* Submit Button */}
            <Button 
              type="submit" 
              disabled={submitting || loadingCharacters || loadingFamily || selectedCharacterIds.size === 0} // Disable while loading family too
              className="w-full md:w-auto" // Adjust button width
            >
              {submitting ? (
                <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Generating...</>
              ) : (
                'Generate Story'
              )}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
} 