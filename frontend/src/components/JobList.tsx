"use client";

import { useEffect, useState } from "react";
import { Job, listJobs } from "@/lib/api";
import JobCard from "./JobCard";

interface JobListProps {
  refreshKey: number;
}

export default function JobList({ refreshKey }: JobListProps) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchJobs = async () => {
      try {
        const data = await listJobs();
        setJobs(data);
      } catch {
        console.error("Failed to fetch jobs");
      } finally {
        setLoading(false);
      }
    };

    fetchJobs();

    // Poll every 5 seconds for active jobs
    const interval = setInterval(fetchJobs, 5000);
    return () => clearInterval(interval);
  }, [refreshKey]);

  if (loading) {
    return (
      <div className="text-center text-zinc-500 py-8">Loading jobs...</div>
    );
  }

  if (jobs.length === 0) {
    return (
      <div className="text-center text-zinc-500 py-8">
        No jobs yet. Upload an image and video to get started.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <h2 className="text-lg font-semibold text-white">Jobs</h2>
      {jobs.map((job) => (
        <JobCard key={job.id} job={job} />
      ))}
    </div>
  );
}
