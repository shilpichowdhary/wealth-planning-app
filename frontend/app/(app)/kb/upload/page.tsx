"use client";
import { useSession } from "next-auth/react";
import { useState } from "react";

const JURISDICTIONS = ["India", "Singapore", "UAE", "UK", "USA", "cross_jurisdiction"];

export default function KBUploadPage() {
  const { data: session } = useSession();
  const token = session?.accessToken ?? "";
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const [file, setFile] = useState<File | null>(null);
  const [jurisdiction, setJurisdiction] = useState("India");
  const [topic, setTopic] = useState("");
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<{ chunks: number; message: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (session?.user?.role !== "advisor" && session?.user?.role !== "admin") {
    return <div className="p-8 text-red-600">Access denied. Advisors only.</div>;
  }

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setUploading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("jurisdiction", jurisdiction);
    formData.append("topic", topic || "general");

    try {
      const res = await fetch(`${apiUrl}/kb/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || "Upload failed");
      }
      const data = await res.json();
      setResult({ chunks: data.chunks_added ?? data.chunk_count ?? 0, message: data.message ?? "Uploaded successfully" });
      setFile(null);
      (e.target as HTMLFormElement).reset();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-slate-900 mb-2">Upload Knowledge Base Document</h1>
      <p className="text-slate-500 text-sm mb-6">
        Upload PDFs or Word documents (tax guides, estate planning, compliance rules). They will be
        chunked and embedded into the AI knowledge base.
      </p>

      <form onSubmit={handleUpload} className="bg-white rounded-xl border border-slate-200 p-6 space-y-5">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Jurisdiction</label>
          <select
            value={jurisdiction}
            onChange={(e) => setJurisdiction(e.target.value)}
            className="w-full border border-slate-300 rounded-lg px-4 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {JURISDICTIONS.map((j) => (
              <option key={j} value={j}>{j}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Topic <span className="text-slate-400 font-normal">(optional)</span></label>
          <input
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. inheritance tax, trust structures, estate duty"
            className="w-full border border-slate-300 rounded-lg px-4 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Document</label>
          <div className="border-2 border-dashed border-slate-300 rounded-lg p-6 text-center hover:border-blue-400 transition">
            <input
              type="file"
              accept=".pdf,.doc,.docx,.txt"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
              required
            />
            <p className="text-xs text-slate-400 mt-2">PDF, Word, or TXT — max 20MB</p>
          </div>
          {file && (
            <p className="text-sm text-slate-600 mt-2">Selected: <span className="font-medium">{file.name}</span> ({(file.size / 1024).toFixed(0)} KB)</p>
          )}
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">{error}</div>
        )}

        {result && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-700">
            ✓ {result.message} — <strong>{result.chunks} chunks</strong> added to the knowledge base.
          </div>
        )}

        <button
          type="submit"
          disabled={uploading || !file}
          className="w-full bg-blue-600 text-white rounded-lg py-2.5 text-sm font-semibold hover:bg-blue-700 transition disabled:opacity-50"
        >
          {uploading ? "Uploading & embedding..." : "Upload to Knowledge Base"}
        </button>
      </form>

      <div className="mt-6 bg-slate-100 rounded-xl p-4">
        <p className="text-xs font-semibold text-slate-600 mb-2">SUGGESTED DOCUMENTS TO UPLOAD</p>
        <ul className="text-xs text-slate-500 space-y-1">
          <li><strong>India:</strong> IT Act HNI taxation sections, FEMA regulations, trust structures</li>
          <li><strong>Singapore:</strong> MAS wealth management guidelines, estate duty rules</li>
          <li><strong>UAE:</strong> DIFC trust regulations, zero-tax residency rules</li>
          <li><strong>UK:</strong> IHT400 guidance, non-dom rules, trust registration</li>
          <li><strong>USA:</strong> IRC gift/estate tax sections, trust structures</li>
        </ul>
      </div>
    </div>
  );
}
