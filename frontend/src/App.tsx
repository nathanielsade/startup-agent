import { useEffect, useState } from "react";
import "./styles/tokens.css";
import "./styles/app.css";
import { CvUpload } from "./components/CvUpload";
import { PreferencesForm } from "./components/PreferencesForm";
import { ProfileForm } from "./components/ProfileForm";
import { RunProgress } from "./components/RunProgress";
import { JobList } from "./components/JobList";
import { getCvStatus, getResults, runStream, type RunEvent, type JobMatch } from "./api/client";
import { AuthGate } from "./components/AuthGate";
import { authConfigured, signOut } from "./api/auth";

type Phase = "upload" | "preferences" | "running" | "results";

export default function App() {
  return (
    <AuthGate>
      <AppInner />
    </AuthGate>
  );
}

function AppInner() {
  const [phase, setPhase] = useState<Phase>("upload");
  const [checking, setChecking] = useState(authConfigured);  // cloud: look for a saved CV first
  const [last, setLast] = useState<RunEvent | null>(null);
  const [jobs, setJobs] = useState<JobMatch[]>([]);

  // On login, reuse the user's stored CV instead of asking them to upload again.
  useEffect(() => {
    if (!authConfigured) return;
    getCvStatus()
      .then((s) => { if (s.has_cv) setPhase("preferences"); })
      .catch(() => {})
      .finally(() => setChecking(false));
  }, []);

  function start() {
    setPhase("running"); setLast(null);
    if (authConfigured) {
      // cloud: matches are precomputed by the batch — just fetch + sort, no live run
      setLast({ stage: "matching", candidates: 0 });
      getResults()
        .then((matches) => { setJobs(matches); setPhase("results"); })
        .catch((e) => setLast({ stage: "error", message: e instanceof Error ? e.message : "Failed" }));
      return;
    }
    runStream((ev) => {
      setLast(ev);
      if (ev.stage === "done") { setJobs(ev.matches); setPhase("results"); }
    });
  }

  return (
    <div className="app">
      <header className="header">
        <span className="brand">JobScout</span>
        <span style={{ display: "flex", gap: 14, alignItems: "center" }}>
          {phase === "results" && (
            <span className="header-summary">{jobs.length} matches found</span>
          )}
          {authConfigured && (
            <button className="link-btn" onClick={() => signOut().then(() => window.location.reload())}>
              Sign out
            </button>
          )}
        </span>
      </header>
      <main className="main">
        {checking ? (
          <div className="progress-card">
            <div className="progress-spinner" />
            <div className="progress-label">Loading your account…</div>
          </div>
        ) : (
          <>
            {phase === "upload" && <CvUpload onReady={() => setPhase("preferences")} />}
            {phase === "preferences" && (
              <>
                <div style={{ width: "100%", maxWidth: 560, textAlign: "right" }}>
                  <button className="link-btn" onClick={() => setPhase("upload")}>
                    ↻ Use a different CV
                  </button>
                </div>
                <ProfileForm />
                <PreferencesForm onSaved={start} />
              </>
            )}
            {phase === "running" && <RunProgress last={last} />}
            {phase === "results" && (
              <div className="results-wrap">
                <div className="results-header">
                  <div>
                    <div className="results-title">{jobs.length} matches</div>
                    <div className="results-sub">across 250+ companies, ranked to your CV</div>
                  </div>
                  <button className="results-new-search" onClick={() => window.location.reload()}>
                    ↻ New search
                  </button>
                </div>
                <JobList jobs={jobs} />
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
