import type { JobMatch } from "../api/client";

function initials(company: string): string {
  const words = company.trim().split(/\s+/).filter(Boolean);
  if (words.length === 1) return words[0].slice(0, 2);
  return (words[0][0] + words[1][0]).toUpperCase();
}

export function JobCard({ job }: { job: JobMatch }) {
  const meta = [job.company, job.location, job.age_label].filter(Boolean).join(" · ");

  return (
    <div className="card">
      <div className="company-avatar" aria-hidden="true">{initials(job.company)}</div>
      <div className="card-body">
        <div className="card-top">
          <span className="card-title">{job.title}</span>
          <span className="score">{job.score}</span>
        </div>
        <div className="card-meta">{meta}</div>
        <a className="apply" href={job.url} target="_blank" rel="noreferrer">Apply →</a>
      </div>
    </div>
  );
}
