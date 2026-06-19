import type { JobMatch } from "../api/client";

export function JobCard({ job }: { job: JobMatch }) {
  return (
    <div className="card">
      <div className="card-top">
        <b>{job.title}</b>
        <span className="score">{job.score}</span>
      </div>
      <div className="muted">
        {job.company}{job.location ? ` · ${job.location}` : ""}{job.age_label ? ` · ${job.age_label}` : ""}
      </div>
      <a className="apply" href={job.url} target="_blank" rel="noreferrer">Apply →</a>
    </div>
  );
}
