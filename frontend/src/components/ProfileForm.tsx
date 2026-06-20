import { useEffect, useState } from "react";
import {
  type ApplicantProfile,
  extractProfile,
  getProfile,
  saveProfile,
} from "../api/client";

const FIELDS: { key: keyof ApplicantProfile; label: string }[] = [
  { key: "first_name", label: "First name" },
  { key: "last_name", label: "Last name" },
  { key: "email", label: "Email" },
  { key: "phone", label: "Phone" },
  { key: "linkedin_url", label: "LinkedIn URL" },
  { key: "github_url", label: "GitHub URL" },
  { key: "location", label: "Location" },
  { key: "current_title", label: "Current title" },
];

export function ProfileForm() {
  const [p, setP] = useState<ApplicantProfile | null>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => { getProfile().then(setP); }, []);

  async function extract() {
    setBusy(true); setErr(null); setSaved(false);
    try {
      const ex = await extractProfile();
      // merge only non-empty extracted values, so a re-extract without a key
      // doesn't blank a name/location you typed in by hand
      setP((cur) => {
        const merged = { ...(cur as ApplicantProfile) };
        (Object.keys(ex) as (keyof ApplicantProfile)[]).forEach((k) => {
          if (ex[k]) merged[k] = ex[k];
        });
        return merged;
      });
    } catch (e) { setErr(e instanceof Error ? e.message : "Extract failed"); }
    finally { setBusy(false); }
  }

  async function save() {
    if (!p) return;
    setErr(null);
    try { await saveProfile(p); setSaved(true); }
    catch (e) { setErr(e instanceof Error ? e.message : "Save failed"); }
  }

  if (!p) return null;

  return (
    <div className="profile-card">
      <h3 className="profile-title">Your application details</h3>
      <button className="autofill-btn" onClick={extract} disabled={busy}>
        {busy ? "Reading your CV…" : "Extract from CV"}
      </button>
      <p className="muted profile-hint">
        Email, phone and links fill automatically. Name &amp; location need an AI key
        (set it in AI scoring) — otherwise type them once.
      </p>
      <div className="profile-fields">
        {FIELDS.map(({ key, label }) => (
          <label key={key} className="profile-field">
            <span className="profile-field-label">{label}</span>
            <input
              value={p[key]}
              onChange={(e) => { setP({ ...p, [key]: e.target.value }); setSaved(false); }}
            />
          </label>
        ))}
      </div>
      <button className="primary" onClick={save}>{saved ? "Saved ✓" : "Save details"}</button>
      {err && <p className="error">{err}</p>}
    </div>
  );
}
