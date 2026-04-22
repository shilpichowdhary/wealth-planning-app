"use client";
import { useSession } from "next-auth/react";
import { useState } from "react";
import { UploadCloud, FileText, CheckCircle2, AlertTriangle } from "lucide-react";
import { JURISDICTIONS } from "@/lib/jurisdictions";

export default function KBUploadPage() {
  const { data: session } = useSession();
  const token = session?.accessToken ?? "";
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const [file, setFile] = useState<File | null>(null);
  const [jurisdiction, setJurisdiction] = useState(JURISDICTIONS[0].slug);
  const [topic, setTopic] = useState("");
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<{ chunks: number; message: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  if (!["admin", "advisor"].includes(session?.user?.role ?? "")) {
    return (
      <div className="max-w-2xl mx-auto px-8 py-16 text-ember-500">
        Access denied. Advisors and admins only.
      </div>
    );
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
      setResult({
        chunks: data.chunks_added ?? data.chunk_count ?? 0,
        message: data.message ?? "Uploaded successfully",
      });
      setFile(null);
      (e.target as HTMLFormElement).reset();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  function handleDrop(e: React.DragEvent<HTMLLabelElement>) {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) setFile(dropped);
  }

  return (
    <div className="max-w-3xl mx-auto w-full px-8 py-10">
      <header className="mb-8 animate-fade-in-up">
        <p className="text-[11px] uppercase tracking-[0.2em] text-ink-400 font-medium">Knowledge base</p>
        <h1 className="mt-2 font-display text-[38px] leading-[1.05] tracking-tight text-ink-100">
          Upload<em className="italic text-brass-400 font-normal">.</em>
        </h1>
        <p className="mt-2 text-ink-300 text-[15px] max-w-xl">
          Add a PDF, Word, or plaintext document to the firm knowledge base. Text is chunked and embedded for RAG
          retrieval.
        </p>
      </header>

      <form onSubmit={handleUpload} className="space-y-5 animate-fade-in-up" style={{ animationDelay: '0.05s' }}>
        <div className="rounded-2xl border border-ink-800 bg-ink-900 p-6 space-y-5">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-[11px] uppercase tracking-[0.16em] text-ink-400 font-medium mb-1.5">
                Jurisdiction
              </label>
              <select
                value={jurisdiction}
                onChange={(e) => setJurisdiction(e.target.value as typeof jurisdiction)}
                className="w-full bg-ink-850 border border-ink-700 rounded-lg px-4 py-2.5 text-sm text-ink-100 focus:outline-none focus:border-brass-500 focus:ring-2 focus:ring-brass-500/20 transition"
              >
                {JURISDICTIONS.map((j) => (
                  <option key={j.slug} value={j.slug} className="bg-ink-900">
                    {j.flag}  {j.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-[11px] uppercase tracking-[0.16em] text-ink-400 font-medium mb-1.5">
                Topic <span className="normal-case tracking-normal text-ink-500">(optional)</span>
              </label>
              <input
                type="text"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="e.g. inheritance tax, trust structures"
                className="w-full bg-ink-850 border border-ink-700 rounded-lg px-4 py-2.5 text-sm text-ink-100 placeholder:text-ink-500 focus:outline-none focus:border-brass-500 focus:ring-2 focus:ring-brass-500/20 transition"
              />
            </div>
          </div>

          <div>
            <label className="block text-[11px] uppercase tracking-[0.16em] text-ink-400 font-medium mb-1.5">
              Document
            </label>
            <label
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              className={`relative flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-8 cursor-pointer transition ${
                dragOver
                  ? "border-brass-500 bg-brass-500/5"
                  : file
                  ? "border-brass-500/40 bg-brass-500/[0.04]"
                  : "border-ink-700 bg-ink-850 hover:border-ink-600"
              }`}
            >
              <input
                type="file"
                accept=".pdf,.doc,.docx,.txt,.md"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="sr-only"
                required
              />
              {file ? (
                <>
                  <FileText size={28} className="text-brass-400" />
                  <p className="text-sm text-ink-100 font-medium">{file.name}</p>
                  <p className="text-[11px] text-ink-400">{(file.size / 1024).toFixed(0)} KB · click to change</p>
                </>
              ) : (
                <>
                  <UploadCloud size={28} className="text-ink-400" />
                  <p className="text-sm text-ink-200 font-medium">Drop your file here, or click to browse</p>
                  <p className="text-[11px] text-ink-500">PDF, Word, TXT, Markdown — up to 20MB</p>
                </>
              )}
            </label>
          </div>

          {error && (
            <div className="flex items-center gap-2 rounded-lg border border-ember-500/40 bg-ember-500/10 px-3 py-2 text-sm text-ember-500">
              <AlertTriangle size={14} />
              {error}
            </div>
          )}

          {result && (
            <div className="flex items-center gap-2 rounded-lg border border-jade-500/40 bg-jade-500/10 px-3 py-2 text-sm text-jade-500">
              <CheckCircle2 size={14} />
              <span>
                {result.message} — <strong>{result.chunks} chunks</strong> embedded.
              </span>
            </div>
          )}

          <button
            type="submit"
            disabled={uploading || !file}
            className="w-full rounded-lg bg-lc-red text-lc-white py-3 text-sm font-semibold hover:bg-lc-red/90 transition disabled:opacity-50"
          >
            {uploading ? "Uploading & embedding…" : "Upload to knowledge base"}
          </button>
        </div>
      </form>

      <div className="mt-6 rounded-2xl border border-ink-800 bg-ink-900/40 p-5 animate-fade-in-up" style={{ animationDelay: '0.1s' }}>
        <p className="text-[11px] uppercase tracking-[0.16em] text-ink-400 font-medium mb-2">
          Suggested topics by jurisdiction
        </p>
        <ul className="text-[13px] text-ink-300 space-y-1.5">
          <li><span className="text-ink-100 font-medium">India</span> — IT Act HNI sections, FEMA, trust structures</li>
          <li><span className="text-ink-100 font-medium">Singapore</span> — MAS guidelines, VCC framework, estate duty</li>
          <li><span className="text-ink-100 font-medium">UAE</span> — DIFC/ADGM trusts, zero-tax residency rules</li>
          <li><span className="text-ink-100 font-medium">UK</span> — IHT400, non-dom/domicile, trust registration</li>
          <li><span className="text-ink-100 font-medium">USA</span> — IRC gift/estate, trust structures, FBAR</li>
          <li><span className="text-ink-100 font-medium">Taiwan / China</span> — CFC, exchange controls, trust regulation</li>
        </ul>
      </div>
    </div>
  );
}
