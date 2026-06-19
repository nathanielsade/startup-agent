export interface JobMatch {
  title: string;
  company: string;
  location: string | null;
  score: number;
  url: string;
  posted_at: string | null;
  age_label: string;
}

export type RunEvent =
  | { stage: "fetching"; done: number; total: number; company: string; jobs_fetched: number; jobs_new: number }
  | { stage: "matching"; candidates: number }
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
  const resp = await fetch("/api/preferences");
  if (!resp.ok) throw new Error(`Load prefs failed (${resp.status})`);
  return resp.json();
}

export async function savePreferences(prefs: Preferences): Promise<void> {
  const resp = await fetch("/api/preferences", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(prefs),
  });
  if (!resp.ok) throw new Error(`Save prefs failed (${resp.status})`);
}

export async function uploadCv(file: File): Promise<{ status: string; chars: number }> {
  const body = new FormData();
  body.append("file", file);
  const resp = await fetch("/api/cv", { method: "POST", body });
  if (!resp.ok) throw new Error(`Upload failed (${resp.status})`);
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
