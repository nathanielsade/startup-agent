import { useEffect, useState } from "react";
import { type ApplicantProfile, getProfile, type JobMatch } from "../api/client";
import { JobCard } from "./JobCard";

export function JobList({ jobs }: { jobs: JobMatch[] }) {
  const [profile, setProfile] = useState<ApplicantProfile | null>(null);
  useEffect(() => { getProfile().then(setProfile); }, []);

  if (!jobs.length) return <p className="muted">No matching jobs.</p>;
  return (
    <div className="job-list">
      {jobs.map((j, i) => <JobCard key={i} job={j} profile={profile} />)}
    </div>
  );
}
