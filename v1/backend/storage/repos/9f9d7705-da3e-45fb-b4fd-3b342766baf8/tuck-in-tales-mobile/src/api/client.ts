import axios, { type AxiosInstance } from 'axios';
import type { FamilyDetails } from '../models/family';
import type { Character, CharacterSummary, CharacterDetail, CharacterCreate, CharacterUpdate } from '../models/character';
import type { Story, StoryBasic, StoryGenerationRequest } from '../models/story';
import { auth } from '../config/firebase';
import { getFirebaseToken } from '../config/firebase';

// Get the API base URL from environment variables
const baseURL = process.env.EXPO_PUBLIC_API_BASE_URL || 'http://localhost:8000/api';

const apiClient = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add a request interceptor to include the Firebase ID token
apiClient.interceptors.request.use(
  async (config) => {
    console.log('API Interceptor: Checking auth state...');
    const user = auth.currentUser;
    if (user) {
      console.log('API Interceptor: Firebase user found.', user.uid);
      try {
        const token = await user.getIdToken();
        config.headers.Authorization = `Bearer ${token}`;
        console.log('API Interceptor: Firebase ID token attached.');
      } catch (error) {
        console.error('API Interceptor: Error getting Firebase ID token:', error);
      }
    } else {
      console.warn('API Interceptor: No Firebase user found. Request will likely be unauthorized.');
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// API functions
export const api = {
  // Family functions
  createFamily: async (familyName: string) => {
    console.log(`API Call: Create family - ${familyName}`);
    const response = await apiClient.post('/families/', { name: familyName });
    return response.data;
  },

  joinFamily: async (joinCode: string) => {
    console.log(`API Call: Join family - ${joinCode}`);
    const response = await apiClient.post('/families/join', { join_code: joinCode });
    return response.data;
  },

  fetchFamilyDetails: async () => {
    console.log(`API Call: Fetch family details`);
    const response = await apiClient.get('/families/mine');
    return response.data;
  },

  updateFamilySettings: async (settings: { name?: string; default_language?: string | null }) => {
    console.log(`API Call: Update family settings:`, settings);
    const response = await apiClient.put('/families/mine', settings);
    return response.data;
  },

  // Character functions
  createCharacter: async (characterData: CharacterCreate): Promise<Character> => {
    console.log(`API Call: Create character - ${characterData.name}`);
    const response = await apiClient.post<Character>('/characters', characterData);
    return response.data;
  },

  fetchCharacters: async (): Promise<Character[]> => {
    console.log('API Call: Fetch characters');
    const response = await apiClient.get<Character[]>('/characters/');
    return response.data;
  },

  fetchCharacter: async (characterId: string): Promise<Character> => {
    console.log(`API Call: Fetch character ${characterId}`);
    const response = await apiClient.get<Character>(`/characters/${characterId}`);
    return response.data;
  },

  updateCharacter: async (characterId: string, characterData: CharacterUpdate): Promise<Character> => {
    console.log(`API Call: Update character ${characterId}`);
    const response = await apiClient.put<Character>(`/characters/${characterId}`, characterData);
    return response.data;
  },

  deleteCharacter: async (characterId: string): Promise<void> => {
    console.log(`API Call: Delete character ${characterId}`);
    await apiClient.delete(`/characters/${characterId}`);
  },

  uploadCharacterPhotos: async (characterId: string, files: any[]): Promise<Character> => {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));
    console.log(`API Call: Upload ${files.length} photos for character ${characterId}`);
    const response = await apiClient.post<Character>(`/characters/${characterId}/photos`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  generateCharacterAvatar: async (characterId: string): Promise<{ message: string }> => {
    console.log(`API Call: Generate avatar for character ${characterId}`);
    const response = await apiClient.post<{ message: string }>(`/characters/${characterId}/generate_avatar`);
    return response.data;
  },

  // Story functions
  listStories: async (): Promise<StoryBasic[]> => {
    console.log('API Call: List stories');
    const response = await apiClient.get<StoryBasic[]>('/stories/');
    return response.data;
  },

  fetchStory: async (storyId: string): Promise<Story> => {
    console.log(`API Call: Fetch story ${storyId}`);
    const response = await apiClient.get<Story>(`/stories/${storyId}`);
    return response.data;
  },

  deleteStory: async (storyId: string): Promise<void> => {
    console.log(`API Call: Delete story ${storyId}`);
    await apiClient.delete(`/stories/${storyId}`);
  },

  generateStory: async (request: StoryGenerationRequest): Promise<{ message: string; story_id: string }> => {
    console.log('API Call: Generate story');
    const response = await apiClient.post<{ message: string; story_id: string }>('/stories/generate', request);
    return response.data;
  },

  // Main character functions
  setMainCharacter: async (characterId: string): Promise<void> => {
    console.log(`API Call: Set main character ${characterId}`);
    await apiClient.post('/families/mine/main_characters', { character_id: characterId });
  },

  removeMainCharacter: async (characterId: string): Promise<void> => {
    console.log(`API Call: Remove main character ${characterId}`);
    await apiClient.delete(`/families/mine/main_characters/${characterId}`);
  },
};
