import { useEffect, useState, type ReactNode } from "react";

import { authConfigured, getToken, onAuthChange, signIn, signUp } from "../api/auth";

export function AuthGate({ children }: { children: ReactNode }) {
  // dev mode (Supabase not configured): no gate, app renders directly
  const [signedIn, setSignedIn] = useState(!authConfigured);
  const [checked, setChecked] = useState(!authConfigured);
  const [mode, setMode] = useState<"in" | "up">("in");
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!authConfigured) return;
    getToken().then((t) => { setSignedIn(Boolean(t)); setChecked(true); });
    return onAuthChange(setSignedIn);
  }, []);

  if (!checked) return null;
  if (signedIn) return <>{children}</>;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      if (mode === "in") await signIn(email, pw);
      else { await signUp(email, pw); setErr("Check your email to confirm, then sign in."); }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Authentication failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app">
      <main className="main">
        <form className="auth-card" onSubmit={submit}>
          <h1 className="brand" style={{ fontSize: 24 }}>JobScout</h1>
          <p className="muted">{mode === "in" ? "Sign in to your account" : "Create an account"}</p>
          <input className="prefs-num" style={{ width: "100%" }} type="email" placeholder="Email"
                 value={email} onChange={(e) => setEmail(e.target.value)} required />
          <input className="prefs-num" style={{ width: "100%" }} type="password" placeholder="Password"
                 value={pw} onChange={(e) => setPw(e.target.value)} required />
          <button className="primary" disabled={busy}>
            {busy ? "…" : mode === "in" ? "Sign in" : "Sign up"}
          </button>
          <button type="button" className="link-btn" onClick={() => setMode(mode === "in" ? "up" : "in")}>
            {mode === "in" ? "Need an account? Sign up" : "Have an account? Sign in"}
          </button>
          {err && <p className="error">{err}</p>}
        </form>
      </main>
    </div>
  );
}
