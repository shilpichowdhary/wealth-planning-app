"use client";
import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";
import Link from "next/link";

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

  useEffect(() => {
    if (!token || session?.user?.role !== "advisor" && session?.user?.role !== "admin") {
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

  if (loading) return <div className="p-8 text-slate-500">Loading...</div>;
  if (session?.user?.role !== "advisor" && session?.user?.role !== "admin")
    return <div className="p-8 text-red-600">Access denied. Advisors only.</div>;

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Knowledge Base Documents</h1>
          <p className="text-slate-500 text-sm mt-1">{docs.length} document{docs.length !== 1 ? "s" : ""} uploaded</p>
        </div>
        <Link
          href="/kb/upload"
          className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition"
        >
          + Upload Document
        </Link>
      </div>

      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">{error}</div>
      )}

      {docs.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
          <p className="text-slate-500 text-sm">No documents uploaded yet.</p>
          <Link href="/kb/upload" className="mt-3 inline-block text-blue-600 text-sm hover:underline">
            Upload your first document →
          </Link>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-slate-600">File</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Jurisdiction</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Topic</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Chunks</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Uploaded</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {docs.map((doc) => (
                <tr key={doc.source_file} className="hover:bg-slate-50 transition">
                  <td className="px-4 py-3 font-medium text-slate-900 max-w-xs truncate" title={doc.source_file}>
                    {doc.source_file}
                  </td>
                  <td className="px-4 py-3 text-slate-600">{doc.jurisdiction || "—"}</td>
                  <td className="px-4 py-3 text-slate-600">{doc.topic || "—"}</td>
                  <td className="px-4 py-3 text-slate-600">{doc.chunk_count}</td>
                  <td className="px-4 py-3 text-slate-500">
                    {doc.last_updated ? new Date(doc.last_updated).toLocaleDateString() : "—"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => handleDelete(doc.source_file)}
                      disabled={deleting === doc.source_file}
                      className="text-red-500 hover:text-red-700 text-xs font-medium disabled:opacity-40 transition"
                    >
                      {deleting === doc.source_file ? "Deleting..." : "Delete"}
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
