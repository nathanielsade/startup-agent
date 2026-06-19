import { useState } from "react";
import "./styles/tokens.css";
import "./styles/app.css";
import { CvUpload } from "./components/CvUpload";
import { RunProgress } from "./components/RunProgress";
import { JobList } from "./components/JobList";
import { runStream, type RunEvent, type JobMatch } from "./api/client";

type Phase = "upload" | "running" | "results";

export default function App() {
  const [phase, setPhase] = useState<Phase>("upload");
  const [last, setLast] = useState<RunEvent | null>(null);
  const [jobs, setJobs] = useState<JobMatch[]>([]);

  function start() {
    setPhase("running"); setLast(null);
    runStream((ev) => {
      setLast(ev);
      if (ev.stage === "done") { setJobs(ev.matches); setPhase("results"); }
    });
  }

  const summary = phase === "results" ? `${jobs.length} matches` : "";

  return (
    <div className="app">
      <header className="header">
        <span className="brand">JobScout</span>
        <span className="muted">{summary}</span>
      </header>
      <main className="main">
        {phase === "upload" && <CvUpload onReady={start} />}
        {phase === "running" && <RunProgress last={last} />}
        {phase === "results" && <JobList jobs={jobs} />}
      </main>
    </div>
  );
}
