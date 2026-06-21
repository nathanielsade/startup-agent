import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const URL = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const ANON = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

// Deployed frontend (Vercel) and API (Render) live on different origins, so prefix
// API calls with VITE_API_BASE. Empty in dev → relative paths hit the Vite proxy.
export const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) || "";

// When Supabase isn't configured (local dev), the app runs in "dev mode": no login
// screen, no JWT — the backend's dev-user fallback handles it.
export const authConfigured = Boolean(URL && ANON);

export const supabase: SupabaseClient | null = authConfigured
  ? createClient(URL!, ANON!)
  : null;

export async function getToken(): Promise<string | null> {
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

/** fetch() with the API base prefixed and the Supabase bearer token attached. */
export async function authFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const token = await getToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return fetch(API_BASE + input, { ...init, headers });
}

export async function signIn(email: string, password: string): Promise<void> {
  if (!supabase) return;
  const { error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) throw new Error(error.message);
}

export async function signUp(email: string, password: string): Promise<void> {
  if (!supabase) return;
  const { error } = await supabase.auth.signUp({ email, password });
  if (error) throw new Error(error.message);
}

export async function signOut(): Promise<void> {
  if (supabase) await supabase.auth.signOut();
}

export function onAuthChange(cb: (signedIn: boolean) => void): () => void {
  if (!supabase) return () => {};
  const { data } = supabase.auth.onAuthStateChange((_e, session) => cb(Boolean(session)));
  return () => data.subscription.unsubscribe();
}
