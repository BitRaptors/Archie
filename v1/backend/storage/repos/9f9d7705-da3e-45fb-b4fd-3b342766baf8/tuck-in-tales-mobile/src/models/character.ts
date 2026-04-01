// Base Character type (matching backend)
export interface Character {
  id: string; // UUID
  name: string;
  bio?: string | null;
  birth_date?: string | null; // Add optional birth_date (YYYY-MM-DD string)
  avatar_url?: string | null;
  created_at: string; // ISO date string
  family_id: string; // UUID
  // Add any other fields from your backend model
}

// Type for displaying in lists (subset of Character)
export interface CharacterSummary {
  id: string;
  name: string;
  avatar_url?: string | null;
}

// Type for detailed view (could be same as Character or have extra fields)
export interface CharacterDetail extends Character {
  // Add any additional fields specific to detail view if needed
  // e.g., associated_memories?: Memory[];
}

// Type for creating a new character (input to API)
export interface CharacterCreate {
  name: string;
  bio?: string | null;
  birth_date?: string | null; // Add optional birth_date
  // Add other required fields for creation
}

// Type for updating an existing character (input to API, fields are optional)
export interface CharacterUpdate {
  name?: string;
  bio?: string | null;
  birth_date?: string | null; // Add optional birth_date
  // Add other updatable fields
} 