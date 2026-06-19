import type { RunEvent } from "../api/client";

export function RunProgress({ last }: { last: RunEvent | null }) {
  if (!last) return <p className="muted">Starting…</p>;
  if (last.stage === "fetching") {
    const pct = Math.round((last.done / last.total) * 100);
    return (
      <div className="progress">
        <div className="bar"><div className="fill" style={{ width: `${pct}%` }} /></div>
        <p className="muted">Fetching {last.done}/{last.total} — {last.company} · {last.jobs_fetched} jobs</p>
      </div>
    );
  }
  if (last.stage === "matching") return <p className="muted">Matching {last.candidates} candidates…</p>;
  if (last.stage === "error") return <p className="error">Error: {last.message}</p>;
  return <p className="muted">Done.</p>;
}
