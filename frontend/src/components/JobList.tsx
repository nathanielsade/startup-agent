import type { JobMatch } from "../api/client";
import { JobCard } from "./JobCard";

export function JobList({ jobs }: { jobs: JobMatch[] }) {
  if (!jobs.length) return <p className="muted">No matching jobs.</p>;
  return <div className="job-list">{jobs.map((j, i) => <JobCard key={i} job={j} />)}</div>;
}
