import type { CharacterSummary } from './character'; // Assuming a summary type exists

// Basic interface for family details fetched from the backend
export interface FamilyDetails {
  id: string; // UUID
  name: string;
  join_code?: string; // Optional, may only be present sometimes
  created_at: string; // ISO date string
  default_language?: string | null; // Add default language
  // Add other fields as needed from your backend model
}

// Represents a member within a family
export interface FamilyMember {
  id: string; // Assuming user ID
  name: string; // Assuming user name
  // Add role or other relevant member details if needed
}

// Basic response structure, often for lists
export interface FamilyBasicResponse {
  id: string;
  name: string;
}

// Detailed response structure, potentially including members, main characters, etc.
export interface FamilyDetailResponse extends FamilyBasicResponse {
  join_code?: string; 
  created_at: string; // ISO date string
  default_language?: string | null;
  members?: FamilyMember[];
  main_characters?: CharacterSummary[]; // Use CharacterSummary or Character
  // Add other detailed fields like settings, etc.
}

// Type for updating family settings
export interface FamilySettingsUpdate {
  name?: string;
  default_language?: string | null;
  // Add any other updatable settings fields
}

// Main Family type - can alias to the detailed response for now
export type Family = FamilyDetailResponse; 