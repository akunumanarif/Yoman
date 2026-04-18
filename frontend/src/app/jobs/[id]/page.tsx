"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Job, getJob, deleteJob } from "@/lib/api";
import VideoPlayer from "@/components/VideoPlayer";

const STEPS = [
  { key: "pending", label: "Queued" },
  { key: "provisioning", label: "GPU Setup" },
  { key: "processing", label: "Generating" },
  { key: "completed", label: "Done" },
];

function getStepIndex(status: string): number {
  if (status === "retrying") return 1;
  if (status === "failed" || status === "cancelled") return -1;
  return STEPS.findIndex((s) => s.key === status);
}

export default function JobDetail() {
  const params = useParams();
  const router = useRouter();
  const jobId = params.id as string;
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchJob = async () => {
      try {
        const data = await getJob(jobId);
        setJob(data);
      } catch {
        console.error("Failed to fetch job");
      } finally {
        setLoading(false);
      }
    };

    fetchJob();

    // Poll if job is still active
    const interval = setInterval(async () => {
      try {
        const data = await getJob(jobId);
        setJob(data);
        if (["completed", "failed", "cancelled"].includes(data.status)) {
          clearInterval(interval);
        }
      } catch {
        clearInterval(interval);
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [jobId]);

  const handleDelete = async () => {
    if (!confirm("Are you sure you want to delete this job?")) return;
    try {
      await deleteJob(jobId);
      router.push("/");
    } catch {
      console.error("Failed to delete job");
    }
  };

  if (loading) {
    return (
      <main className="flex-1 bg-zinc-950 flex items-center justify-center">
        <p className="text-zinc-500">Loading...</p>
      </main>
    );
  }

  if (!job) {
    return (
      <main className="flex-1 bg-zinc-950 flex items-center justify-center">
        <p className="text-zinc-500">Job not found</p>
      </main>
    );
  }

  const stepIndex = getStepIndex(job.status);
  const isActive = ["pending", "provisioning", "processing", "retrying"].includes(job.status);

  return (
    <main className="flex-1 bg-zinc-950">
      <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <Link href="/" className="text-violet-400 hover:text-violet-300 text-sm">
            &larr; Back
          </Link>
          <button
            onClick={handleDelete}
            className="text-red-400 hover:text-red-300 text-sm"
          >
            Delete
          </button>
        </div>

        <div>
          <h1 className="text-2xl font-bold text-white">Job Detail</h1>
          <p className="text-zinc-500 font-mono text-sm mt-1">{job.id}</p>
        </div>

        {/* Progress Steps */}
        {job.status !== "failed" && job.status !== "cancelled" && (
          <div className="flex items-center gap-2">
            {STEPS.map((step, i) => (
              <div key={step.key} className="flex items-center gap-2 flex-1">
                <div
                  className={`h-2 flex-1 rounded-full transition-colors ${
                    i <= stepIndex
                      ? "bg-violet-500"
                      : "bg-zinc-800"
                  } ${i === stepIndex && isActive ? "animate-pulse" : ""}`}
                />
                {i < STEPS.length - 1 && <div className="w-1" />}
              </div>
            ))}
          </div>
        )}
        {job.status !== "failed" && job.status !== "cancelled" && (
          <div className="flex justify-between text-xs text-zinc-500">
            {STEPS.map((step) => (
              <span key={step.key}>{step.label}</span>
            ))}
          </div>
        )}

        {/* Status Info */}
        <div className="bg-zinc-900 rounded-xl p-4 space-y-3">
          <div className="flex justify-between text-sm">
            <span className="text-zinc-400">Status</span>
            <span className="text-white font-medium capitalize">{job.status}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-zinc-400">Resolution</span>
            <span className="text-white">{job.resolution}p</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-zinc-400">Created</span>
            <span className="text-white">{new Date(job.created_at).toLocaleString()}</span>
          </div>
          {job.retry_count > 0 && (
            <div className="flex justify-between text-sm">
              <span className="text-zinc-400">Retries</span>
              <span className="text-orange-400">{job.retry_count}/3</span>
            </div>
          )}
          {job.instance_id && (
            <div className="flex justify-between text-sm">
              <span className="text-zinc-400">GPU Instance</span>
              <span className="text-zinc-500 font-mono text-xs">{job.instance_id}</span>
            </div>
          )}
        </div>

        {/* Error Message */}
        {job.error_message && (
          <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4">
            <p className="text-red-400 text-sm">{job.error_message}</p>
          </div>
        )}

        {/* Result Video */}
        {job.status === "completed" && (
          <div className="space-y-3">
            <h2 className="text-lg font-semibold text-white">Result</h2>
            <VideoPlayer jobId={job.id} />
          </div>
        )}
      </div>
    </main>
  );
}
