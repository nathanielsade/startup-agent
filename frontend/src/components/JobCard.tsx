import { useState } from "react";
import { rateJob, type ApplicantProfile, type JobMatch } from "../api/client";

function initials(company: string): string {
  const words = company.trim().split(/\s+/).filter(Boolean);
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

function logoUrl(website: string | null): string | null {
  if (!website) return null;
  try {
    const url = new URL(website.startsWith("http") ? website : `https://${website}`);
    return `https://unavatar.io/${url.hostname.replace(/^www\./, "")}`;
  } catch {
    return null;
  }
}

function companyLinkedin(j: JobMatch): string {
  return (
    j.company_linkedin_url ||
    `https://www.linkedin.com/search/results/companies/?keywords=${encodeURIComponent(j.company)}`
  );
}

function matchTier(score: number): { label: string; cls: string } {
  if (score >= 75) return { label: "Strong", cls: "tier-strong" };
  if (score >= 55) return { label: "Good", cls: "tier-good" };
  return { label: "Weak", cls: "tier-weak" };
}

const TEASER_LEN = 140;

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
  const [open, setOpen] = useState(false);          // apply kit panel
  const [showDesc, setShowDesc] = useState(false);  // description expand
  const [logoOk, setLogoOk] = useState(true);
  const [copied, setCopied] = useState<string | null>(null);

  const meta = [j.company, j.location, j.age_label].filter(Boolean).join(" · ");
  const tier = matchTier(j.score);
  const logo = logoUrl(j.company_website);
  const hasLongDesc = !!j.description && j.description.length > TEASER_LEN;
  const descShown = j.description ? (showDesc ? j.description : j.description.slice(0, TEASER_LEN)) : "";

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
      {logo && logoOk ? (
        <img className="logo" src={logo} alt="" loading="lazy" onError={() => setLogoOk(false)} />
      ) : (
        <div className="company-avatar" aria-hidden="true">{initials(j.company)}</div>
      )}
      <div className="card-body">
        <div className="card-top">
          <span className="card-title">{j.title}</span>
          <span className={`score-pill ${tier.cls}`}>
            {tier.label} · {j.rated ? `✨${j.score}` : j.score}
          </span>
        </div>
        <div className="card-meta">{meta}</div>
        <div className="card-ctx">
          <a className="li-chip" href={companyLinkedin(j)} target="_blank" rel="noreferrer">
            in · LinkedIn ↗
          </a>
        </div>
        {j.description && (
          <div className="job-desc">
            {descShown}{!showDesc && hasLongDesc ? "… " : " "}
            {hasLongDesc && (
              <span className="more" onClick={() => setShowDesc((s) => !s)}>
                {showDesc ? "less ▴" : "more ▾"}
              </span>
            )}
          </div>
        )}
        {j.rated && j.reason && <div className="reason">Why it fits: {j.reason}</div>}
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
