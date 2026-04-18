"use client";

import { getResultUrl } from "@/lib/api";

interface VideoPlayerProps {
  jobId: string;
}

export default function VideoPlayer({ jobId }: VideoPlayerProps) {
  const videoUrl = getResultUrl(jobId);

  return (
    <div className="rounded-xl overflow-hidden bg-black">
      <video
        src={videoUrl}
        controls
        autoPlay
        loop
        className="w-full max-h-[500px] object-contain"
      >
        Your browser does not support the video tag.
      </video>
      <div className="p-3 bg-zinc-900 flex justify-end">
        <a
          href={videoUrl}
          download={`yoman_${jobId}.mp4`}
          className="px-4 py-2 bg-violet-600 text-white text-sm font-medium rounded-lg hover:bg-violet-500 transition-colors"
        >
          Download
        </a>
      </div>
    </div>
  );
}
