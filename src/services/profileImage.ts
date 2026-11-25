import { File } from 'expo-file-system';
import { supabase } from '../lib/supabase';

const bucket = 'profile-images';
const allowedTypes = new Set(['image/jpeg', 'image/png', 'image/webp']);

export async function signedProfileImage(path?: string | null) {
  if (!path) return null;
  const { data, error } = await supabase.storage.from(bucket).createSignedUrl(path, 60 * 60);
  if (error || !data.signedUrl) throw new Error('ပရိုဖိုင်ပုံကို ဖွင့်မရပါ။');
  return data.signedUrl;
}

export async function uploadProfileImage(owner: string, uri: string, mimeType?: string | null) {
  const contentType = mimeType && allowedTypes.has(mimeType) ? mimeType : 'image/jpeg';
  const extension = contentType === 'image/png' ? 'png' : contentType === 'image/webp' ? 'webp' : 'jpg';
  const path = `${owner}/${Date.now()}-${owner}.${extension}`;
  const body = await new File(uri).arrayBuffer();
  if (!body.byteLength || body.byteLength > 5 * 1024 * 1024) throw new Error('ပရိုဖိုင်ပုံသည် 5 MB အောက် ဖြစ်ရပါမည်။');
  const { error } = await supabase.storage.from(bucket).upload(path, body, { contentType, upsert: false });
  if (error) throw new Error('ပရိုဖိုင်ပုံကို တင်မရပါ။');
  return path;
}

export async function removeProfileImage(path: string) {
  const { error } = await supabase.storage.from(bucket).remove([path]);
  if (error) throw new Error('ပရိုဖိုင်ပုံအဟောင်းကို ဖယ်ရှားမရပါ။');
}
