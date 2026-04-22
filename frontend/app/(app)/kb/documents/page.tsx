"use client";
import { useSession } from "next-auth/react";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Plus, Search, Trash2, FileText } from "lucide-react";
import { JURISDICTIONS, jurisdictionFlag, jurisdictionLabel } from "@/lib/jurisdictions";

interface KBDocument {
  source_file: string;
  jurisdiction: string;
  topic: string;
  last_updated: string;
  source_type: string;
  chunk_count: number;
}

export default function KBDocumentsPage() {
  const { data: session } = useSession();
  const token = session?.accessToken ?? "";
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const [docs, setDocs] = useState<KBDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [filterJ, setFilterJ] = useState<string>("all");
  const [query, setQuery] = useState("");

  useEffect(() => {
    if (!token || !["admin", "advisor"].includes(session?.user?.role ?? "")) {
      setLoading(false);
      return;
    }
    fetch(`${apiUrl}/kb/documents`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => {
        if (!r.ok) throw new Error(`Failed to load: ${r.status}`);
        return r.json();
      })
      .then(setDocs)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [token, apiUrl, session?.user?.role]);

  const filtered = useMemo(() => {
    return docs.filter((d) => {
      if (filterJ !== "all" && d.jurisdiction !== filterJ) return false;
      if (query && !d.source_file.toLowerCase().includes(query.toLowerCase())) return false;
      return true;
    });
  }, [docs, filterJ, query]);

  const countsByJ = useMemo(() => {
    const map: Record<string, number> = {};
    for (const d of docs) map[d.jurisdiction] = (map[d.jurisdiction] || 0) + 1;
    return map;
  }, [docs]);

  async function handleDelete(sourceFile: string) {
    if (!confirm(`Delete "${sourceFile}" from the knowledge base? This cannot be undone.`)) return;
    setDeleting(sourceFile);
    try {
      const res = await fetch(`${apiUrl}/kb/documents/${encodeURIComponent(sourceFile)}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
      setDocs((prev) => prev.filter((d) => d.source_file !== sourceFile));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setDeleting(null);
    }
  }

  if (loading)
    return (
      <div className="max-w-6xl mx-auto px-8 py-10 text-ink-400 text-sm">Loading…</div>
    );

  if (!["admin", "advisor"].includes(session?.user?.role ?? ""))
    return (
      <div className="max-w-6xl mx-auto px-8 py-16 text-ember-500">
        Access denied. Advisors and admins only.
      </div>
    );

  return (
    <div className="max-w-6xl mx-auto w-full px-8 py-10">
      <header className="mb-8 flex items-start justify-between gap-6 animate-fade-in-up">
        <div>
          <p className="text-[11px] uppercase tracking-[0.2em] text-ink-400 font-medium">Knowledge base</p>
          <h1 className="mt-2 font-display text-[38px] leading-[1.05] tracking-tight text-ink-100">
            Documents
            <em className="italic text-brass-400 font-normal">.</em>
          </h1>
          <p className="mt-2 text-ink-300 text-[15px]">
            {docs.length} document{docs.length !== 1 ? "s" : ""} across {Object.keys(countsByJ).length} jurisdiction
            {Object.keys(countsByJ).length !== 1 ? "s" : ""}
          </p>
        </div>
        <Link
          href="/kb/upload"
          className="inline-flex items-center gap-2 rounded-lg bg-lc-red text-lc-white px-4 py-2.5 text-sm font-semibold hover:bg-lc-red/90 transition"
        >
          <Plus size={16} />
          Upload
        </Link>
      </header>

      {error && (
        <div className="mb-5 rounded-lg border border-ember-500/40 bg-ember-500/10 px-4 py-3 text-sm text-ember-500">
          {error}
        </div>
      )}

      {/* Filters */}
      <div className="mb-5 flex flex-col md:flex-row md:items-center gap-3 animate-fade-in-up" style={{ animationDelay: '0.05s' }}>
        <div className="relative flex-1 max-w-md">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-400" />
          <input
            type="search"
            placeholder="Search by filename…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2.5 bg-ink-900 border border-ink-800 rounded-lg text-sm text-ink-100 placeholder:text-ink-500 focus:outline-none focus:border-brass-500 focus:ring-2 focus:ring-brass-500/20 transition"
          />
        </div>

        <div className="flex flex-wrap gap-1.5">
          <FilterPill label="All" count={docs.length} active={filterJ === "all"} onClick={() => setFilterJ("all")} />
          {JURISDICTIONS.map((j) =>
            countsByJ[j.slug] ? (
              <FilterPill
                key={j.slug}
                label={`${j.flag} ${j.label}`}
                count={countsByJ[j.slug]}
                active={filterJ === j.slug}
                onClick={() => setFilterJ(j.slug)}
              />
            ) : null
          )}
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-ink-700 bg-ink-900/30 p-12 text-center">
          <FileText size={28} className="mx-auto text-ink-500 mb-3" />
          <p className="text-sm text-ink-300">
            {docs.length === 0
              ? "No documents uploaded yet."
              : "No documents match your filters."}
          </p>
          {docs.length === 0 && (
            <Link
              href="/kb/upload"
              className="mt-4 inline-flex items-center gap-2 text-brass-400 text-sm font-medium hover:text-brass-300"
            >
              <Plus size={14} /> Upload your first document
            </Link>
          )}
        </div>
      ) : (
        <div className="rounded-2xl border border-ink-800 bg-ink-900 overflow-hidden animate-fade-in-up" style={{ animationDelay: '0.08s' }}>
          <table className="w-full text-sm">
            <thead className="bg-ink-850 border-b border-ink-800">
              <tr>
                <Th>File</Th>
                <Th>Jurisdiction</Th>
                <Th>Topic</Th>
                <Th className="text-right">Chunks</Th>
                <Th>Updated</Th>
                <Th className="w-10" />
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-800">
              {filtered.map((doc) => (
                <tr key={doc.source_file} className="hover:bg-ink-850 transition group">
                  <td className="px-4 py-3 font-medium text-ink-100 max-w-xs truncate" title={doc.source_file}>
                    {doc.source_file}
                  </td>
                  <td className="px-4 py-3">
                    {doc.jurisdiction ? (
                      <span className="chip">
                        <span>{jurisdictionFlag(doc.jurisdiction)}</span>
                        {jurisdictionLabel(doc.jurisdiction)}
                      </span>
                    ) : (
                      <span className="text-ink-500">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-ink-300">{doc.topic || <span className="text-ink-500">—</span>}</td>
                  <td className="px-4 py-3 text-ink-300 text-right tabular-nums">{doc.chunk_count}</td>
                  <td className="px-4 py-3 text-ink-400">
                    {doc.last_updated ? new Date(doc.last_updated).toLocaleDateString() : "—"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => handleDelete(doc.source_file)}
                      disabled={deleting === doc.source_file}
                      title="Delete"
                      className="p-1.5 rounded-md text-ink-400 hover:text-ember-500 hover:bg-ember-500/10 disabled:opacity-40 transition opacity-0 group-hover:opacity-100"
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Th({ children, className = "" }: { children?: React.ReactNode; className?: string }) {
  return (
    <th
      className={`text-left px-4 py-2.5 text-[11px] uppercase tracking-[0.14em] font-medium text-ink-400 ${className}`}
    >
      {children}
    </th>
  );
}

function FilterPill({
  label,
  count,
  active,
  onClick,
}: {
  label: string;
  count: number;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[12px] font-medium transition ${
        active
          ? "border-brass-500/60 bg-brass-500/10 text-brass-300"
          : "border-ink-800 bg-ink-900 text-ink-300 hover:border-ink-700 hover:text-ink-100"
      }`}
    >
      {label}
      <span className={`text-[10px] font-normal ${active ? "text-brass-400" : "text-ink-500"}`}>{count}</span>
    </button>
  );
}
