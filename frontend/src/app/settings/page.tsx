"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  GpuInstance,
  GpuOffer,
  VastInstance,
  getGpuStatus,
  listGpuOffers,
  listMyInstances,
  rentGpuWithOffer,
  connectGpu,
  startGpu,
  stopGpu,
  destroyGpu,
  retrySetup,
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
  const [offers, setOffers] = useState<GpuOffer[]>([]);
  const [showOffers, setShowOffers] = useState(false);
  const [showConnect, setShowConnect] = useState(false);
  const [myInstances, setMyInstances] = useState<VastInstance[]>([]);
  const [connectLoading, setConnectLoading] = useState(false);
  const [offersLoading, setOffersLoading] = useState(false);
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

  const handleFetchOffers = async () => {
    setShowOffers(true);
    setOffersLoading(true);
    setError(null);
    try {
      const data = await listGpuOffers();
      setOffers(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch offers");
    } finally {
      setOffersLoading(false);
    }
  };

  const handleRent = async (offerId: number) => {
    setActionLoading("rent");
    setError(null);
    try {
      const data = await rentGpuWithOffer(offerId);
      setGpu(data);
      setShowOffers(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to rent GPU");
    } finally {
      setActionLoading(null);
    }
  };

  const handleFetchInstances = async () => {
    setShowConnect(true);
    setShowOffers(false);
    setConnectLoading(true);
    setError(null);
    try {
      const data = await listMyInstances();
      setMyInstances(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch instances");
    } finally {
      setConnectLoading(false);
    }
  };

  const handleConnect = async (instanceId: number) => {
    setActionLoading("connect");
    setError(null);
    try {
      const data = await connectGpu(instanceId);
      setGpu(data);
      setShowConnect(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to connect GPU");
    } finally {
      setActionLoading(null);
    }
  };

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
              <>
                <button
                  onClick={handleFetchOffers}
                  disabled={!!actionLoading}
                  className="flex-1 py-2.5 px-4 rounded-lg font-medium text-white bg-violet-600 hover:bg-violet-500 disabled:bg-zinc-700 disabled:text-zinc-500 transition-colors"
                >
                  Rent GPU
                </button>
                <button
                  onClick={handleFetchInstances}
                  disabled={!!actionLoading}
                  className="flex-1 py-2.5 px-4 rounded-lg font-medium text-white bg-zinc-700 hover:bg-zinc-600 disabled:bg-zinc-800 disabled:text-zinc-500 transition-colors"
                >
                  Connect Existing
                </button>
              </>
            )}

            {(gpu?.status === "error" || (gpu?.status === "running" && !gpu.is_setup_done)) && gpu.ssh_host && (
              <button
                onClick={() => handleAction("retry-setup", retrySetup)}
                disabled={!!actionLoading}
                className="flex-1 py-2.5 px-4 rounded-lg font-medium text-white bg-violet-600 hover:bg-violet-500 disabled:bg-zinc-700 disabled:text-zinc-500 transition-colors"
              >
                {actionLoading === "retry-setup" ? "Retrying..." : "Retry Setup"}
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

            {/* Destroy always visible when not offline */}
            {gpu && gpu.status !== "offline" && (
              <button
                onClick={() => handleAction("destroy", destroyGpu)}
                disabled={!!actionLoading}
                className="py-2.5 px-4 rounded-lg font-medium text-red-400 bg-red-500/10 border border-red-500/20 hover:bg-red-500/20 disabled:opacity-50 transition-colors"
              >
                {actionLoading === "destroy" ? "..." : "Destroy"}
              </button>
            )}
          </div>

          {(gpu?.status === "renting" || gpu?.status === "setup") && (
            <p className="text-xs text-zinc-500 text-center">
              This may take a few minutes. Status will update automatically.
            </p>
          )}
        </div>

        {/* GPU Offer Picker */}
        {showOffers && (
          <div className="bg-zinc-900 rounded-xl p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">Select GPU</h2>
              <button
                onClick={() => setShowOffers(false)}
                className="text-zinc-500 hover:text-zinc-300 text-sm"
              >
                Cancel
              </button>
            </div>

            {offersLoading ? (
              <p className="text-zinc-500 text-center py-4">Searching available GPUs...</p>
            ) : offers.length === 0 ? (
              <p className="text-zinc-500 text-center py-4">No suitable GPU offers found. Try again later.</p>
            ) : (
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {offers.map((offer) => (
                  <button
                    key={offer.id}
                    onClick={() => handleRent(offer.id)}
                    disabled={!!actionLoading}
                    className="w-full text-left p-3 rounded-lg bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-white font-medium">{offer.gpu_name}</span>
                      <span className="text-green-400 font-medium">${offer.dph_total.toFixed(3)}/hr</span>
                    </div>
                    <div className="flex gap-4 mt-1 text-xs text-zinc-500">
                      <span>{offer.gpu_ram}GB VRAM</span>
                      <span>{offer.cpu_cores} CPU cores</span>
                      <span>{offer.disk_space}GB disk</span>
                      {offer.reliability && <span>{(offer.reliability * 100).toFixed(0)}% reliability</span>}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Connect Existing Instance */}
        {showConnect && (
          <div className="bg-zinc-900 rounded-xl p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">Your Instances</h2>
              <button
                onClick={() => setShowConnect(false)}
                className="text-zinc-500 hover:text-zinc-300 text-sm"
              >
                Cancel
              </button>
            </div>

            {connectLoading ? (
              <p className="text-zinc-500 text-center py-4">Fetching your instances...</p>
            ) : myInstances.length === 0 ? (
              <p className="text-zinc-500 text-center py-4">No instances found on your vast.ai account.</p>
            ) : (
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {myInstances.map((inst) => (
                  <button
                    key={inst.id}
                    onClick={() => handleConnect(inst.id)}
                    disabled={!!actionLoading}
                    className="w-full text-left p-3 rounded-lg bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-white font-medium">{inst.gpu_name}</span>
                      <span className="text-green-400 font-medium">${inst.cost_per_hour.toFixed(3)}/hr</span>
                    </div>
                    <div className="flex gap-4 mt-1 text-xs text-zinc-500">
                      <span>{inst.gpu_ram}GB VRAM</span>
                      <span>ID: {inst.id}</span>
                      <span className={inst.status === "running" ? "text-green-500" : "text-yellow-500"}>
                        {inst.status}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Info */}
        <div className="bg-zinc-900/50 rounded-xl p-4 space-y-2 text-sm text-zinc-500">
          <p><strong className="text-zinc-400">Rent</strong> — Pick a GPU, creates instance, and installs Wan 2.2 model (~72GB, first time only)</p>
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
