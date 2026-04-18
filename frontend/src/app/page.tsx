"use client";

import { useState } from "react";
import UploadForm from "@/components/UploadForm";
import JobList from "@/components/JobList";

export default function Home() {
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <main className="flex-1 bg-zinc-950">
      <div className="max-w-2xl mx-auto px-4 py-8 space-y-8">
        <header>
          <h1 className="text-3xl font-bold text-white">Yoman</h1>
          <p className="text-zinc-400 mt-1">
            AI Video Generation powered by Wan 2.2 Animate
          </p>
        </header>

        <UploadForm onJobCreated={() => setRefreshKey((k) => k + 1)} />
        <JobList refreshKey={refreshKey} />
      </div>
    </main>
  );
}
