// Frontend type definitions mirroring backend Pydantic models

// Corresponds to StoryPageProgress TypedDict in story.py
export interface DebugPromptEntry {
  system: string;
  user: string;
  model: string;
  temperature: number;
  // Consistency check extra fields
  response?: string;
  passed?: boolean;
  attempt?: number;
}

export interface StoryPageProgress {
  page: number;
  description?: string | null;
  text?: string | null;
  image_prompt?: string | null;
  image_url?: string | null;
  characters_on_page?: string[] | null; // List of character names involved
  debug_prompts?: Record<string, DebugPromptEntry> | null;
  avatar_urls?: Record<string, string> | null;
}

// --- Story Basic Type (for lists) ---
export interface StoryBasic {
  id: string;
  title: string;
  status: string;
  language: string;
  created_at: string;
}

// --- Full Story Type ---
export interface Story {
  id: string; // UUID is a string in TS/JSON
  family_id: string; // UUID
  title: string; 
  input_prompt?: string | null;
  pages: StoryPageProgress[]; // Use the interface defined above
  language: string;
  target_age?: number | null;
  character_ids?: string[] | null; // List of UUID strings
  debug_prompts?: Record<string, DebugPromptEntry> | null; // Story-level debug (e.g. outline)
  status: string; // e.g., 'INITIALIZING', 'OUTLINING', etc.
  created_at: string; // ISO date string
  // Add any other fields from your Story model
}

// Represents info about a character involved in a story
export interface CharacterInfo {
  id: string;
  name: string;
  avatar_url?: string | null;
}

// Represents a single page within a story
export interface StoryPage {
  page_number: number;
  text: string;
  image_prompt?: string | null;
  image_url?: string | null;
  characters_on_page?: CharacterInfo[]; // Use CharacterInfo
}

// Structure for requesting a new story generation
export interface StoryGenerationRequest {
  topic: string;
  character_ids: string[];
  age_group?: string | null; // e.g., '3-5', '6-8'
  moral?: string | null;
  language?: string | null;
  num_pages?: number | null; // Number of pages to generate (1-20). If omitted, LLM decides (3-5).
}

// Add detailed Story type if different from StoryBasic
// Use StoryPageProgress as indicated by linter
export interface Story extends StoryBasic {
  pages: StoryPageProgress[]; // Use StoryPageProgress here
  characters: CharacterInfo[];
  // Add other fields from full Story model like age_group, moral, etc.
} 