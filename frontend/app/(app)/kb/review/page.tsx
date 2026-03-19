"use client";
import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";

interface QueueEntry {
  entry_id: string;
  jurisdiction: string;
  topic: string;
  content: string;
  web_url: string;
  date_retrieved: string | null;
  current_status: string;
  review_count: number;
  rejection_note: string | null;
}

export default function KBReviewPage() {
  const { data: session } = useSession();
  const [entries, setEntries] = useState<QueueEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  const token = session?.accessToken;

  useEffect(() => {
    if (!token) return;
    fetch(`${apiUrl}/kb/review-queue`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then(setEntries)
      .finally(() => setLoading(false));
  }, [token, apiUrl]);

  const handleAction = async (entryId: string, action: "approve" | "reject") => {
    await fetch(`${apiUrl}/kb/review-queue/${entryId}/action`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ action }),
    });
    setEntries((prev) => prev.filter((e) => e.entry_id !== entryId));
  };

  if (loading) return <div className="p-8">Loading...</div>;
  if (session?.user?.role !== "advisor")
    return <div className="p-8 text-red-600">Access denied. Advisors only.</div>;

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-6">KB Review Queue</h1>
      {entries.length === 0 ? (
        <p className="text-gray-500">No entries pending review.</p>
      ) : (
        <div className="space-y-4">
          {entries.map((entry) => (
            <div key={entry.entry_id} className="border rounded-lg p-4">
              <div className="flex justify-between items-start mb-2">
                <span className="text-sm text-gray-500">
                  {entry.jurisdiction} &middot; {entry.topic} &middot;{" "}
                  {entry.date_retrieved
                    ? new Date(entry.date_retrieved).toLocaleDateString()
                    : "Unknown date"}
                </span>
              </div>
              {entry.web_url && (
                <a
                  href={entry.web_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-blue-600 hover:underline mb-1 block truncate"
                >
                  {entry.web_url}
                </a>
              )}
              <p className="text-sm mb-3 line-clamp-3">{entry.content}</p>
              <div className="flex gap-2">
                <button
                  onClick={() => handleAction(entry.entry_id, "approve")}
                  className="px-3 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-700"
                >
                  Approve
                </button>
                <button
                  onClick={() => handleAction(entry.entry_id, "reject")}
                  className="px-3 py-1 bg-red-600 text-white rounded text-sm hover:bg-red-700"
                >
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
