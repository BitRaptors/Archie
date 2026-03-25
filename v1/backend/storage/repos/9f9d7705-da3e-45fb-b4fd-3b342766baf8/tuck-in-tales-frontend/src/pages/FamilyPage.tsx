import React, { useState, useEffect, useCallback } from 'react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { api } from '@/api/client'; // Import the API client
import type { Character, CharacterSummary } from '@/models/character'; // Import Character types
import type { FamilyDetailResponse as FamilyDetailResponseData } from '@/models/family'; // Rename the import alias to avoid conflict with local interface
import { useAuth } from '@/context/AuthContext'; // To ensure user is loaded
// Import Shadcn Avatar components
import {
  Avatar,
  AvatarFallback,
  AvatarImage,
} from "@/components/ui/avatar";
// Import icons for edit/save/cancel
import { Pencil, Check, X, ChevronsUpDown, Loader2 } from 'lucide-react'; // Add Loader2 for loading state
// Import Select components
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
// --- Add Combobox Imports ---
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList, // Often used with Command
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils"; // Add import for cn utility
// --- Add Checkbox Import ---
import { Checkbox } from "@/components/ui/checkbox";
// -------------------------

// Define a type for the family data structure returned by the API
interface FamilyMember {
  id: string;
  display_name: string | null; // Use display_name from API
  email: string | null; // Still keeping email for now
  avatar_url: string | null; // Add avatar URL
}

// --- Local FamilyDetails Interface (Keep this as is) ---
interface FamilyDetails {
  id: string; // Assuming UUID comes as string from API
  name: string | null;
  join_code: string | null;
  members: FamilyMember[];
  default_language?: string | null; // Add here
  main_characters?: CharacterSummary[]; // Add main_characters field
}
// --------------------------------------------------------

// Define a more comprehensive list of supported languages
const SUPPORTED_LANGUAGES = [
  { code: "en", name: "English" },
  { code: "es", name: "Spanish" },
  { code: "fr", name: "French" },
  { code: "de", name: "German" },
  { code: "it", name: "Italian" },
  { code: "pt", name: "Portuguese (Portugal, Brazil)" },
  { code: "ru", name: "Russian" },
  { code: "ja", name: "Japanese" },
  { code: "ko", name: "Korean" },
  { code: "zh", name: "Chinese (Simplified)" },
//   { code: "zh-TW", name: "Chinese (Traditional)" }, // Example region specific
  { code: "hi", name: "Hindi" },
  { code: "ar", name: "Arabic" },
  { code: "bn", name: "Bengali" },
  { code: "ur", name: "Urdu" },
  { code: "id", name: "Indonesian" },
  { code: "nl", name: "Dutch" },
  { code: "tr", name: "Turkish" },
  { code: "vi", name: "Vietnamese" },
  { code: "pl", name: "Polish" },
  { code: "th", name: "Thai" },
  { code: "fa", name: "Persian (Farsi)" },
  { code: "ro", name: "Romanian" },
  { code: "el", name: "Greek" },
  { code: "he", name: "Hebrew" },
  { code: "sv", name: "Swedish" },
  { code: "no", name: "Norwegian" },
  { code: "da", name: "Danish" },
  { code: "fi", name: "Finnish" },
  { code: "cs", name: "Czech" },
  { code: "hu", name: "Hungarian" },
  { code: "ms", name: "Malay" },
  { code: "sw", name: "Swahili" },
  { code: "af", name: "Afrikaans" },
  { code: "fil", name: "Filipino" },
  { code: "uk", name: "Ukrainian" },
  { code: "bg", name: "Bulgarian" },
  { code: "sk", name: "Slovak" },
  { code: "hr", name: "Croatian" },
  { code: "sr", name: "Serbian" },
  { code: "lt", name: "Lithuanian" },
  { code: "lv", name: "Latvian" },
  { code: "et", name: "Estonian" },
  { code: "sl", name: "Slovenian" },
  { code: "is", name: "Icelandic" },
  { code: "ga", name: "Irish" },
  { code: "cy", name: "Welsh" },
  { code: "ca", name: "Catalan" },
  { code: "eu", name: "Basque" },
  { code: "gl", name: "Galician" },
  // Add ~30-50 more common languages or use a library if available
];

// Add the special option to the list for easier handling in Combobox
const LANGUAGES_WITH_PROMPT_OPTION = [
  { code: "__none__", name: "* Use Prompt Language *" },
  ...SUPPORTED_LANGUAGES,
];

export default function FamilyPage() {
  const { currentUser, loading: authLoading } = useAuth(); 
  const [familyData, setFamilyData] = useState<FamilyDetails | null>(null);
  const [loadingFamily, setLoadingFamily] = useState(true);
  const [errorFamily, setErrorFamily] = useState<string | null>(null);

  const [joinCode, setJoinCode] = useState('');
  const [createLoading, setCreateLoading] = useState(false);
  const [joinLoading, setJoinLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // --- State for Editing Name ---
  const [isEditingName, setIsEditingName] = useState(false);
  const [editedName, setEditedName] = useState('');
  // --- State for Editing Language ---
  const [editedLanguage, setEditedLanguage] = useState<string | undefined>(undefined);
  const [isEditingLanguage, setIsEditingLanguage] = useState(false);
  // --- Loading state for settings update --- 
  const [updateSettingsLoading, setUpdateSettingsLoading] = useState(false);
  // --- Add state for Combobox ---
  const [comboboxOpen, setComboboxOpen] = useState(false);
  // --- State for Characters ---
  const [characters, setCharacters] = useState<Character[]>([]);
  const [loadingCharacters, setLoadingCharacters] = useState(false);
  const [errorCharacters, setErrorCharacters] = useState<string | null>(null);
  const [updatingMainChars, setUpdatingMainChars] = useState<{ [key: string]: boolean }>({});
  // ----------------------------

  // Function to fetch family details
  const fetchFamily = useCallback(async () => {
    if (!currentUser) return; // Don't fetch if user isn't loaded
    
    setLoadingFamily(true);
    setErrorFamily(null);
    try {
      const data = await api.fetchFamilyDetails();
      setFamilyData(data);
      // Set initial edited name and language when data loads
      if (data) {
        setEditedName(data.name || '');
        // Ensure initial language state is set correctly (undefined if null/empty)
        setEditedLanguage(data.default_language || undefined);
      }
    } catch (err: any) {
      console.error("Fetch family details error:", err);
      // Don't set error if it's just 404 (user not in family) - API returns null/empty
      if (err.response?.status !== 404) {
           setErrorFamily('Failed to load family details.');
      } else {
          setFamilyData(null); // Ensure data is null if not found
      }
    } finally {
      setLoadingFamily(false);
    }
  }, [currentUser]);

  // --- NEW: Function to fetch characters ---
  const fetchCharacters = useCallback(async () => {
    if (!currentUser) return;
    setLoadingCharacters(true);
    setErrorCharacters(null);
    try {
      const data = await api.fetchCharacters();
      setCharacters(data);
    } catch (err) {
      console.error("Fetch characters error:", err);
      setErrorCharacters('Failed to load characters.');
    } finally {
      setLoadingCharacters(false);
    }
  }, [currentUser]);
  // ---------------------------------------

  // Fetch family details on mount or when user changes
  useEffect(() => {
    if (!authLoading && currentUser) { // Only fetch when auth is resolved and user exists
        fetchFamily();
        fetchCharacters(); // Fetch characters as well
    }
  }, [currentUser, authLoading, fetchFamily, fetchCharacters]);

  const handleCreateFamily = async () => {
    setCreateLoading(true);
    setActionError(null);
    console.log('Attempting to create family...');
    try {
      // TODO: Allow setting family name? Defaulting for now.
      await api.createFamily("My Family"); 
      console.log('Family created successfully');
      await fetchFamily(); // Re-fetch family details to update UI
    } catch (err: any) {
      console.error("Create family error:", err);
      setActionError(err.response?.data?.detail || 'Failed to create family.');
    } finally {
      setCreateLoading(false);
    }
  };

  const handleJoinFamily = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!joinCode.trim()) {
      setActionError('Please enter a join code.');
      return;
    }
    setJoinLoading(true);
    setActionError(null);
    console.log(`Attempting to join family with code: ${joinCode}...`);
    try {
      await api.joinFamily(joinCode);
      console.log('Joined family successfully');
      setJoinCode('');
      await fetchFamily(); // Re-fetch family details to update UI
    } catch (err: any) {
      console.error("Join family error:", err);
      setActionError(err.response?.data?.detail || 'Failed to join family. Check the code and try again.');
    } finally {
      setJoinLoading(false);
    }
  };

  // --- Handlers for Editing Name ---
  const handleEditName = () => {
    if (familyData) {
      setEditedName(familyData.name || ''); // Reset to current name on edit start
      setIsEditingName(true);
    }
  };

  const handleCancelEdit = () => {
    setIsEditingName(false);
    setIsEditingLanguage(false);
    // Optionally reset editedName if needed, but might not be necessary
    // if(familyData) setEditedName(familyData.name || ''); 
    // if(familyData) setEditedLanguage(familyData.default_language || undefined);
  };

  // Rename and update save handler
  const handleSaveSettings = async () => {
    const nameToSave = editedName.trim();
    const langToSave = editedLanguage;

    // Basic validation
    if (!nameToSave) {
      setActionError('Family name cannot be empty.');
      return;
    }
    // Optional: Add validation for language if needed
    
    const updates: { name?: string; default_language?: string | null } = {};
    if (nameToSave !== familyData?.name) {
        updates.name = nameToSave;
    }
    if (langToSave !== familyData?.default_language) {
        updates.default_language = langToSave === undefined ? null : langToSave;
    }

    if (Object.keys(updates).length === 0) {
      setIsEditingName(false); // Close edit modes if nothing changed
      setIsEditingLanguage(false);
      return; // Nothing to save
    }

    setUpdateSettingsLoading(true);
    setActionError(null);
    try {
      const updatedFamily = await api.updateFamilySettings(updates);
      setFamilyData(prevData => ({
          ...prevData!,
          name: updatedFamily.name,
          default_language: updatedFamily.default_language
      }));
      setEditedLanguage(updatedFamily.default_language || undefined);
      setIsEditingName(false);
    } catch (err: any) {
      console.error("Update family settings error:", err);
      setActionError(err.response?.data?.detail || 'Failed to update family settings.');
    } finally {
      setUpdateSettingsLoading(false);
    }
  };
  // ---------------------------------

  // --- NEW: Handler for Main Character Checkbox Change ---
  const handleMainCharacterChange = async (characterId: string, isChecked: boolean) => {
    setUpdatingMainChars(prev => ({ ...prev, [characterId]: true }));
    setActionError(null); // Clear previous errors
    
    try {
      if (isChecked) {
        await api.setMainCharacter(characterId);
        // console.log(`Successfully set ${characterId} as main character.`); // Optional success log
      } else {
        await api.removeMainCharacter(characterId);
        // console.log(`Successfully removed ${characterId} as main character.`); // Optional success log
      }

      // --- Re-fetch family data AFTER successful API call --- 
      await fetchFamily(); 
      // ------------------------------------------------------

    } catch (err: any) {
      console.error(`Failed to ${isChecked ? 'set' : 'remove'} main character:`, err);
      setActionError(err.response?.data?.detail || `Failed to update main character status.`);
      // No need to revert state, as we didn't change it optimistically
    } finally {
      setUpdatingMainChars(prev => ({ ...prev, [characterId]: false }));
    }
  };
  // -----------------------------------------------------

  // Show loading state while checking auth or fetching family info
  if (authLoading || loadingFamily) {
    return <div className="container mx-auto p-4">Loading family information...</div>;
  }

  // Show error if fetching failed (and it wasn't a 404)
  if (errorFamily) {
      return <div className="container mx-auto p-4 text-red-500">Error: {errorFamily}</div>;
  }

  const userHasFamily = !!familyData;

  // Helper to get initials for Avatar Fallback
  const getInitials = (name: string | null | undefined): string => {
    if (!name) return "?";
    const names = name.split(' ');
    if (names.length === 1) return names[0].charAt(0).toUpperCase();
    return (names[0].charAt(0) + names[names.length - 1].charAt(0)).toUpperCase();
  };

  // Determine which characters are currently main characters
  const mainCharacterIds = new Set(familyData?.main_characters?.map(c => c.id) || []);

  return (
    <div className="container mx-auto p-4 max-w-2xl">
      {userHasFamily ? (
        // Display Family Details View
        <Card>
          <CardHeader>
            {/* --- Conditional Rendering for Name/Edit Input --- */}
            {isEditingName ? (
              <div className="flex items-center space-x-2">
                <Input 
                  value={editedName}
                  onChange={(e) => setEditedName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !updateSettingsLoading && editedName.trim()) {
                      e.preventDefault();
                      handleSaveSettings(); // Use combined save handler
                    } else if (e.key === 'Escape' && !updateSettingsLoading) {
                      handleCancelEdit();
                    }
                  }}
                  placeholder="Enter family name"
                  className="flex-grow"
                  disabled={updateSettingsLoading}
                />
                <Button 
                  variant="ghost" 
                  size="icon" 
                  onClick={handleSaveSettings} // Use combined save handler
                  disabled={updateSettingsLoading || !editedName.trim()}
                  aria-label="Save name"
                >
                  <Check className={`h-4 w-4 ${updateSettingsLoading ? 'animate-spin' : ''}`} />
                </Button>
                 <Button 
                  variant="ghost" 
                  size="icon" 
                  onClick={handleCancelEdit} 
                  disabled={updateSettingsLoading}
                  aria-label="Cancel edit"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ) : (
              <div className="flex items-center space-x-2">
                 <CardTitle>Your Family: {familyData.name || 'Unnamed Family'}</CardTitle>
                 <Button variant="ghost" size="icon" onClick={handleEditName} aria-label="Edit family name">
                    <Pencil className="h-4 w-4" />
                 </Button>
              </div>
            )}
            {/* --- Default Language Setting (using Combobox) --- */}
            <div>
              <h3 className="text-lg font-semibold mb-2 mt-4">Default Story Language</h3>
              <div className="flex items-center space-x-2">
                {/* --- Combobox Start --- */}
                <Popover open={comboboxOpen} onOpenChange={setComboboxOpen}>
                  <PopoverTrigger asChild>
                    <Button
                      variant="outline"
                      role="combobox"
                      aria-expanded={comboboxOpen}
                      className="w-[250px] justify-between" // Adjust width as needed
                      disabled={updateSettingsLoading}
                    >
                      {editedLanguage
                        ? LANGUAGES_WITH_PROMPT_OPTION.find((lang) => lang.code === editedLanguage)?.name
                        : "* Use Prompt Language *"} {/* Show placeholder text */}
                      <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-[250px] p-0"> {/* Adjust width */}
                    <Command>
                      <CommandInput placeholder="Search language..." />
                      <CommandList> {/* Ensure items are scrollable */}
                        <CommandEmpty>No language found.</CommandEmpty>
                        <CommandGroup>
                          {LANGUAGES_WITH_PROMPT_OPTION.map((lang) => (
                            <CommandItem
                              key={lang.code}
                              value={lang.name} // Filter/Value is now the name
                              onSelect={(currentValue: string) => { // currentValue is lang.name
                                // Find the language object by the selected name
                                const selectedLang = LANGUAGES_WITH_PROMPT_OPTION.find(l => l.name === currentValue);
                                const selectedCode = selectedLang ? selectedLang.code : undefined;

                                // Set state using the CODE
                                setEditedLanguage(selectedCode === "__none__" ? undefined : selectedCode);
                                setComboboxOpen(false);
                              }}
                            >
                              <Check
                                className={cn(
                                  "mr-2 h-4 w-4",
                                  // Comparison still uses the code
                                  editedLanguage === lang.code ? "opacity-100" : "opacity-0"
                                )}
                              />
                              {/* Display the name */}
                              {lang.name}
                            </CommandItem>
                          ))}
                        </CommandGroup>
                      </CommandList>
                    </Command>
                  </PopoverContent>
                </Popover>
                {/* --- End Combobox --- */}

                {/* Save Button (only enable if language changed) */}
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleSaveSettings}
                  disabled={updateSettingsLoading || editedLanguage === (familyData?.default_language || undefined)} // Compare with initial fetched state
                  aria-label="Save language"
                >
                   <Check className={`h-4 w-4 ${updateSettingsLoading ? 'animate-spin' : ''}`} />
                </Button>
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                 Default language used for stories generated without a specific language request.
              </p>
            </div>
            {/* ------------------------------ */}
            <CardDescription>Manage your family members and settings.</CardDescription>
          </CardHeader>
           {/* Show action error related to name update or main character update */}
           {actionError && <p className="text-sm text-red-500 dark:text-red-400 px-6 pb-2">{actionError}</p>}

          <CardContent className="space-y-6"> {/* Increased spacing */}
            {familyData.join_code && (
                 <div>
                 <h3 className="text-lg font-semibold mb-2">Join Code</h3>
                 <p className="text-sm text-muted-foreground mb-1">Share this code with others to invite them:</p>
                 <div className="flex items-center space-x-2 p-3 bg-muted rounded-md">
                     <span className="font-mono text-lg flex-grow">{familyData.join_code}</span>
                     <Button variant="outline" size="sm" onClick={() => navigator.clipboard.writeText(familyData.join_code!)}>Copy</Button>
                 </div>
                 </div>
            )}
            <div>
              <h3 className="text-lg font-semibold mb-2">Members</h3>
              {familyData.members && familyData.members.length > 0 ? (
                <ul className="space-y-2">
                    {familyData.members.map(member => {
                      return (
                        <li key={member.id} className="flex items-center space-x-3 p-2 border rounded-md">
                            {/* Avatar */}
                            <Avatar className="h-8 w-8">
                                <AvatarImage src={member.avatar_url ?? undefined} alt={member.display_name || 'User Avatar'} />
                                <AvatarFallback>{getInitials(member.display_name)}</AvatarFallback>
                            </Avatar>
                            {/* Name and Email */}
                            <div className="flex-grow">
                                <span className="font-medium">{member.display_name || 'Unnamed User'}</span>
                                {member.email && <span className="block text-xs text-muted-foreground">{member.email}</span>}
                            </div>
                             {/* TODO: Add Remove Button here later, conditionally */} 
                        </li>
                      );
                    })}
                </ul>
              ) : (
                 <p className="text-sm text-muted-foreground">No members found.</p>
              )}
            </div>

            {/* --- NEW: Main Characters Section --- */}
            <div>
                <h3 className="text-lg font-semibold mb-2">Main Characters for Stories</h3>
                <p className="text-sm text-muted-foreground mb-3">Select characters that can be easily chosen when generating new stories.</p>
                {loadingCharacters ? (
                    <p className="text-sm text-muted-foreground">Loading characters...</p>
                ) : errorCharacters ? (
                    <p className="text-sm text-red-500 dark:text-red-400">{errorCharacters}</p>
                ) : characters.length > 0 ? (
                    <ul className="space-y-2">
                        {characters.map(character => (
                            <li key={character.id} className="flex items-center space-x-3 p-2 border rounded-md">
                                <Checkbox
                                    id={`main-char-${character.id}`}
                                    checked={mainCharacterIds.has(character.id)}
                                    onCheckedChange={(checked) => {
                                        handleMainCharacterChange(character.id, !!checked);
                                    }}
                                    disabled={updatingMainChars[character.id]} // Disable while updating this specific character
                                    aria-label={`Set ${character.name} as main character`}
                                />
                                <Avatar className="h-8 w-8">
                                    <AvatarImage src={character.avatar_url ?? undefined} alt={character.name || 'Character Avatar'} />
                                    <AvatarFallback>{getInitials(character.name)}</AvatarFallback>
                                </Avatar>
                                <Label htmlFor={`main-char-${character.id}`} className="flex-grow font-medium cursor-pointer">
                                    {character.name || 'Unnamed Character'}
                                </Label>
                                {updatingMainChars[character.id] && (
                                    <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                                )}
                            </li>
                        ))}
                    </ul>
                ) : (
                    <p className="text-sm text-muted-foreground">No characters found in this family. Create characters on the Characters page.</p>
                )}
            </div>
            {/* ------------------------------------ */}

             {/* TODO: Add leave family button? */} 
          </CardContent>
        </Card>
      ) : (
        // Display Create/Join View
         <div className="grid md:grid-cols-2 gap-6">
          {/* Create Family Card */}
          <Card>
            <CardHeader>
              <CardTitle>Create a New Family</CardTitle>
              <CardDescription>Start a new family group to share stories and characters.</CardDescription>
            </CardHeader>
            <CardFooter>
              <Button onClick={handleCreateFamily} disabled={createLoading || joinLoading || authLoading || loadingFamily}>
                {createLoading ? 'Creating...' : 'Create Family'}
              </Button>
            </CardFooter>
          </Card>

          {/* Join Family Card */}
          <Card>
            <CardHeader>
              <CardTitle>Join an Existing Family</CardTitle>
              <CardDescription>Enter the join code shared by a family member.</CardDescription>
            </CardHeader>
            <form onSubmit={handleJoinFamily}>
              <CardContent className="space-y-2">
                <Label htmlFor="joinCode">Join Code</Label>
                <Input 
                  id="joinCode" 
                  placeholder="ABC-XYZ-123" 
                  value={joinCode}
                  onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
                  disabled={joinLoading || createLoading || authLoading || loadingFamily}
                  required
                />
              </CardContent>
              <CardFooter>
                <Button type="submit" disabled={joinLoading || createLoading || authLoading || loadingFamily}>
                  {joinLoading ? 'Joining...' : 'Join Family'}
                </Button>
              </CardFooter>
            </form>
          </Card>
           {/* Keep actionError display for create/join */}
          {actionError && (createLoading || joinLoading) && <p className="text-sm text-red-500 dark:text-red-400 md:col-span-2 text-center pt-2">{actionError}</p>}
        </div>
      )}
    </div>
  );
} 