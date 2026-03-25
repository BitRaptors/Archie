import axios, { type AxiosInstance } from 'axios';
import type { FamilyDetails } from '../models/family'; 
import type { Character, CharacterSummary, CharacterDetail } from '../models/character';
import type { Story, StoryBasic } from '../models/story'; // Import StoryBasic
import { auth } from '@/firebaseConfig'; // Import Firebase auth instance
import { getFirebaseToken } from '@/utils/firebase'; // Correct the import path
import type { CharacterCreate, CharacterUpdate, CharacterRelationship, AddRelationshipRequest } from '@/models/character';
import type { Family, FamilySettingsUpdate, FamilyDetailResponse, FamilyBasicResponse, FamilyMember } from '@/models/family'; // Ensure Family types are imported
import type { StoryGenerationRequest, StoryPageProgress, CharacterInfo, StoryPage } from '@/models/story'; // Add StoryPage to this import
import type { Prompt, PromptUpdate, PromptTestRequest, PromptTestResponse } from '@/models/prompt';
import type { Memory, MemoryConfirmRequest, ApplySuggestionRequest, MemorySearchRequest, MemorySearchResult, CreateCharactersFromMemoryRequest } from '@/models/memory';

// Get the API base URL from environment variables, defaulting to localhost:8000
const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

const apiClient = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add a request interceptor to include the Firebase ID token
apiClient.interceptors.request.use(async (config) => {
  console.log('API Interceptor: Checking auth state...'); // Log start
  const user = auth.currentUser;
  if (user) {
    console.log('API Interceptor: Firebase user found.', user.uid);
    try {
      const token = await user.getIdToken();
      config.headers.Authorization = `Bearer ${token}`;
      console.log('API Interceptor: Firebase ID token attached.'); // Log success
    } catch (error) {
      console.error('API Interceptor: Error getting Firebase ID token:', error);
      // Handle error, e.g., redirect to login or show a message
      // Depending on the error, you might want to reject the request
      // return Promise.reject(error); 
    }
  } else {
    console.warn('API Interceptor: No Firebase user found. Request will likely be unauthorized.'); // Log warning
  }
  return config;
}, (error) => {
  // Do something with request error
  return Promise.reject(error);
});

// Define API functions here (add more as needed)
export const api = {
  // Example function (replace or remove later)
  // fetchUserData: async () => {
  //   const response = await apiClient.get('/user');
  //   return response.data;
  // },

  // Family functions using actual API calls
  createFamily: async (familyName: string) => { 
    console.log(`API Call: Create family - ${familyName}`);
    // Make actual POST request
    const response = await apiClient.post('/families/', { name: familyName });
    return response.data; // Return data from backend response
  },

  joinFamily: async (joinCode: string) => { 
    console.log(`API Call: Join family - ${joinCode}`);
    // Make actual POST request
    const response = await apiClient.post('/families/join', { join_code: joinCode });
    return response.data; // Return data from backend response
  },

  fetchFamilyDetails: async () => { 
    console.log(`API Call: Fetch family details`);
    // Make actual GET request
    const response = await apiClient.get('/families/mine');
    return response.data; // Return data from backend response (could be null or details)
  },

  // --- NEW: Update Family Settings ---
  updateFamilySettings: async (settings: { name?: string; default_language?: string | null }) => {
    console.log(`API Call: Update family settings:`, settings);
    // Use PUT /families/mine as defined in the backend route
    const response = await apiClient.put('/families/mine', settings); 
    return response.data; // Backend should return the updated family (FamilyBasicResponse)
  },

  // --- NEW: Create Character ---
  createCharacter: async (characterData: CharacterCreate): Promise<Character> => {
    console.log(`API Call: Create character - ${characterData.name}`);
    const response = await apiClient.post<Character>('/characters', characterData);
    return response.data;
  },

  // --- NEW: Fetch Characters ---
  fetchCharacters: async (): Promise<Character[]> => {
    console.log('API Call: Fetch characters');
    const response = await apiClient.get<Character[]>('/characters/');
    return response.data;
  },

  // --- NEW: Fetch Single Character --- 
  fetchCharacter: async (characterId: string): Promise<Character> => {
    console.log(`API Call: Fetch character ${characterId}`);
    const response = await apiClient.get<Character>(`/characters/${characterId}`);
    return response.data;
  },

  // --- NEW: Update Character ---
  updateCharacter: async (characterId: string, characterData: CharacterUpdate): Promise<Character> => {
    console.log(`API Call: Update character ${characterId}`);
    const response = await apiClient.put<Character>(`/characters/${characterId}`, characterData);
    return response.data;
  },

  // --- NEW: Delete Character ---
  deleteCharacter: async (characterId: string): Promise<void> => {
    console.log(`API Call: Delete character ${characterId}`);
    await apiClient.delete(`/characters/${characterId}`);
  },

  // --- NEW: Upload Character Photos ---
  uploadCharacterPhotos: async (characterId: string, files: File[]): Promise<Character> => {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file)); 
    console.log(`API Call: Upload ${files.length} photos for character ${characterId}`);
    const response = await apiClient.post<Character>(`/characters/${characterId}/photos`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  // --- NEW: Generate Character Avatar ---
  generateCharacterAvatar: async (characterId: string): Promise<{ message: string }> => {
    console.log(`API Call: Generate avatar for character ${characterId}`);
    const response = await apiClient.post<{ message: string }>(`/characters/${characterId}/generate_avatar`);
    return response.data;
  },

  // --- Generate Visual Description ---
  generateVisualDescription: async (characterId: string): Promise<{ visual_description: string }> => {
    const response = await apiClient.post<{ visual_description: string }>(`/characters/${characterId}/generate_visual_description`);
    return response.data;
  },

  // --- Character Relationships ---
  addRelationship: async (characterId: string, data: AddRelationshipRequest): Promise<CharacterRelationship> => {
    const response = await apiClient.post<CharacterRelationship>(`/characters/${characterId}/relationships`, data);
    return response.data;
  },

  updateRelationship: async (characterId: string, relationshipId: string, relationshipType: string): Promise<CharacterRelationship> => {
    const response = await apiClient.put<CharacterRelationship>(
      `/characters/${characterId}/relationships/${relationshipId}`,
      { relationship_type: relationshipType }
    );
    return response.data;
  },

  deleteRelationship: async (characterId: string, relationshipId: string): Promise<void> => {
    await apiClient.delete(`/characters/${characterId}/relationships/${relationshipId}`);
  },

  // --- Photo URLs ---
  getPhotoSignedUrls: async (characterId: string): Promise<{ signed_urls: Array<{ path: string; url: string }> }> => {
    const response = await apiClient.get(`/characters/${characterId}/photos/signed-urls`);
    return response.data;
  },

  // --- Photo Person Detection ---
  detectPeopleInPhoto: async (characterId: string): Promise<{ description: string; detected_people: any[]; photo_path: string }> => {
    const response = await apiClient.post(`/characters/${characterId}/detect-people`);
    return response.data;
  },

  cropPhoto: async (characterId: string, faceX: number): Promise<{ message: string; new_photo_path: string }> => {
    const response = await apiClient.post(`/characters/${characterId}/crop-photo`, { face_x: faceX });
    return response.data;
  },

  // --- List Stories ---
  listStories: async (): Promise<StoryBasic[]> => {
    console.log('API Call: List stories');
    const response = await apiClient.get<StoryBasic[]>('/stories/');
    return response.data;
  },

  // --- NEW: Fetch Story ---
  fetchStory: async (storyId: string): Promise<Story> => {
    console.log(`API Call: Fetch story ${storyId}`);
    const response = await apiClient.get<Story>(`/stories/${storyId}`);
    return response.data;
  },

  // --- NEW: Delete Story ---
  deleteStory: async (storyId: string): Promise<void> => {
    console.log(`API Call: Delete story ${storyId}`);
    await apiClient.delete(`/stories/${storyId}`);
  },

  // --- NEW: Generate Story ---
  generateStory: async (request: StoryGenerationRequest): Promise<{ message: string; story_id: string }> => {
    console.log('API Call: Generate story');
    const response = await apiClient.post<{ message: string; story_id: string }>('/stories/generate', request);
    return response.data;
  },

  // --- Retry Failed Story ---
  retryStory: async (storyId: string): Promise<{ message: string; story_id: string }> => {
    console.log(`API Call: Retry story ${storyId}`);
    const response = await apiClient.post<{ message: string; story_id: string }>(`/stories/${storyId}/retry`);
    return response.data;
  },

  // --- NEW: Set Main Character ---
  setMainCharacter: async (characterId: string): Promise<void> => {
    console.log(`API Call: Set main character ${characterId}`);
    await apiClient.post('/families/mine/main_characters', { character_id: characterId });
  },

  // --- NEW: Remove Main Character ---
  removeMainCharacter: async (characterId: string): Promise<void> => {
    console.log(`API Call: Remove main character ${characterId}`);
    await apiClient.delete(`/families/mine/main_characters/${characterId}`);
  },

  // --- Prompt Management ---
  fetchPrompts: async (): Promise<Prompt[]> => {
    console.log('API Call: Fetch prompts');
    const response = await apiClient.get<Prompt[]>('/prompts/');
    return response.data;
  },

  fetchPrompt: async (slug: string): Promise<Prompt> => {
    console.log(`API Call: Fetch prompt ${slug}`);
    const response = await apiClient.get<Prompt>(`/prompts/${slug}`);
    return response.data;
  },

  updatePrompt: async (slug: string, data: PromptUpdate): Promise<Prompt> => {
    console.log(`API Call: Update prompt ${slug}`);
    const response = await apiClient.put<Prompt>(`/prompts/${slug}`, data);
    return response.data;
  },

  testPrompt: async (data: PromptTestRequest): Promise<PromptTestResponse> => {
    console.log('API Call: Test prompt');
    const response = await apiClient.post<PromptTestResponse>('/prompts/test', data);
    return response.data;
  },

  // --- Memory Management ---
  createMemory: async (text: string | null, date: string | null, files: File[]): Promise<Memory> => {
    const formData = new FormData();
    if (text) formData.append('text', text);
    if (date) formData.append('date', date);
    files.forEach(file => formData.append('files', file));
    console.log('API Call: Create memory');
    const response = await apiClient.post<Memory>('/memories/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  fetchMemories: async (): Promise<Memory[]> => {
    console.log('API Call: Fetch memories');
    const response = await apiClient.get<Memory[]>('/memories/');
    return response.data;
  },

  fetchMemory: async (memoryId: string): Promise<Memory> => {
    console.log(`API Call: Fetch memory ${memoryId}`);
    const response = await apiClient.get<Memory>(`/memories/${memoryId}`);
    return response.data;
  },

  analyzeMemory: async (memoryId: string): Promise<{ message: string; memory_id: string }> => {
    console.log(`API Call: Analyze memory ${memoryId}`);
    const response = await apiClient.post<{ message: string; memory_id: string }>(`/memories/${memoryId}/analyze`);
    return response.data;
  },

  confirmMemory: async (memoryId: string, data: MemoryConfirmRequest): Promise<Memory> => {
    console.log(`API Call: Confirm memory ${memoryId}`);
    const response = await apiClient.post<Memory>(`/memories/${memoryId}/confirm`, data);
    return response.data;
  },

  applySuggestion: async (memoryId: string, data: ApplySuggestionRequest): Promise<any> => {
    console.log(`API Call: Apply suggestion for memory ${memoryId}`);
    const response = await apiClient.post(`/memories/${memoryId}/apply-suggestion`, data);
    return response.data;
  },

  uploadMemoryPhotos: async (memoryId: string, files: File[]): Promise<Memory> => {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));
    console.log(`API Call: Upload ${files.length} photos for memory ${memoryId}`);
    const response = await apiClient.post<Memory>(`/memories/${memoryId}/photos`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  searchMemories: async (data: MemorySearchRequest): Promise<MemorySearchResult[]> => {
    console.log('API Call: Search memories');
    const response = await apiClient.post<MemorySearchResult[]>('/memories/search', data);
    return response.data;
  },

  deleteMemory: async (memoryId: string): Promise<void> => {
    console.log(`API Call: Delete memory ${memoryId}`);
    await apiClient.delete(`/memories/${memoryId}`);
  },

  createCharactersFromMemory: async (memoryId: string, data: CreateCharactersFromMemoryRequest): Promise<any> => {
    console.log(`API Call: Create ${data.characters.length} characters from memory ${memoryId}`);
    const response = await apiClient.post(`/memories/${memoryId}/create-characters`, data);
    return response.data;
  },
};

// --- Type Re-Exports (Ensure this line remains exactly as below) --- 
export type { Story, StoryBasic, StoryGenerationRequest, StoryPage, StoryPageProgress, CharacterInfo };
// ----------------------------------------------------------------------

// Export the configured Axios instance if direct access is needed (rarely)
// export default apiClient;