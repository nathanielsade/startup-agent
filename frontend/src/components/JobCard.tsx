import { useState } from "react";
import { rateJob, type ApplicantProfile, type JobMatch } from "../api/client";

function initials(company: string): string {
  const words = company.trim().split(/\s+/).filter(Boolean);
  if (words.length === 1) return words[0].slice(0, 2);
  return (words[0][0] + words[1][0]).toUpperCase();
}

function linkedinCompanyUrl(company: string): string {
  return `https://www.linkedin.com/search/results/companies/?keywords=${encodeURIComponent(company)}`;
}

const PANEL_FIELDS: { key: keyof ApplicantProfile; label: string }[] = [
  { key: "first_name", label: "First name" },
  { key: "last_name", label: "Last name" },
  { key: "email", label: "Email" },
  { key: "phone", label: "Phone" },
  { key: "linkedin_url", label: "LinkedIn" },
  { key: "github_url", label: "GitHub" },
  { key: "location", label: "Location" },
  { key: "current_title", label: "Title" },
];

export function JobCard({ job, profile }: { job: JobMatch; profile: ApplicantProfile | null }) {
  const [j, setJ] = useState(job);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

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

  async function copy(key: string, value: string) {
    try { await navigator.clipboard.writeText(value); setCopied(key); }
    catch { setCopied(`${key}:err`); }
    setTimeout(() => setCopied(null), 1200);
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
          <a className="apply" href={j.url} target="_blank" rel="noreferrer">Open application →</a>
          <button className="rate-btn" onClick={() => setOpen((o) => !o)}>
            {open ? "Hide apply kit" : "Apply"}
          </button>
          {!j.rated && (
            <button className="rate-btn" onClick={rate} disabled={busy}>
              {busy ? "Rating…" : "✨ Rate"}
            </button>
          )}
        </div>
        {open && (
          <div className="apply-panel">
            <a className="li-link" href={linkedinCompanyUrl(j.company)} target="_blank" rel="noreferrer">
              View {j.company} on LinkedIn ↗
            </a>
            {!profile || PANEL_FIELDS.every((f) => !profile[f.key]) ? (
              <p className="muted">No details yet — fill "Your application details" on the preferences screen.</p>
            ) : (
              <div className="apply-fields">
                {PANEL_FIELDS.filter((f) => profile[f.key]).map(({ key, label }) => (
                  <div key={key} className="apply-row">
                    <span className="apply-row-label">{label}</span>
                    <span className="apply-row-val">{profile[key]}</span>
                    <button className="copy-btn" onClick={() => copy(key, profile[key])}>
                      {copied === key ? "Copied ✓" : copied === `${key}:err` ? "⚠" : "Copy"}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        {err && <div className="error">{err}</div>}
      </div>
    </div>
  );
}
