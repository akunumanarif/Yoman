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
