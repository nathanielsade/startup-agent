import { authFetch } from "./auth";

export interface JobMatch {
  job_id: string;
  title: string;
  company: string;
  location: string | null;
  score: number;
  url: string;
  posted_at: string | null;
  age_label: string;
  reason: string | null;
  rated: boolean;
  company_linkedin_url: string | null;
  company_website: string | null;
  description: string | null;
  status: string;
}

export async function setJobStatus(jobId: string, status: string,
                                   snapshot?: Record<string, unknown>): Promise<void> {
  const resp = await authFetch(`/api/jobs/${jobId}/status`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, snapshot }),
  });
  if (!resp.ok) throw new Error(`Update status failed (${resp.status})`);
}

// Cloud mode: fetch the per-user matches precomputed by the batch (no live fetch/embed).
export async function getResults(): Promise<JobMatch[]> {
  const resp = await authFetch("/api/results");
  if (!resp.ok) throw new Error(`Load results failed (${resp.status})`);
  const data = (await resp.json()) as { matches: JobMatch[] };
  return data.matches;
}

export type RunEvent =
  | { stage: "fetching"; done: number; total: number; company: string; jobs_fetched: number; jobs_new: number }
  | { stage: "matching"; candidates: number }
  | { stage: "rating"; count: number }
  | { stage: "done"; matched: number; matches: JobMatch[] }
  | { stage: "error"; message: string };

export interface Preferences {
  districts: string[];
  include_remote: boolean;
  max_years: number | null;
  posted_within_days: number | null;
  title_include: string[];
  exclude: string[];
  roles: string[];
  seniority: string[];
  locations: string[];
  must_have: string[];
}

export async function getPreferences(): Promise<Preferences> {
  const resp = await authFetch("/api/preferences");
  if (!resp.ok) throw new Error(`Load prefs failed (${resp.status})`);
  return resp.json();
}

export async function savePreferences(prefs: Preferences): Promise<void> {
  const resp = await authFetch("/api/preferences", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(prefs),
  });
  if (!resp.ok) throw new Error(`Save prefs failed (${resp.status})`);
}

export async function uploadCv(file: File): Promise<{ status: string; chars: number }> {
  const body = new FormData();
  body.append("file", file);
  const resp = await authFetch("/api/cv", { method: "POST", body });
  if (!resp.ok) throw new Error(`Upload failed (${resp.status})`);
  return resp.json();
}

export async function rateJob(jobId: string): Promise<{ score: number; reason: string }> {
  const resp = await authFetch("/api/rate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_id: jobId }),
  });
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}));
    throw new Error((detail as { detail?: string }).detail || `Rate failed (${resp.status})`);
  }
  return resp.json();
}

export async function suggestPreferences(): Promise<Preferences> {
  const resp = await authFetch("/api/preferences/suggest", { method: "POST" });
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}));
    throw new Error((detail as { detail?: string }).detail || `Auto-fill failed (${resp.status})`);
  }
  return resp.json();
}

export interface LlmConfig {
  configured: boolean;
  provider: string | null;
}

export async function getLlmConfig(): Promise<LlmConfig> {
  const resp = await authFetch("/api/llm-config");
  if (!resp.ok) throw new Error(`Load LLM config failed (${resp.status})`);
  return resp.json();
}

export async function setLlmConfig(provider: string, apiKey: string, model?: string): Promise<LlmConfig> {
  const resp = await authFetch("/api/llm-config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider, api_key: apiKey, model }),
  });
  if (!resp.ok) throw new Error(`Save key failed (${resp.status})`);
  return resp.json();
}

export async function clearLlmConfig(): Promise<void> {
  const resp = await authFetch("/api/llm-config", { method: "DELETE" });
  if (!resp.ok) throw new Error(`Remove key failed (${resp.status})`);
}

export interface ApplicantProfile {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  linkedin_url: string;
  github_url: string;
  location: string;
  current_title: string;
}

export async function getProfile(): Promise<ApplicantProfile> {
  const resp = await authFetch("/api/profile");
  if (!resp.ok) throw new Error(`Load profile failed (${resp.status})`);
  return resp.json();
}

export async function saveProfile(profile: ApplicantProfile): Promise<void> {
  const resp = await authFetch("/api/profile", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(profile),
  });
  if (!resp.ok) throw new Error(`Save profile failed (${resp.status})`);
}

export async function extractProfile(): Promise<ApplicantProfile> {
  const resp = await authFetch("/api/profile/extract", { method: "POST" });
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}));
    throw new Error((detail as { detail?: string }).detail || `Extract failed (${resp.status})`);
  }
  return resp.json();
}

// SSE via EventSource (GET). onEvent fires per progress event; resolves on done/error.
export function runStream(onEvent: (e: RunEvent) => void): EventSource {
  const es = new EventSource("/api/run");
  es.onmessage = (msg) => {
    const ev = JSON.parse(msg.data) as RunEvent;
    onEvent(ev);
    if (ev.stage === "done" || ev.stage === "error") es.close();
  };
  es.onerror = () => es.close();
  return es;
}
