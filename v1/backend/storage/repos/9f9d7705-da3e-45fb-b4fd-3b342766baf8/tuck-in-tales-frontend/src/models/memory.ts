export interface MemorySuggestion {
  type: 'new_character' | 'update_character_bio' | 'update_character_visual' | 'update_character_avatar';
  character_id?: string;
  character_name?: string;
  data: Record<string, any>;
}

export interface Memory {
  id: string;
  family_id: string;
  text: string | null;
  date: string;
  photo_paths: string[];
  categories: string[];
  summary: string | null;
  linked_character_ids: string[];
  analysis_status: 'PENDING' | 'ANALYZING' | 'ANALYZED' | 'CONFIRMED' | 'FAILED';
  raw_analysis: any;
  suggestions: MemorySuggestion[] | null;
  created_at: string;
}

export interface MemoryConfirmRequest {
  categories: string[];
  summary: string | null;
  linked_character_ids: string[];
}

export interface ApplySuggestionRequest {
  suggestion_index: number;
  approved: boolean;
}

export interface MemorySearchRequest {
  query: string;
  match_threshold?: number;
  match_count?: number;
}

export interface MemorySearchResult extends Memory {
  similarity: number;
}

// --- New character detection types ---

export interface NewCharacterDetection {
  name: string;
  guessed_bio: string;
}

export interface PhotoDetectedPerson {
  name: string;
  confidence: 'high' | 'medium' | 'low';
  is_known: boolean;
  visual_note?: string;
  face_x?: number; // 0-100, percentage from left
  face_y?: number; // 0-100, percentage from top
}

export interface PhotoAnalysisResult {
  photo_index: number;
  description: string;
  detected_people: PhotoDetectedPerson[];
}

export interface NewCharacterFromMemoryRequest {
  name: string;
  bio?: string;
  face_x?: number;
  photo_index?: number;
}

export interface CreateCharactersFromMemoryRequest {
  characters: NewCharacterFromMemoryRequest[];
}

export type MemoryCategory = 'context' | 'new_character' | 'important_event' | 'feeling_emotion' | 'watch_for';

export const CATEGORY_LABELS: Record<MemoryCategory, string> = {
  context: 'Context',
  new_character: 'New Character',
  important_event: 'Important Event',
  feeling_emotion: 'Feeling / Emotion',
  watch_for: 'Watch For',
};

export const CATEGORY_COLORS: Record<MemoryCategory, string> = {
  context: 'bg-blue-100 text-blue-800',
  new_character: 'bg-purple-100 text-purple-800',
  important_event: 'bg-amber-100 text-amber-800',
  feeling_emotion: 'bg-pink-100 text-pink-800',
  watch_for: 'bg-red-100 text-red-800',
};
