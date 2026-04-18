"use client";

import Link from "next/link";
import { Job } from "@/lib/api";

const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  pending: { label: "Pending", color: "bg-yellow-500/20 text-yellow-400" },
  provisioning: { label: "Provisioning GPU", color: "bg-blue-500/20 text-blue-400" },
  processing: { label: "Processing", color: "bg-purple-500/20 text-purple-400" },
  retrying: { label: "Retrying", color: "bg-orange-500/20 text-orange-400" },
  completed: { label: "Completed", color: "bg-green-500/20 text-green-400" },
  failed: { label: "Failed", color: "bg-red-500/20 text-red-400" },
  cancelled: { label: "Cancelled", color: "bg-zinc-500/20 text-zinc-400" },
};

export default function JobCard({ job }: { job: Job }) {
  const status = STATUS_CONFIG[job.status] || STATUS_CONFIG.pending;
  const createdAt = new Date(job.created_at).toLocaleString();

  return (
    <Link href={`/jobs/${job.id}`}>
      <div className="bg-zinc-900 rounded-lg p-4 hover:bg-zinc-800 transition-colors cursor-pointer">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-mono text-zinc-500">
            {job.id.slice(0, 8)}...
          </span>
          <span className={`text-xs px-2 py-1 rounded-full font-medium ${status.color}`}>
            {status.label}
          </span>
        </div>

        <div className="flex items-center justify-between text-sm">
          <span className="text-zinc-400">{job.resolution}p</span>
          <span className="text-zinc-500">{createdAt}</span>
        </div>

        {job.retry_count > 0 && (
          <p className="text-xs text-orange-400 mt-1">
            Retries: {job.retry_count}/3
          </p>
        )}

        {job.error_message && job.status === "failed" && (
          <p className="text-xs text-red-400 mt-1 truncate">
            {job.error_message}
          </p>
        )}
      </div>
    </Link>
  );
}
