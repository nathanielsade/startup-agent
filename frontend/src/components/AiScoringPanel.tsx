import { useEffect, useState } from "react";
import { clearLlmConfig, getLlmConfig, setLlmConfig } from "../api/client";

export function AiScoringPanel() {
  const [configured, setConfigured] = useState(false);
  const [provider, setProvider] = useState("anthropic");
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getLlmConfig().then((c) => { setConfigured(c.configured); if (c.provider) setProvider(c.provider); });
  }, []);

  async function save() {
    setBusy(true); setError(null);
    try {
      await setLlmConfig(provider, key);
      setConfigured(true); setKey("");
    } catch (e) { setError(e instanceof Error ? e.message : "Save failed"); }
    finally { setBusy(false); }
  }

  async function remove() {
    setBusy(true); setError(null);
    try { await clearLlmConfig(); setConfigured(false); }
    catch (e) { setError(e instanceof Error ? e.message : "Remove failed"); }
    finally { setBusy(false); }
  }

  return (
    <div className="ai-panel">
      <label className="prefs-label">✨ AI scoring (optional)</label>
      {configured ? (
        <div className="ai-on">
          <span className="ai-badge">AI scoring: on · {provider}</span>
          <button className="link-btn" onClick={remove} disabled={busy}>Remove</button>
        </div>
      ) : (
        <>
          <p className="muted ai-hint">Add your own API key to unlock AI fit-scores &amp; reasons — optional; matching works without it. Held in memory only, never saved to disk.</p>
          <div className="ai-row">
            <select value={provider} onChange={(e) => setProvider(e.target.value)}>
              <option value="anthropic">Anthropic (Claude)</option>
              <option value="openai">OpenAI (GPT)</option>
            </select>
            <input type="password" placeholder="API key" value={key}
                   onChange={(e) => setKey(e.target.value)} />
            <button className="primary-sm" onClick={save} disabled={busy || !key}>Save</button>
          </div>
        </>
      )}
      {error && <p className="error">{error}</p>}
    </div>
  );
}
