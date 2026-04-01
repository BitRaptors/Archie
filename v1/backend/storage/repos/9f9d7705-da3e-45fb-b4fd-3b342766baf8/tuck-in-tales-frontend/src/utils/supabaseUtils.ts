import { createClient } from '@supabase/supabase-js';

// TODO: Replace with your actual Supabase URL and Anon Key from environment variables
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || '';
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || '';

if (!supabaseUrl || !supabaseAnonKey) {
    console.warn("Supabase URL or Anon Key is missing. Check your .env file.");
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

// --- Public URL Helper ---
const SUPABASE_PROJECT_REF = supabaseUrl ? new URL(supabaseUrl).hostname.split('.')[0] : '';
const AVATAR_BUCKET = 'avatars'; // <-- Changed to avatars bucket

/**
 * Constructs the public URL for an avatar image stored in Supabase storage.
 *
 * @param avatarPath The path to the avatar file within the bucket (e.g., 'family_id/character_id/avatar.png').
 * @returns The full public URL, or null if the path is invalid.
 */
export function getPublicAvatarUrl(avatarPath?: string | null): string | null {
    if (!avatarPath || typeof avatarPath !== 'string' || avatarPath.trim() === '') {
        return null; // Return null if path is missing or invalid
    }
    if (!SUPABASE_PROJECT_REF) {
        console.error("Supabase Project Ref ID is not configured for public URL generation.");
        return null;
    }
    // Construct the URL using the correct bucket
    return `https://${SUPABASE_PROJECT_REF}.supabase.co/storage/v1/object/public/${AVATAR_BUCKET}/${avatarPath}`;
}

const PHOTOS_BUCKET = 'photos';
const MEMORY_PHOTOS_BUCKET = 'memory-photos';

export function getPublicPhotoUrl(photoPath?: string | null): string | null {
    if (!photoPath || typeof photoPath !== 'string' || photoPath.trim() === '') return null;
    if (!SUPABASE_PROJECT_REF) return null;
    return `https://${SUPABASE_PROJECT_REF}.supabase.co/storage/v1/object/public/${PHOTOS_BUCKET}/${photoPath}`;
}

export function getPublicMemoryPhotoUrl(photoPath?: string | null): string | null {
    if (!photoPath || typeof photoPath !== 'string' || photoPath.trim() === '') return null;
    if (!SUPABASE_PROJECT_REF) return null;
    return `https://${SUPABASE_PROJECT_REF}.supabase.co/storage/v1/object/public/${MEMORY_PHOTOS_BUCKET}/${photoPath}`;
} 