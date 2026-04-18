const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export interface Job {
  id: string;
  status:
    | "pending"
    | "provisioning"
    | "processing"
    | "retrying"
    | "completed"
    | "failed"
    | "cancelled";
  result_path: string | null;
  instance_id: string | null;
  retry_count: number;
  error_message: string | null;
  resolution: string;
  created_at: string;
  updated_at: string;
}

export interface GpuInstance {
  instance_id: number | null;
  status: "offline" | "renting" | "running" | "stopped" | "setup" | "error";
  gpu_name: string | null;
  ssh_host: string | null;
  ssh_port: number | null;
  cost_per_hour: number | null;
  error_message: string | null;
  is_setup_done: boolean;
  updated_at: string;
}

// === Job API ===

export async function createJob(
  image: File,
  video: File,
  resolution: string = "720"
): Promise<Job> {
  const formData = new FormData();
  formData.append("image", image);
  formData.append("video", video);
  formData.append("resolution", resolution);

  const res = await fetch(`${API_BASE}/jobs`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(error.detail || "Upload failed");
  }

  return res.json();
}

export async function listJobs(): Promise<Job[]> {
  const res = await fetch(`${API_BASE}/jobs`);
  if (!res.ok) throw new Error("Failed to fetch jobs");
  return res.json();
}

export async function getJob(id: string): Promise<Job> {
  const res = await fetch(`${API_BASE}/jobs/${id}`);
  if (!res.ok) throw new Error("Failed to fetch job");
  return res.json();
}

export async function deleteJob(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/jobs/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete job");
}

export function getResultUrl(id: string): string {
  return `${API_BASE}/jobs/${id}/result`;
}

// === GPU API ===

export interface GpuOffer {
  id: number;
  gpu_name: string;
  gpu_ram: number;
  cpu_cores: number;
  disk_space: number;
  dph_total: number;
  reliability: number | null;
}

export interface VastInstance {
  id: number;
  gpu_name: string;
  gpu_ram: number;
  status: string;
  cost_per_hour: number;
  cur_state: string;
}

export async function listMyInstances(): Promise<VastInstance[]> {
  const res = await fetch(`${API_BASE}/gpu/instances`);
  if (!res.ok) throw new Error("Failed to fetch instances");
  return res.json();
}

export async function getGpuStatus(): Promise<GpuInstance> {
  const res = await fetch(`${API_BASE}/gpu/status`);
  if (!res.ok) throw new Error("Failed to fetch GPU status");
  return res.json();
}

export async function listGpuOffers(): Promise<GpuOffer[]> {
  const res = await fetch(`${API_BASE}/gpu/offers`);
  if (!res.ok) throw new Error("Failed to fetch GPU offers");
  return res.json();
}

export async function rentGpuWithOffer(offerId: number): Promise<GpuInstance> {
  const res = await fetch(`${API_BASE}/gpu/rent`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ offer_id: offerId }),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to rent GPU" }));
    throw new Error(error.detail || "Failed to rent GPU");
  }
  return res.json();
}

async function gpuAction(action: string): Promise<GpuInstance> {
  const res = await fetch(`${API_BASE}/gpu/${action}`, { method: "POST" });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: `Failed to ${action} GPU` }));
    throw new Error(error.detail || `Failed to ${action} GPU`);
  }
  return res.json();
}

export async function connectGpu(instanceId: number): Promise<GpuInstance> {
  const res = await fetch(`${API_BASE}/gpu/connect`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ instance_id: instanceId }),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to connect GPU" }));
    throw new Error(error.detail || "Failed to connect GPU");
  }
  return res.json();
}

export const startGpu = () => gpuAction("start");
export const stopGpu = () => gpuAction("stop");
export const destroyGpu = () => gpuAction("destroy");
export const retrySetup = () => gpuAction("retry-setup");
