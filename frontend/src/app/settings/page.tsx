"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  GpuInstance,
  getGpuStatus,
  rentGpu,
  startGpu,
  stopGpu,
  destroyGpu,
} from "@/lib/api";

const STATUS_CONFIG: Record<string, { label: string; color: string; dot: string }> = {
  offline: { label: "Offline", color: "text-zinc-400", dot: "bg-zinc-500" },
  renting: { label: "Renting...", color: "text-blue-400", dot: "bg-blue-500 animate-pulse" },
  setup: { label: "Setting up model...", color: "text-yellow-400", dot: "bg-yellow-500 animate-pulse" },
  running: { label: "Running", color: "text-green-400", dot: "bg-green-500" },
  stopped: { label: "Stopped", color: "text-orange-400", dot: "bg-orange-500" },
  error: { label: "Error", color: "text-red-400", dot: "bg-red-500" },
};

export default function SettingsPage() {
  const [gpu, setGpu] = useState<GpuInstance | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = async () => {
    try {
      const data = await getGpuStatus();
      setGpu(data);
      setError(null);
    } catch {
      setError("Failed to fetch GPU status");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleAction = async (action: string, fn: () => Promise<GpuInstance>) => {
    if (action === "destroy" && !confirm("Are you sure? This will delete the instance and all cached model data.")) {
      return;
    }
    setActionLoading(action);
    setError(null);
    try {
      const data = await fn();
      setGpu(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${action}`);
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <main className="flex-1 bg-zinc-950 flex items-center justify-center">
        <p className="text-zinc-500">Loading...</p>
      </main>
    );
  }

  const status = gpu ? STATUS_CONFIG[gpu.status] || STATUS_CONFIG.offline : STATUS_CONFIG.offline;
  const isTransitioning = gpu?.status === "renting" || gpu?.status === "setup";

  return (
    <main className="flex-1 bg-zinc-950">
      <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">
        <div className="flex items-center justify-between">
          <Link href="/" className="text-violet-400 hover:text-violet-300 text-sm">
            &larr; Back
          </Link>
        </div>

        <div>
          <h1 className="text-2xl font-bold text-white">Settings</h1>
          <p className="text-zinc-400 mt-1">Manage your GPU instance</p>
        </div>

        {/* GPU Status Card */}
        <div className="bg-zinc-900 rounded-xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">GPU Instance</h2>
            <div className="flex items-center gap-2">
              <div className={`w-2.5 h-2.5 rounded-full ${status.dot}`} />
              <span className={`text-sm font-medium ${status.color}`}>{status.label}</span>
            </div>
          </div>

          {gpu && gpu.status !== "offline" && (
            <div className="space-y-2 text-sm">
              {gpu.gpu_name && (
                <div className="flex justify-between">
                  <span className="text-zinc-400">GPU</span>
                  <span className="text-white font-medium">{gpu.gpu_name}</span>
                </div>
              )}
              {gpu.instance_id && (
                <div className="flex justify-between">
                  <span className="text-zinc-400">Instance ID</span>
                  <span className="text-zinc-500 font-mono">{gpu.instance_id}</span>
                </div>
              )}
              {gpu.cost_per_hour != null && (
                <div className="flex justify-between">
                  <span className="text-zinc-400">Cost</span>
                  <span className="text-white">${gpu.cost_per_hour.toFixed(3)}/hr</span>
                </div>
              )}
              {gpu.is_setup_done && (
                <div className="flex justify-between">
                  <span className="text-zinc-400">Wan 2.2 Model</span>
                  <span className="text-green-400">Installed</span>
                </div>
              )}
              {gpu.ssh_host && (
                <div className="flex justify-between">
                  <span className="text-zinc-400">SSH</span>
                  <span className="text-zinc-500 font-mono text-xs">{gpu.ssh_host}:{gpu.ssh_port}</span>
                </div>
              )}
            </div>
          )}

          {gpu?.error_message && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3">
              <p className="text-red-400 text-sm">{gpu.error_message}</p>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex gap-3 pt-2">
            {(!gpu || gpu.status === "offline" || gpu.status === "error") && (
              <button
                onClick={() => handleAction("rent", rentGpu)}
                disabled={!!actionLoading}
                className="flex-1 py-2.5 px-4 rounded-lg font-medium text-white bg-violet-600 hover:bg-violet-500 disabled:bg-zinc-700 disabled:text-zinc-500 transition-colors"
              >
                {actionLoading === "rent" ? "Renting..." : "Rent GPU"}
              </button>
            )}

            {gpu?.status === "stopped" && (
              <button
                onClick={() => handleAction("start", startGpu)}
                disabled={!!actionLoading}
                className="flex-1 py-2.5 px-4 rounded-lg font-medium text-white bg-green-600 hover:bg-green-500 disabled:bg-zinc-700 disabled:text-zinc-500 transition-colors"
              >
                {actionLoading === "start" ? "Starting..." : "Start GPU"}
              </button>
            )}

            {gpu?.status === "running" && (
              <button
                onClick={() => handleAction("stop", stopGpu)}
                disabled={!!actionLoading}
                className="flex-1 py-2.5 px-4 rounded-lg font-medium text-white bg-orange-600 hover:bg-orange-500 disabled:bg-zinc-700 disabled:text-zinc-500 transition-colors"
              >
                {actionLoading === "stop" ? "Stopping..." : "Stop GPU"}
              </button>
            )}

            {gpu && gpu.status !== "offline" && !isTransitioning && (
              <button
                onClick={() => handleAction("destroy", destroyGpu)}
                disabled={!!actionLoading}
                className="py-2.5 px-4 rounded-lg font-medium text-red-400 bg-red-500/10 border border-red-500/20 hover:bg-red-500/20 disabled:opacity-50 transition-colors"
              >
                {actionLoading === "destroy" ? "..." : "Destroy"}
              </button>
            )}
          </div>

          {isTransitioning && (
            <p className="text-xs text-zinc-500 text-center">
              This may take a few minutes. Status will update automatically.
            </p>
          )}
        </div>

        {/* Info */}
        <div className="bg-zinc-900/50 rounded-xl p-4 space-y-2 text-sm text-zinc-500">
          <p><strong className="text-zinc-400">Rent</strong> — Creates a new GPU instance and installs Wan 2.2 model (~72GB, first time only)</p>
          <p><strong className="text-zinc-400">Stop</strong> — Pauses compute billing. Storage is kept so model stays installed. Small storage cost only.</p>
          <p><strong className="text-zinc-400">Start</strong> — Resumes a stopped instance. Much faster than renting new.</p>
          <p><strong className="text-zinc-400">Destroy</strong> — Deletes everything. You will need to re-download the model next time.</p>
        </div>

        {error && (
          <p className="text-red-400 text-sm text-center">{error}</p>
        )}
      </div>
    </main>
  );
}
