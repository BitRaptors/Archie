import { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '@/api/client';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { ExclamationTriangleIcon, DotsHorizontalIcon } from '@radix-ui/react-icons';
import { toast } from 'sonner';
import { getPublicAvatarUrl, getPublicPhotoUrl } from '@/utils/supabaseUtils';
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Loader2 } from 'lucide-react';
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import ReactMarkdown from 'react-markdown';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import type { Character } from '@/models/character';
import { useAvatarStream } from '@/hooks/useAvatarStream';
import { CalendarIcon } from "@radix-ui/react-icons";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Calendar } from "@/components/ui/calendar";
import { format } from "date-fns";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { Cross1Icon, PlusIcon } from "@radix-ui/react-icons";
import MentionInput, { renderMentionText } from '@/components/MentionInput';
import type { CharacterRelationship } from '@/models/character';

// Type for individual chat messages
interface ChatMessage {
    id: string; 
    role: 'system' | 'ai' | 'user';
    content: string;
    timestamp: Date;
}

// Define custom renderers for Markdown outside the main component
// Use standard JSX syntax for component definitions
const markdownComponents = {
    pre: (props: any) => {
        const { node, children, ...rest } = props;
        // Use standard quotes, remove overflow-x-auto, add whitespace-pre-wrap
        return <pre className="bg-amber-50 p-2 rounded text-xs whitespace-pre-wrap" {...rest}>{children}</pre>;
    },
    code: (props: any) => {
        const { node, children, ...rest } = props;
        // Code blocks can remain as they were
        return <code className="bg-amber-50 rounded px-1 text-xs" {...rest}>{children}</code>;
    }
};

export default function CharacterDetailPage() {
  const { characterId } = useParams<{ characterId: string }>();
  const navigate = useNavigate();
  const [initialCharacter, setInitialCharacter] = useState<Character | null>(null);
  const [editedCharacter, setEditedCharacter] = useState<Character | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isGeneratingAvatar, setIsGeneratingAvatar] = useState(false);
  const [publicAvatarUrl, setPublicAvatarUrl] = useState<string | null>(null);
  const generationTriggeredRef = useRef(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const chatScrollAreaRef = useRef<HTMLDivElement>(null);

  // SSE-based avatar stream hook
  const {
    statusMessage: avatarMessage,
    isComplete: avatarComplete,
    error: avatarError,
    isConnected: avatarConnected,
    visualDescription: streamVisualDesc,
    imagePrompt: streamImagePrompt,
    avatarUrl: streamAvatarUrl,
  } = useAvatarStream(characterId, isGeneratingAvatar);

  // --- NEW: State for Deletion ---
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // --- NEW: State for Bio Editing ---
  const [editableBio, setEditableBio] = useState<string>('');
  const [isBioModified, setIsBioModified] = useState(false);
  const [isSavingBio, setIsSavingBio] = useState(false);
  const [bioError, setBioError] = useState<string | null>(null);

  // --- NEW: State for Birth Date Editing ---
  const [editableBirthDate, setEditableBirthDate] = useState<string>('');
  const [isBirthDateModified, setIsBirthDateModified] = useState(false);
  const [isSavingBirthDate, setIsSavingBirthDate] = useState(false);
  const [birthDateError, setBirthDateError] = useState<string | null>(null);
  const [isGeneratingVisualDesc, setIsGeneratingVisualDesc] = useState(false);

  // --- Relationships ---
  const [familyCharacters, setFamilyCharacters] = useState<Character[]>([]);
  const [showAddRelModal, setShowAddRelModal] = useState(false);

  // Source photo signed URLs
  const [photoSignedUrls, setPhotoSignedUrls] = useState<Array<{ path: string; url: string }>>([]);

  // Person detection for avatar generation
  const [showPersonSelectModal, setShowPersonSelectModal] = useState(false);
  const [detectedPeople, setDetectedPeople] = useState<Array<{name: string; face_x?: number; face_y?: number; visual_note?: string}>>([]);
  const [detectingPeople, setDetectingPeople] = useState(false);
  const [detectPhotoUrl, setDetectPhotoUrl] = useState<string | null>(null);
  const [relTargetId, setRelTargetId] = useState('');
  const [relType, setRelType] = useState('');
  const [addingRel, setAddingRel] = useState(false);

  // Restore Helper to add a new message
  const addChatMessage = (role: ChatMessage['role'], content: string) => {
      setChatMessages(prev => [
          ...prev,
          { id: crypto.randomUUID(), role, content, timestamp: new Date() }
      ]);
  };

  // --- Data Fetching --- 
  const fetchCharacter = useCallback(async () => {
    if (!characterId) return;
    console.log(`(fetchCharacter) Fetching character ${characterId}..`);
    setLoading(true);
    setError(null);
    try {
      const data = await api.fetchCharacter(characterId);
      console.log("(fetchCharacter) Received data:", data);
      // --- Access using the actual key from JSON: 'birthdate' --- 
      const receivedBirthDate = (data as any).birthdate; // Use type assertion for now
      console.log(`(fetchCharacter) Received birthdate value: ${receivedBirthDate} (Type: ${typeof receivedBirthDate})`);
      // -------------------------------------------------------
      setInitialCharacter(data);
      setEditedCharacter(data);
      setEditableBio(data.bio || '');

      // Load family characters for @mentions and relationship selector
      try {
        const allChars = await api.fetchCharacters();
        setFamilyCharacters(allChars.filter(c => c.id !== characterId));
      } catch (e) {
        console.warn('Failed to load family characters:', e);
      }

      // Load signed URLs for source photos
      if (data.photo_paths?.length) {
        try {
          const result = await api.getPhotoSignedUrls(characterId);
          setPhotoSignedUrls(result.signed_urls || []);
        } catch (e) {
          console.warn('Failed to load photo signed URLs:', e);
        }
      }
      setIsBioModified(false);
      setBioError(null);
      
      // --- Use the correctly accessed value --- 
      const birthDateToSet = receivedBirthDate || '';
      console.log(`(fetchCharacter) Calling setEditableBirthDate with: '${birthDateToSet}'`);
      setEditableBirthDate(birthDateToSet);
      // --------------------------------------

      setIsBirthDateModified(false);
      setBirthDateError(null);
      const newPublicUrl = getPublicAvatarUrl(data?.avatar_url);
      setPublicAvatarUrl(newPublicUrl);
      if (newPublicUrl) {
          generationTriggeredRef.current = false;
      }
    } catch (err: any) {
      console.error("(fetchCharacter) Error:", err);
      setError(err.message || 'Failed to load character.');
      toast.error("Failed to load character details.");
    } finally {
      setLoading(false);
    }
  }, [characterId]);

  // --- Effect for initial fetch ---
  useEffect(() => {
    console.log("Running initial fetch effect");
    fetchCharacter();
  }, [fetchCharacter]); 

  // --- Avatar Generation Trigger ---
  useEffect(() => {
    // Trigger ONLY if:
    // - Character data is loaded
    // - Character has NO avatar_url
    // - Not already generating
    // - We haven't already triggered generation in this component lifecycle
    if (initialCharacter && !initialCharacter.avatar_url && !isGeneratingAvatar && !generationTriggeredRef.current) {
      console.log("(Trigger Effect) Conditions met. Triggering generation.");
      generationTriggeredRef.current = true;
      // Add initial chat message
      addChatMessage('ai', "Okay, I'll start generating an avatar based on the photo(s). You'll see my steps here.");

      const triggerApiCall = async () => {
        if (!initialCharacter.id) return;
        try {
          // Step 1: Detect people in photo first
          addChatMessage('ai', "Checking who's in the photo...");
          setDetectingPeople(true);
          const detection = await api.detectPeopleInPhoto(initialCharacter.id);
          setDetectingPeople(false);
          const people = detection.detected_people || [];

          if (people.length > 1) {
            // Multiple people detected — ask user which one is the character
            addChatMessage('ai', `I see ${people.length} people in this photo. Please select which one is ${initialCharacter.name}.`);
            setDetectedPeople(people);
            // Get signed URL for the photo to show in modal
            try {
              const urls = await api.getPhotoSignedUrls(initialCharacter.id);
              if (urls.signed_urls?.length) setDetectPhotoUrl(urls.signed_urls[0].url);
            } catch { /* ignore */ }
            setShowPersonSelectModal(true);
            return; // Don't start avatar gen yet — modal will handle it
          }

          // Step 2: Single person or no detection — proceed directly
          console.log(`(Trigger Effect) Calling api.generateCharacterAvatar for ${initialCharacter.id}...`);
          await api.generateCharacterAvatar(initialCharacter.id);
          toast.info("Avatar generation process started.");
          setIsGeneratingAvatar(true);
        } catch (err: any) {
          console.error("(Trigger Effect) API call failed:", err);
          setDetectingPeople(false);
          const errorMsg = err.response?.data?.detail || err.message || 'Failed to start avatar generation.';
          setError(prev => prev ? `${prev}\n${errorMsg}` : errorMsg);
          addChatMessage('system', `Error during generation: ${errorMsg}`);
          toast.error(errorMsg);
          generationTriggeredRef.current = false;
        }
      };
      triggerApiCall();
    }
  }, [initialCharacter, isGeneratingAvatar]);

  // --- SSE Stream: React to avatar progress updates ---
  useEffect(() => {
    if (avatarMessage) {
      addChatMessage('system', avatarMessage);
    }
  }, [avatarMessage]);

  useEffect(() => {
    if (streamVisualDesc) {
      addChatMessage('ai', `📝 Visual Description:\n${streamVisualDesc}`);
    }
  }, [streamVisualDesc]);

  useEffect(() => {
    if (streamImagePrompt) {
      addChatMessage('ai', `🎨 Image Prompt:\n${streamImagePrompt}`);
    }
  }, [streamImagePrompt]);

  useEffect(() => {
    if (streamAvatarUrl) {
      addChatMessage('ai', `✅ Avatar generated! Refreshing...`);
      // Refresh character data to show new avatar
      fetchCharacter();
    }
  }, [streamAvatarUrl]);

  // --- SSE Stream: React to completion ---
  useEffect(() => {
    if (avatarComplete && isGeneratingAvatar) {
      console.log("(SSE) Avatar generation complete. Refetching character...");
      addChatMessage('ai', "All done! The new avatar should be ready.");
      toast.success("Avatar generation complete!");
      setIsGeneratingAvatar(false);
      fetchCharacter();
    }
  }, [avatarComplete, isGeneratingAvatar, fetchCharacter]);

  // --- SSE Stream: React to errors ---
  useEffect(() => {
    if (avatarError && isGeneratingAvatar) {
      console.error("(SSE) Avatar generation error:", avatarError);
      setError(prev => prev ? `${prev}\n${avatarError}` : avatarError);
      addChatMessage('system', `Error during generation: ${avatarError}`);
      toast.error(`Avatar generation failed: ${avatarError}`);
      setIsGeneratingAvatar(false);
    }
  }, [avatarError, isGeneratingAvatar]);

  // Restore Effect to scroll chat to bottom
  useEffect(() => {
      if (chatScrollAreaRef.current) {
          chatScrollAreaRef.current.scrollTo({ top: chatScrollAreaRef.current.scrollHeight, behavior: 'smooth' });
      }
  }, [chatMessages]);

  // --- NEW: Save Bio Handler ---
  const handleSaveBio = async () => {
    if (!characterId || !editedCharacter) {
      setBioError("Character data is missing.");
      toast.error("Cannot save bio: Character data missing.");
      return;
    }

    setIsSavingBio(true);
    setBioError(null);
    console.log(`Attempting to save bio for character ${characterId}...`);

    try {
      // Assume api.updateCharacter exists and accepts ID and partial data
      const updatedCharacter = await api.updateCharacter(characterId, { bio: editableBio });
      
      // Update local state
      setEditedCharacter(prev => prev ? { ...prev, bio: updatedCharacter.bio } : null);
      setEditableBio(updatedCharacter.bio || '');
      setIsBioModified(false);

      toast.success(`Bio for '${editedCharacter.name}' updated successfully.`);

      // Auto-detect relationships from @mentions in bio
      const bio = updatedCharacter.bio || '';
      const mentionRegex = /@\{([^}]+)\}/g;
      let match;
      const existingRelIds = new Set((initialCharacter?.relationships || []).map(r => r.to_character_id));

      while ((match = mentionRegex.exec(bio)) !== null) {
        const mentionName = match[1];
        const mentionedChar = familyCharacters.find(c => c.name === mentionName);
        if (!mentionedChar || existingRelIds.has(mentionedChar.id)) continue;

        // Extract relationship context: words around the @mention
        const fullText = bio;
        const mentionStart = match.index;
        const mentionEnd = match.index + match[0].length;
        const before = fullText.slice(Math.max(0, mentionStart - 40), mentionStart).trim();
        const after = fullText.slice(mentionEnd, mentionEnd + 40).trim();

        // Get the closest meaningful words (strip punctuation, take last/first few words)
        const beforeWords = before.split(/\s+/).slice(-3).join(' ');
        const afterWords = after.split(/[\s,.!?]+/).slice(0, 3).join(' ');
        const relType = afterWords || beforeWords || 'connected';

        try {
          const rel = await api.addRelationship(characterId, {
            to_character_id: mentionedChar.id,
            relationship_type: relType,
          });
          setInitialCharacter(prev => prev ? {
            ...prev,
            relationships: [...(prev.relationships || []), rel],
          } : null);
          existingRelIds.add(mentionedChar.id);
          toast.success(`Relationship added: ${mentionName} — ${relType}`);
        } catch (e) {
          // Silently skip if duplicate or error
        }
      }
    } catch (err: any) {
      console.error("Error saving bio:", err);
      const errorMsg = err.response?.data?.detail || err.message || 'Failed to save bio.';
      setBioError(errorMsg);
      toast.error(`Bio update failed: ${errorMsg}`);
      // Optionally revert editableBio to original character.bio here if desired
    } finally {
      setIsSavingBio(false);
    }
  };

  // --- NEW: Save Birth Date Handler ---
  const handleSaveBirthDate = async () => {
    if (!characterId || !editedCharacter) {
      setBirthDateError("Character data is missing.");
      toast.error("Cannot save birth date: Character data missing.");
      return;
    }

    // Basic validation (optional, enhance as needed)
    // Example: Check if it's a valid date format (YYYY-MM-DD)
    const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
    if (editableBirthDate && !dateRegex.test(editableBirthDate)) {
        setBirthDateError("Please use YYYY-MM-DD format.");
        toast.error("Invalid date format. Use YYYY-MM-DD.");
        return;
    }

    setIsSavingBirthDate(true);
    setBirthDateError(null);
    console.log(`Attempting to save birth date for character ${characterId}...`);

    try {
      // Assume api.updateCharacter exists and accepts ID and partial data
      const updatedCharacter = await api.updateCharacter(characterId, { 
        birth_date: editableBirthDate || null // Send null if empty string
      });
      
      // Update local state optimistically or with response data
      setEditedCharacter(prev => prev ? { ...prev, birth_date: updatedCharacter.birth_date } : null); 
      setEditableBirthDate(updatedCharacter.birth_date || ''); // Ensure editableBirthDate matches saved state
      setIsBirthDateModified(false); // Reset modification status
      
      toast.success(`Birth date for '${editedCharacter.name}' updated successfully.`);
    } catch (err: any) {
      console.error("Error saving birth date:", err);
      const errorMsg = err.response?.data?.detail || err.message || 'Failed to save birth date.';
      setBirthDateError(errorMsg);
      toast.error(`Birth date update failed: ${errorMsg}`);
    } finally {
      setIsSavingBirthDate(false);
    }
  };

  // --- Generate Visual Description ---
  const handleGenerateVisualDescription = async () => {
    if (!characterId) return;
    setIsGeneratingVisualDesc(true);
    try {
      const result = await api.generateVisualDescription(characterId);
      setInitialCharacter(prev => prev ? { ...prev, visual_description: result.visual_description } : null);
      setEditedCharacter(prev => prev ? { ...prev, visual_description: result.visual_description } : null);
      toast.success("Visual description generated.");
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || 'Failed to generate visual description.';
      toast.error(errorMsg);
    } finally {
      setIsGeneratingVisualDesc(false);
    }
  };

  // --- NEW: Delete Handler ---
  const handleDeleteCharacter = async () => {
    if (!characterId) {
      setDeleteError("Character ID is missing.");
      toast.error("Cannot delete character: ID missing.");
      return;
    }

    setIsDeleting(true);
    setDeleteError(null);
    console.log(`Attempting to delete character ${characterId}...`);

    try {
      await api.deleteCharacter(characterId);
      toast.success(`Character '${editedCharacter?.name || 'Unknown'}' deleted successfully.`);
      setIsDeleting(false);
      setIsDeleteDialogOpen(false);
      navigate('/characters'); // Redirect to character list page after deletion
    } catch (err: any) {
      console.error("Error deleting character:", err);
      const errorMsg = err.response?.data?.detail || err.message || 'Failed to delete character.';
      setDeleteError(errorMsg);
      toast.error(`Deletion failed: ${errorMsg}`);
      setIsDeleting(false);
      // Keep the dialog open on error? Or close it? Let's close it for now.
      // setIsDeleteDialogOpen(false); 
    }
  };

  // --- Render Logic ---

  if (loading && !initialCharacter) { // Show skeleton only on initial load
    return (
        <div className="container mx-auto p-4 space-y-4">
            <Skeleton className="h-8 w-1/3" />
            <Skeleton className="h-4 w-1/2" />
            <Card><CardContent className="pt-6">
                {/* Skeleton for Avatar area */}
                <div className="aspect-square bg-muted rounded flex items-center justify-center">
                    <Skeleton className="h-24 w-24 rounded-full" /> 
                </div>
            </CardContent></Card>
             {/* Placeholder for chat */}
             <Card><CardContent><Skeleton className="h-60 w-full" /></CardContent></Card>
        </div>
    );
  }

  // Show full page error if character couldn't be loaded initially
  if (error && !initialCharacter) { 
    return (
      <div className="container mx-auto p-4">
        <Alert variant="destructive">
            <ExclamationTriangleIcon className="h-4 w-4" />
            <AlertTitle>Error Loading Character</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
        </Alert>
      </div>
    );
  }

  // If character fetch succeeded but maybe errored later, or no char data
  if (!initialCharacter) {
     return <div className="container mx-auto p-4">Character data is unavailable.</div>; 
  }

  // --- Render Character Details --- 
  return (
    <div className="container mx-auto p-4 grid grid-cols-1 md:grid-cols-3 gap-6">
      {/* Left Column: Character Details & Avatar */}
      <div className="md:col-span-1 space-y-4">
        <Card>
          <CardHeader className="flex flex-row items-start justify-between pb-2">
            <div> 
                <CardTitle>{initialCharacter.name}</CardTitle>
            </div>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="ml-auto -mt-1 -mr-2">
                  <DotsHorizontalIcon className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem 
                  className="text-red-600 focus:text-red-700 focus:bg-red-50"
                  onSelect={(event: Event) => { 
                     event.preventDefault(); 
                     setDeleteError(null);
                     setIsDeleteDialogOpen(true);
                  }}
                >
                  Delete Character
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </CardHeader>
          <CardContent className="space-y-4">
             <div className="space-y-2">
                <Label htmlFor="character-bio">Bio</Label>
                <MentionInput
                    value={editableBio}
                    onChange={(val) => {
                        setEditableBio(val);
                        setIsBioModified(true);
                        setBioError(null);
                    }}
                    characters={familyCharacters}
                    placeholder="Enter a bio... Use @ to mention other characters"
                    rows={4}
                    className="min-h-[100px]"
                />
                {isBioModified && (
                    <div className="flex justify-end items-center gap-2">
                       {bioError && <p className="text-xs text-red-600">{bioError}</p>}
                       <Button 
                          size="sm" 
                          onClick={handleSaveBio} 
                          disabled={isSavingBio}
                       >
                          {isSavingBio ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                          {isSavingBio ? 'Saving...' : 'Save Bio'}
                       </Button>
                    </div>
                )}
                {!isBioModified && !editableBio && (
                     <p className="text-sm text-muted-foreground italic mt-1">(No bio provided)</p>
                )}
             </div>
             
             {/* --- Replace Birth Date Input with Shadcn Date Picker --- */}
             <div className="space-y-2">
                <Label htmlFor="character-birthdate">Birth Date</Label>
                <Popover>
                  <PopoverTrigger asChild>
                    <Button
                      variant={"outline"}
                      className={cn(
                        "w-full justify-start text-left font-normal",
                        !editableBirthDate && "text-muted-foreground"
                      )}
                    >
                      <CalendarIcon className="mr-2 h-4 w-4" />
                      {editableBirthDate ? (
                        format(new Date(editableBirthDate + 'T00:00:00'), 'yyyy-MM-dd') // Force correct parsing
                      ) : (
                        <span>Pick a date</span>
                      )}
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0" align="start">
                    <Calendar
                      mode="single"
                      // Parse the YYYY-MM-DD string into a Date object for the calendar
                      // Add time part to avoid timezone issues during parsing
                      selected={editableBirthDate ? new Date(editableBirthDate + 'T00:00:00') : undefined}
                      onSelect={(date: Date | undefined) => {
                        if (date) {
                          // Format selected date back to YYYY-MM-DD string
                          const formattedDate = format(date, 'yyyy-MM-dd');
                          setEditableBirthDate(formattedDate);
                          setIsBirthDateModified(true);
                          setBirthDateError(null); // Clear error on valid selection
                        } else {
                          // Handle case where date is cleared
                          setEditableBirthDate(''); 
                          setIsBirthDateModified(true);
                          setBirthDateError(null);
                        }
                      }}
                      initialFocus
                      // Optional: Add date constraints if needed
                      // disabled={(date) => date > new Date() || date < new Date("1900-01-01")}
                    />
                  </PopoverContent>
                </Popover>
                {/* Keep save button logic separate for now */}
                {isBirthDateModified && (
                    <div className="flex justify-end items-center gap-2">
                       {birthDateError && <p className="text-xs text-red-600">{birthDateError}</p>}
                       <Button 
                          size="sm" 
                          onClick={handleSaveBirthDate} 
                          disabled={isSavingBirthDate}
                       >
                          {isSavingBirthDate ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                          {isSavingBirthDate ? 'Saving...' : 'Save Birth Date'}
                       </Button>
                    </div>
                )}
                 {!isBirthDateModified && !editableBirthDate && (
                     <p className="text-sm text-muted-foreground italic mt-1">(No birth date provided)</p>
                )}
             </div>
             {/* --- End Birth Date Input --- */}

             {/* Visual Description (read-only, generated by AI) */}
             <div className="space-y-2">
               <div className="flex items-center justify-between">
                 <Label>Visual Description</Label>
                 <Button
                   size="sm"
                   variant="outline"
                   onClick={handleGenerateVisualDescription}
                   disabled={isGeneratingVisualDesc}
                 >
                   {isGeneratingVisualDesc ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                   {initialCharacter.visual_description ? 'Regenerate' : 'Generate'}
                 </Button>
               </div>
               {initialCharacter.visual_description ? (
                 <p className="text-sm text-muted-foreground bg-muted rounded p-2">
                   {initialCharacter.visual_description}
                 </p>
               ) : (
                 <p className="text-sm text-muted-foreground italic">(No visual description generated yet)</p>
               )}
             </div>

             {/* Source Photos */}
             {photoSignedUrls.length > 0 && (
               <div className="space-y-2">
                 <Label className="text-xs text-muted-foreground">Source Photos</Label>
                 <div className="grid grid-cols-3 gap-2">
                   {photoSignedUrls.map((photo, i) => (
                     <img
                       key={i}
                       src={photo.url}
                       alt={`Source photo ${i + 1}`}
                       className="w-full h-20 object-cover rounded-md border"
                     />
                   ))}
                 </div>
               </div>
             )}

             {/* Relationships */}
             <div className="space-y-2">
               <div className="flex items-center justify-between">
                 <Label>Relationships</Label>
                 <Button size="sm" variant="ghost" onClick={() => setShowAddRelModal(true)}>
                   <PlusIcon className="h-4 w-4 mr-1" /> Add
                 </Button>
               </div>
               {(initialCharacter.relationships ?? []).length > 0 ? (
                 <div className="space-y-1.5">
                   {(initialCharacter.relationships ?? []).map((rel) => (
                     <div key={rel.id} className="flex items-center gap-2 p-2 rounded-md bg-muted group/rel">
                       <Avatar className="w-7 h-7 flex-shrink-0">
                         <AvatarImage src={getPublicAvatarUrl(rel.to_character_avatar_url) || ''} />
                         <AvatarFallback className="text-[9px]">
                           {(rel.to_character_name || '?').slice(0, 2).toUpperCase()}
                         </AvatarFallback>
                       </Avatar>
                       <button
                         className="text-sm font-medium hover:underline"
                         onClick={() => navigate(`/characters/${rel.to_character_id}`)}
                       >
                         {rel.to_character_name || 'Unknown'}
                       </button>
                       <Badge variant="outline" className="text-xs">{rel.relationship_type}</Badge>
                       <button
                         className="ml-auto opacity-0 group-hover/rel:opacity-100 transition-opacity text-muted-foreground hover:text-destructive"
                         onClick={async () => {
                           try {
                             await api.deleteRelationship(characterId!, rel.id);
                             setInitialCharacter(prev => prev ? {
                               ...prev,
                               relationships: (prev.relationships || []).filter(r => r.id !== rel.id),
                             } : null);
                             toast.success('Relationship removed.');
                           } catch (e) {
                             toast.error('Failed to remove relationship.');
                           }
                         }}
                       >
                         <Cross1Icon className="h-3 w-3" />
                       </button>
                     </div>
                   ))}
                 </div>
               ) : (
                 <p className="text-sm text-muted-foreground italic">(No relationships yet)</p>
               )}
             </div>

             <Separator />

             <div className="aspect-square bg-muted rounded flex items-center justify-center relative group overflow-hidden">
                {
                    isGeneratingAvatar ? (
                        <div className='text-center p-4'>
                            <Loader2 className="h-8 w-8 animate-spin mx-auto mb-2" />
                            <p className="text-sm text-muted-foreground">Generating Avatar...</p>
                            {avatarConnected && (
                              <p className="text-xs text-muted-foreground mt-1">{avatarMessage}</p>
                            )}
                        </div>
                    ) : publicAvatarUrl ? (
                         <Avatar className="h-full w-full rounded-none">
                             <AvatarImage src={publicAvatarUrl} alt={initialCharacter.name} className="object-cover" />
                             <AvatarFallback className="text-4xl">
                                 {initialCharacter.name?.charAt(0).toUpperCase() || 'C'}
                            </AvatarFallback>
                         </Avatar>
                    ) : avatarError ? (
                        <div className='text-center p-4 text-destructive'>
                            <ExclamationTriangleIcon className="h-8 w-8 mx-auto mb-2" />
                            <p className="text-sm">Generation Failed</p>
                             <p className="text-xs mt-1">{avatarError || 'An error occurred.'}</p>
                        </div>
                     ) : (
                        <div className='text-center p-4'>
                             <p className="text-sm text-muted-foreground">No avatar generated yet.</p>
                        </div>
                     )
                }
             </div>
          </CardContent>
        </Card>
        
        {error && avatarError && (
             <Alert variant="destructive" className="mt-4">
                 <ExclamationTriangleIcon className="h-4 w-4" />
                 <AlertTitle>Generation Error</AlertTitle>
                 <AlertDescription>{error}</AlertDescription>
            </Alert>
        )}

        <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
              <AlertDialogDescription>
                This action cannot be undone. This will permanently delete the character
                '{initialCharacter.name}' and all associated data, including photos and the generated avatar.
                {deleteError && (
                    <Alert variant="destructive" className="mt-4">
                        <ExclamationTriangleIcon className="h-4 w-4" />
                        <AlertTitle>Deletion Error</AlertTitle>
                        <AlertDescription>{deleteError}</AlertDescription>
                    </Alert>
                )}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
              <AlertDialogAction 
                onClick={handleDeleteCharacter} 
                disabled={isDeleting}
                className="bg-red-600 hover:bg-red-700 focus:ring-red-500"
              >
                {isDeleting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                {isDeleting ? 'Deleting...' : 'Yes, delete character'}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>

      <div className="md:col-span-2">
        <Card className="flex flex-col h-[400px] md:h-[600px]"> 
          <CardHeader>
            <CardTitle>Avatar Generation Process</CardTitle>
            <CardDescription>Follow the AI's steps and refine the result later.</CardDescription>
          </CardHeader>
          <CardContent className="flex-grow overflow-hidden relative">
            <ScrollArea className="h-full absolute inset-0 pr-4" ref={chatScrollAreaRef}> 
                <div className="space-y-4 p-1">
                    {chatMessages.map((msg) => (
                        <div 
                            key={msg.id} 
                            className={cn(
                                "flex max-w-[85%] flex-col gap-2 rounded-lg px-3 py-2 text-sm", 
                                msg.role === 'user' && "ml-auto bg-primary text-primary-foreground",
                                msg.role === 'ai' && "bg-muted",
                                msg.role === 'system' && "bg-amber-100 text-amber-900 border border-amber-200 text-xs" 
                            )}
                        >
                           <div className="prose prose-sm max-w-none">
                               <ReactMarkdown 
                                    components={markdownComponents} 
                                >
                                    {msg.content}
                                </ReactMarkdown>
                            </div>
                        </div>
                    ))}
                </div>
            </ScrollArea>
          </CardContent>
        </Card>
      </div>

      {/* Person Selection Modal (for multi-person photos) */}
      <Dialog open={showPersonSelectModal} onOpenChange={(open) => {
        if (!open) {
          setShowPersonSelectModal(false);
          // If user closes without selecting, allow re-trigger
          generationTriggeredRef.current = false;
        }
      }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Who is {initialCharacter?.name}?</DialogTitle>
            <DialogDescription>
              Multiple people detected in the photo. Select which one is {initialCharacter?.name}.
            </DialogDescription>
          </DialogHeader>
          {/* Photo with face position indicators */}
          {detectPhotoUrl && (
            <div className="relative rounded-md overflow-hidden">
              <img src={detectPhotoUrl} alt="Source photo" className="w-full h-48 object-cover" />
              {detectedPeople.map((person, i) => {
                const x = person.face_x ?? (detectedPeople.length === 1 ? 50 : 15 + (70 / (detectedPeople.length - 1)) * i);
                const y = person.face_y ?? 35;
                return (
                  <div key={i} className="absolute flex flex-col items-center"
                    style={{ left: `${Math.max(8, Math.min(92, x))}%`, top: `${Math.min(85, y + 15)}%`, transform: 'translate(-50%, 0)', zIndex: 10 }}>
                    <svg width="8" height="6" viewBox="0 0 8 6" className="drop-shadow-md -mb-0.5">
                      <polygon points="4,0 0,6 8,6" fill="white" fillOpacity="0.95" />
                    </svg>
                    <span className="px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-white/90 shadow-md backdrop-blur-sm">
                      {i + 1}
                    </span>
                  </div>
                );
              })}
            </div>
          )}

          <div className="space-y-2">
            {detectedPeople.map((person, i) => (
              <button
                key={i}
                className="w-full text-left p-3 rounded-md border hover:bg-accent transition-colors flex items-center gap-3"
                onClick={async () => {
                  if (!characterId || person.face_x == null) return;
                  setShowPersonSelectModal(false);
                  try {
                    addChatMessage('ai', `Cropping photo to focus on the selected person...`);
                    await api.cropPhoto(characterId, person.face_x);
                    // Refresh source photo signed URLs after crop
                    try {
                      const urls = await api.getPhotoSignedUrls(characterId);
                      setPhotoSignedUrls(urls.signed_urls || []);
                    } catch { /* ignore */ }
                    addChatMessage('ai', 'Photo cropped. Starting avatar generation...');
                    await api.generateCharacterAvatar(characterId);
                    toast.info("Avatar generation started.");
                    setIsGeneratingAvatar(true);
                  } catch (err: any) {
                    const msg = err.response?.data?.detail || 'Failed to process.';
                    addChatMessage('system', `Error: ${msg}`);
                    toast.error(msg);
                    generationTriggeredRef.current = false;
                  }
                }}
              >
                <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-sm font-medium">
                  {i + 1}
                </div>
                <div>
                  <p className="text-sm font-medium">
                    {person.name?.startsWith('unknown') ? `Person ${i + 1}` : person.name}
                  </p>
                  {person.visual_note && (
                    <p className="text-xs text-muted-foreground">{person.visual_note}</p>
                  )}
                </div>
              </button>
            ))}
          </div>
        </DialogContent>
      </Dialog>

      {/* Add Relationship Modal */}
      <Dialog open={showAddRelModal} onOpenChange={setShowAddRelModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Relationship</DialogTitle>
            <DialogDescription>Connect {initialCharacter?.name} to another character.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Character</Label>
              <div className="grid grid-cols-1 gap-1.5 max-h-48 overflow-y-auto">
                {familyCharacters.map((char) => (
                  <button
                    key={char.id}
                    className={cn(
                      "flex items-center gap-2 p-2 rounded-md text-sm text-left transition-colors",
                      relTargetId === char.id ? "bg-accent ring-1 ring-primary" : "hover:bg-accent"
                    )}
                    onClick={() => setRelTargetId(char.id)}
                  >
                    <Avatar className="w-7 h-7">
                      <AvatarImage src={getPublicAvatarUrl(char.avatar_url) || ''} />
                      <AvatarFallback className="text-[9px]">{char.name.slice(0, 2).toUpperCase()}</AvatarFallback>
                    </Avatar>
                    {char.name}
                  </button>
                ))}
              </div>
            </div>
            <div className="space-y-2">
              <Label>Relationship</Label>
              <Input
                placeholder="e.g., best friend, brother, mom..."
                value={relType}
                onChange={(e) => setRelType(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setShowAddRelModal(false)}>Cancel</Button>
            <Button
              disabled={!relTargetId || !relType.trim() || addingRel}
              onClick={async () => {
                if (!characterId || !relTargetId || !relType.trim()) return;
                setAddingRel(true);
                try {
                  const rel = await api.addRelationship(characterId, {
                    to_character_id: relTargetId,
                    relationship_type: relType.trim(),
                  });
                  setInitialCharacter(prev => prev ? {
                    ...prev,
                    relationships: [...(prev.relationships || []), rel],
                  } : null);
                  toast.success('Relationship added!');
                  setShowAddRelModal(false);
                  setRelTargetId('');
                  setRelType('');
                } catch (err: any) {
                  toast.error(err?.response?.data?.detail || 'Failed to add relationship.');
                } finally {
                  setAddingRel(false);
                }
              }}
            >
              {addingRel ? 'Adding...' : 'Add'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}