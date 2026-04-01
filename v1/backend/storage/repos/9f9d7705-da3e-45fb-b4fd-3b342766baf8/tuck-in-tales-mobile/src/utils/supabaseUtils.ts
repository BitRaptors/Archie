import { supabase } from '../config/supabase';

/**
 * Convert a Supabase Storage path to a public URL
 * @param bucket - The storage bucket name (e.g., 'avatars')
 * @param path - The file path in the bucket
 * @returns Full public URL or null if path is empty
 */
export function getPublicUrl(bucket: string, path: string | null | undefined): string | null {
  if (!path) return null;

  const { data } = supabase.storage.from(bucket).getPublicUrl(path);
  return data.publicUrl;
}

/**
 * Get avatar public URL from storage path
 * @param avatarPath - The avatar file path in storage
 * @returns Full public URL or null
 */
export function getAvatarUrl(avatarPath: string | null | undefined): string | null {
  return getPublicUrl('avatars', avatarPath);
}

/**
 * Get photo public URL from storage path
 * @param photoPath - The photo file path in storage
 * @returns Full public URL or null
 */
export function getPhotoUrl(photoPath: string | null | undefined): string | null {
  return getPublicUrl('photos', photoPath);
}
