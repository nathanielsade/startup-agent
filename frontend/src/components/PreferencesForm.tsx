import { useEffect, useState } from "react";
import { getLlmConfig, getPreferences, savePreferences, suggestPreferences, type Preferences } from "../api/client";
import { AiScoringPanel } from "./AiScoringPanel";

const DISTRICTS = ["center", "north", "south", "jerusalem"];
const ROLES = ["backend", "frontend", "full-stack", "ai", "data", "devops", "security"];
const SENIORITY = ["junior", "mid", "senior"];

function Chips({ options, selected, onToggle }:
  { options: string[]; selected: string[]; onToggle: (v: string) => void }) {
  return (
    <div className="chips">
      {options.map((o) => (
        <button key={o} type="button"
          className={`chip ${selected.includes(o) ? "chip-on" : ""}`}
          onClick={() => onToggle(o)}>{o}</button>
      ))}
    </div>
  );
}

export function PreferencesForm({ onSaved }: { onSaved: () => void }) {
  const [p, setP] = useState<Preferences | null>(null);
  const [aiOn, setAiOn] = useState(false);
  const [autofilling, setAutofilling] = useState(false);
  const [autofillErr, setAutofillErr] = useState<string | null>(null);

  useEffect(() => { getPreferences().then(setP); }, []);
  useEffect(() => { getLlmConfig().then((c) => setAiOn(c.configured)); }, []);

  async function autofill() {
    setAutofilling(true); setAutofillErr(null);
    try {
      const s = await suggestPreferences();
      setP((cur) => cur && ({
        ...cur,
        max_years: s.max_years, roles: s.roles,
        seniority: s.seniority, title_include: s.title_include,
      }));
    } catch (e) { setAutofillErr(e instanceof Error ? e.message : "Auto-fill failed"); }
    finally { setAutofilling(false); }
  }

  if (!p) return <p className="muted">Loading preferences…</p>;

  const toggle = (key: "districts" | "roles" | "seniority", v: string) =>
    setP({ ...p, [key]: p[key].includes(v) ? p[key].filter((x) => x !== v) : [...p[key], v] });

  async function save() { await savePreferences(p!); onSaved(); }

  return (
    <div className="card prefs">
      <h3>Your preferences</h3>

      <button className="autofill-btn" onClick={autofill}
              disabled={!aiOn || autofilling}
              title={aiOn ? "" : "Add a key in AI scoring below to enable"}>
        {autofilling ? "Reading your CV…" : "✨ Auto-fill from CV"}
      </button>
      {!aiOn && <p className="muted autofill-hint">Enable AI scoring below to auto-fill from your CV.</p>}
      {autofillErr && <p className="error">{autofillErr}</p>}

      <label className="prefs-label">Districts <span className="hard">· hard</span></label>
      <Chips options={DISTRICTS} selected={p.districts} onToggle={(v) => toggle("districts", v)} />
      <label className="prefs-check">
        <input type="checkbox" checked={p.include_remote}
          onChange={(e) => setP({ ...p, include_remote: e.target.checked })} /> Include remote
      </label>

      <label className="prefs-label">Max experience (years) <span className="hard">· hard</span></label>
      <input className="prefs-num" type="number" min={0} max={20}
        value={p.max_years ?? ""} placeholder="no limit"
        onChange={(e) => setP({ ...p, max_years: e.target.value ? Number(e.target.value) : null })} />

      <label className="prefs-label">Posted within (days) <span className="hard">· hard</span></label>
      <input className="prefs-num" type="number" min={1} max={365}
        value={p.posted_within_days ?? ""} placeholder="any time"
        onChange={(e) => setP({ ...p, posted_within_days: e.target.value ? Number(e.target.value) : null })} />

      <label className="prefs-label">Role / domain <span className="soft">★ soft</span></label>
      <Chips options={ROLES} selected={p.roles} onToggle={(v) => toggle("roles", v)} />

      <label className="prefs-label">Seniority <span className="soft">★ soft</span></label>
      <Chips options={SENIORITY} selected={p.seniority} onToggle={(v) => toggle("seniority", v)} />

      <AiScoringPanel />
      <button className="primary" onClick={save}>Save & Find jobs →</button>
    </div>
  );
}
