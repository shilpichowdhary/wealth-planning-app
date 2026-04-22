"use client";
import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ArrowLeft, FileText } from "lucide-react";

const FRONTMATTER_RE = /^---\n([\s\S]*?)\n---\n?/;

interface Frontmatter {
  title?: string;
  jurisdiction?: string;
  topic?: string;
  status?: string;
  last_compiled?: string;
  data_as_of?: string;
}

function parseFrontmatter(raw: string): { meta: Frontmatter; body: string } {
  const m = raw.match(FRONTMATTER_RE);
  if (!m) return { meta: {}, body: raw };
  const meta: Frontmatter = {};
  for (const line of m[1].split("\n")) {
    const idx = line.indexOf(":");
    if (idx === -1) continue;
    const key = line.slice(0, idx).trim();
    const val = line.slice(idx + 1).trim().replace(/^["']|["']$/g, "");
    if (key && val && !val.startsWith("[") && !val.startsWith("{")) {
      (meta as Record<string, string>)[key] = val;
    }
  }
  return { meta, body: raw.slice(m[0].length) };
}

export default function WikiViewerPage() {
  const params = useParams();
  const slug = params.slug as string[] | undefined;
  const path = slug ? slug.map(decodeURIComponent).join("/") : "";

  const { data: session } = useSession();
  const token = session?.accessToken ?? "";
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";

  const [content, setContent] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token || !path) {
      setLoading(false);
      return;
    }
    fetch(`${apiUrl}/kb/wiki/${path}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (r) => {
        if (!r.ok) {
          const body = await r.json().catch(() => ({}));
          throw new Error(body.detail || `Failed to load (${r.status})`);
        }
        return r.json();
      })
      .then((data: { path: string; content: string }) => setContent(data.content))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [apiUrl, token, path]);

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-8 py-10 text-ink-400 text-sm">Loading…</div>
    );
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto px-8 py-10">
        <Link href="/kb/documents" className="inline-flex items-center gap-1.5 text-ink-400 hover:text-ink-100 text-sm mb-6">
          <ArrowLeft size={14} /> Back to documents
        </Link>
        <div className="rounded-lg border border-ember-500/40 bg-ember-500/10 px-4 py-3 text-sm text-ember-500">
          {error}
        </div>
      </div>
    );
  }

  const { meta, body } = parseFrontmatter(content);
  const basename = path.split("/").pop() || path;

  return (
    <div className="max-w-4xl mx-auto w-full px-8 py-10">
      <Link
        href="/kb/documents"
        className="inline-flex items-center gap-1.5 text-ink-400 hover:text-ink-100 text-sm mb-6 transition"
      >
        <ArrowLeft size={14} /> Back to documents
      </Link>

      <header className="mb-8 animate-fade-in-up">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-ink-400 font-medium mb-3">
          <FileText size={12} />
          <span>{path}</span>
        </div>
        <h1 className="font-display text-[38px] leading-[1.1] tracking-tight text-ink-100">
          {meta.title || basename.replace(/\.md$/, "")}
        </h1>
        {(meta.jurisdiction || meta.topic || meta.last_compiled) && (
          <div className="mt-4 flex flex-wrap gap-2">
            {meta.jurisdiction && <span className="chip">{meta.jurisdiction}</span>}
            {meta.topic && <span className="chip">{meta.topic}</span>}
            {meta.last_compiled && (
              <span className="chip">Compiled {meta.last_compiled}</span>
            )}
            {meta.status && meta.status !== "final" && (
              <span className="chip border-brass-500/40 text-brass-300">{meta.status}</span>
            )}
          </div>
        )}
      </header>

      <article className="wiki-prose animate-fade-in-up" style={{ animationDelay: "0.05s" }}>
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{body}</ReactMarkdown>
      </article>
    </div>
  );
}
