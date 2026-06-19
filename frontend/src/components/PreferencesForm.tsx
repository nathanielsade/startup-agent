import { useEffect, useState } from "react";
import { getPreferences, savePreferences, type Preferences } from "../api/client";

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

  useEffect(() => { getPreferences().then(setP); }, []);
  if (!p) return <p className="muted">Loading preferences…</p>;

  const toggle = (key: "districts" | "roles" | "seniority", v: string) =>
    setP({ ...p, [key]: p[key].includes(v) ? p[key].filter((x) => x !== v) : [...p[key], v] });

  async function save() { await savePreferences(p!); onSaved(); }

  return (
    <div className="card prefs">
      <h3>Your preferences</h3>

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

      <button className="primary" onClick={save}>Save & Find jobs →</button>
    </div>
  );
}
