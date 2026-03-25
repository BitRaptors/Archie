import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.EXPO_PUBLIC_SUPABASE_URL!;
const supabaseAnonKey = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY!;

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

/**
 * Get public URL for avatar from Supabase storage
 * @param avatarPath - Path to avatar in storage (e.g., "avatars/uuid/file.jpg")
 * @returns Public URL or null
 */
export function getPublicAvatarUrl(avatarPath: string | null | undefined): string | null {
  if (!avatarPath) return null;

  const { data } = supabase.storage
    .from('avatars')
    .getPublicUrl(avatarPath);

  return data?.publicUrl || null;
}
