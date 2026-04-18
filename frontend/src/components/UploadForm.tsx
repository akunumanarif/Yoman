"use client";

import { useState, useRef } from "react";
import { createJob } from "@/lib/api";

interface UploadFormProps {
  onJobCreated: () => void;
}

export default function UploadForm({ onJobCreated }: UploadFormProps) {
  const [image, setImage] = useState<File | null>(null);
  const [video, setVideo] = useState<File | null>(null);
  const [resolution, setResolution] = useState("720");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const imageRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLInputElement>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!image || !video) return;

    setLoading(true);
    setError(null);

    try {
      await createJob(image, video, resolution);
      setImage(null);
      setVideo(null);
      if (imageRef.current) imageRef.current.value = "";
      if (videoRef.current) videoRef.current.value = "";
      onJobCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create job");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="bg-zinc-900 rounded-xl p-6 space-y-5">
      <h2 className="text-xl font-semibold text-white">Generate Video</h2>

      {/* Image Upload */}
      <div>
        <label className="block text-sm font-medium text-zinc-400 mb-2">
          Reference Image
        </label>
        <input
          ref={imageRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          onChange={(e) => setImage(e.target.files?.[0] || null)}
          className="block w-full text-sm text-zinc-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-violet-600 file:text-white hover:file:bg-violet-500 file:cursor-pointer"
        />
        {image && (
          <p className="mt-1 text-xs text-zinc-500">{image.name} ({(image.size / 1024 / 1024).toFixed(1)} MB)</p>
        )}
      </div>

      {/* Video Upload */}
      <div>
        <label className="block text-sm font-medium text-zinc-400 mb-2">
          Driving Video
        </label>
        <input
          ref={videoRef}
          type="file"
          accept="video/mp4,video/quicktime,video/x-msvideo"
          onChange={(e) => setVideo(e.target.files?.[0] || null)}
          className="block w-full text-sm text-zinc-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-violet-600 file:text-white hover:file:bg-violet-500 file:cursor-pointer"
        />
        {video && (
          <p className="mt-1 text-xs text-zinc-500">{video.name} ({(video.size / 1024 / 1024).toFixed(1)} MB)</p>
        )}
      </div>

      {/* Resolution */}
      <div>
        <label className="block text-sm font-medium text-zinc-400 mb-2">
          Resolution
        </label>
        <div className="flex gap-3">
          {["480", "720"].map((res) => (
            <button
              key={res}
              type="button"
              onClick={() => setResolution(res)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                resolution === res
                  ? "bg-violet-600 text-white"
                  : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
              }`}
            >
              {res}p
            </button>
          ))}
        </div>
      </div>

      {error && (
        <p className="text-red-400 text-sm">{error}</p>
      )}

      <button
        type="submit"
        disabled={!image || !video || loading}
        className="w-full py-3 px-4 rounded-lg font-medium text-white bg-violet-600 hover:bg-violet-500 disabled:bg-zinc-700 disabled:text-zinc-500 disabled:cursor-not-allowed transition-colors"
      >
        {loading ? "Uploading..." : "Generate Video"}
      </button>
    </form>
  );
}
