import { useState } from "react";
import { rateJob, type JobMatch } from "../api/client";

function initials(company: string): string {
  const words = company.trim().split(/\s+/).filter(Boolean);
  if (words.length === 1) return words[0].slice(0, 2);
  return (words[0][0] + words[1][0]).toUpperCase();
}

export function JobCard({ job }: { job: JobMatch }) {
  const [j, setJ] = useState(job);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const meta = [j.company, j.location, j.age_label].filter(Boolean).join(" · ");

  async function rate() {
    setBusy(true); setErr(null);
    try {
      const r = await rateJob(j.job_id);
      setJ({ ...j, score: r.score, reason: r.reason, rated: true });
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Rate failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <div className="company-avatar" aria-hidden="true">{initials(j.company)}</div>
      <div className="card-body">
        <div className="card-top">
          <span className="card-title">{j.title}</span>
          <span className={`score${j.rated ? " score-ai" : ""}`}>{j.rated ? `✨ ${j.score}` : j.score}</span>
        </div>
        <div className="card-meta">{meta}</div>
        {j.reason && <div className="reason">{j.reason}</div>}
        <div className="card-actions">
          <a className="apply" href={j.url} target="_blank" rel="noreferrer">Apply →</a>
          {!j.rated && (
            <button className="rate-btn" onClick={rate} disabled={busy}>
              {busy ? "Rating…" : "✨ Rate"}
            </button>
          )}
        </div>
        {err && <div className="error">{err}</div>}
      </div>
    </div>
  );
}
