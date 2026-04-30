"use client";
import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";
import { Check, X, ExternalLink, ClipboardCheck } from "lucide-react";
import { jurisdictionFlag, jurisdictionLabel } from "@/lib/jurisdictions";

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
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<string | null>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const token = session?.accessToken;

  useEffect(() => {
    if (!token || !["admin", "advisor"].includes(session?.user?.role ?? "")) {
      setLoading(false);
      return;
    }
    fetch(`${apiUrl}/kb/review-queue`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => {
        if (!r.ok) throw new Error(`Failed to load review queue: ${r.status}`);
        return r.json();
      })
      .then((data) => setEntries(data))
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : "Failed to load review queue."),
      )
      .finally(() => setLoading(false));
  }, [token, apiUrl, session?.user?.role]);

  const handleAction = async (entryId: string, action: "approve" | "reject") => {
    setError(null);
    setSubmitting(entryId);
    try {
      const res = await fetch(`${apiUrl}/kb/review-queue/${entryId}/action`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ action }),
      });
      if (res.ok) {
        setEntries((prev) => prev.filter((e) => e.entry_id !== entryId));
      } else {
        setError("Action failed. Please try again.");
      }
    } finally {
      setSubmitting(null);
    }
  };

  if (loading)
    return <div className="max-w-4xl mx-auto px-8 py-10 text-ink-500 text-sm">Loading…</div>;
  if (!["admin", "advisor"].includes(session?.user?.role ?? ""))
    return (
      <div className="max-w-4xl mx-auto px-8 py-16 text-ember-500">
        Access denied. Advisors and admins only.
      </div>
    );

  return (
    <div className="max-w-4xl mx-auto w-full px-8 py-10">
      <header className="mb-8 animate-fade-in-up">
        <p className="text-[11px] uppercase tracking-[0.2em] text-ink-500 font-medium">Knowledge base</p>
        <h1 className="mt-2 font-display text-[38px] leading-[1.05] tracking-tight text-ink-900">
          Review queue
          <em className="italic text-brass-400 font-normal">.</em>
        </h1>
        <p className="mt-2 text-ink-600 text-[15px]">
          Web-sourced content awaiting approval into the knowledge base.
        </p>
      </header>

      {error && (
        <div className="mb-5 rounded-lg border border-ember-500/40 bg-ember-500/10 px-4 py-3 text-sm text-ember-500">
          {error}
        </div>
      )}

      {entries.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-ink-300 bg-white/30 p-12 text-center animate-fade-in-up">
          <ClipboardCheck size={28} className="mx-auto text-ink-400 mb-3" />
          <p className="text-sm text-ink-600">No entries pending review.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {entries.map((entry, i) => (
            <article
              key={entry.entry_id}
              style={{ animationDelay: `${i * 0.04}s` }}
              className="rounded-2xl border border-ink-200 bg-white p-5 animate-fade-in-up"
            >
              <div className="flex flex-wrap items-center gap-2 mb-3">
                {entry.jurisdiction && (
                  <span className="chip">
                    <span>{jurisdictionFlag(entry.jurisdiction)}</span>
                    {jurisdictionLabel(entry.jurisdiction)}
                  </span>
                )}
                {entry.topic && <span className="chip">{entry.topic}</span>}
                {entry.date_retrieved && (
                  <span className="text-[11px] text-ink-500">
                    {new Date(entry.date_retrieved).toLocaleDateString()}
                  </span>
                )}
              </div>

              {entry.web_url && (
                <a
                  href={entry.web_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-[12px] text-brass-400 hover:text-brass-300 mb-3 truncate max-w-full"
                >
                  <ExternalLink size={12} />
                  <span className="truncate">{entry.web_url}</span>
                </a>
              )}

              <p className="text-[14px] text-ink-800 leading-relaxed line-clamp-4 mb-4">{entry.content}</p>

              <div className="flex gap-2">
                <button
                  disabled={submitting !== null}
                  onClick={() => handleAction(entry.entry_id, "approve")}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-jade-500/15 border border-jade-500/40 text-jade-500 text-sm font-medium hover:bg-jade-500/25 transition disabled:opacity-50"
                >
                  <Check size={14} />
                  Approve
                </button>
                <button
                  disabled={submitting !== null}
                  onClick={() => handleAction(entry.entry_id, "reject")}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-ember-500/10 border border-ember-500/40 text-ember-500 text-sm font-medium hover:bg-ember-500/20 transition disabled:opacity-50"
                >
                  <X size={14} />
                  Reject
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
