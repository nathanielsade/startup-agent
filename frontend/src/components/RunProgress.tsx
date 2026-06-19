import type { RunEvent } from "../api/client";

export function RunProgress({ last }: { last: RunEvent | null }) {
  if (!last || last.stage === "fetching" && last.done === 0) {
    return (
      <div className="progress-card">
        <div className="progress-spinner" />
        <div className="progress-bar-wrap">
          <div className="progress-bar-indeterminate" />
        </div>
        <div className="progress-label">Starting up…</div>
      </div>
    );
  }

  if (last.stage === "fetching") {
    const pct = Math.round((last.done / last.total) * 100);
    return (
      <div className="progress-card">
        <div className="progress-spinner" />
        <div className="progress-bar-wrap">
          <div className="progress-bar-fill" style={{ width: `${pct}%` }} />
        </div>
        <div className="progress-label">
          <span className="progress-pulsedot" />
          Scanning {last.done}/{last.total} companies — {last.company}
        </div>
        <div className="progress-sub">{last.jobs_fetched} jobs found so far</div>
      </div>
    );
  }

  if (last.stage === "matching") {
    return (
      <div className="progress-card">
        <div className="progress-spinner" />
        <div className="progress-bar-wrap">
          <div className="progress-bar-indeterminate" />
        </div>
        <div className="progress-label">
          <span className="progress-pulsedot" />
          Matching {last.candidates} roles to your CV…
        </div>
      </div>
    );
  }

  if (last.stage === "error") {
    return (
      <div className="progress-card">
        <div className="error">Error: {last.message}</div>
      </div>
    );
  }

  return (
    <div className="progress-card">
      <div className="progress-label">Done.</div>
    </div>
  );
}
