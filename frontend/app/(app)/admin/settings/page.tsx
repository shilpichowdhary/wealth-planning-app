"use client";
import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";
import { AlertTriangle, Check, PlugZap, Loader2, Database, RefreshCw } from "lucide-react";

interface SettingEntry {
  label: string;
  value: string;
  is_set: boolean;
}

interface TestResult {
  ok: boolean;
  stage?: string;
  detail: string;
  raw?: string;
  model?: string;
  input_tokens?: number;
  stop_reason?: string;
}

interface RechunkResult {
  ok: boolean;
  documents?: number;
  total_old_chunks?: number;
  total_new_chunks?: number;
  failed?: string[];
  detail?: string;
}

export default function AdminSettingsPage() {
  const { data: session } = useSession();
  const token = session?.accessToken ?? "";
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const [settings, setSettings] = useState<Record<string, SettingEntry>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [drafts, setDrafts] = useState<Record<string, string>>({});

  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);

  const [rechunking, setRechunking] = useState(false);
  const [rechunkResult, setRechunkResult] = useState<RechunkResult | null>(null);

  useEffect(() => {
    if (!token || session?.user?.role !== "admin") {
      setLoading(false);
      return;
    }
    loadSettings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, session?.user?.role]);

  async function loadSettings() {
    setLoading(true);
    try {
      const res = await fetch(`${apiUrl}/admin/settings`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`Failed to load: ${res.status}`);
      const data = await res.json();
      setSettings(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load settings");
    } finally {
      setLoading(false);
    }
  }

  async function handleSave(key: string) {
    const value = drafts[key];
    if (!value || !value.trim()) return;
    setSaving(key);
    setError(null);
    setSuccess(null);
    try {
      const res = await fetch(`${apiUrl}/admin/settings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ key, value: value.trim() }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Failed" }));
        throw new Error(err.detail || "Failed to save");
      }
      setDrafts((prev) => ({ ...prev, [key]: "" }));
      setSuccess(key);
      setTestResult(null);
      setTimeout(() => setSuccess(null), 3000);
      await loadSettings();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save setting");
    } finally {
      setSaving(null);
    }
  }

  async function handleTestAnthropic() {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await fetch(`${apiUrl}/admin/settings/test-anthropic`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setTestResult(data);
    } catch (e: unknown) {
      setTestResult({
        ok: false,
        stage: "client",
        detail: e instanceof Error ? e.message : "Request failed from the browser.",
      });
    } finally {
      setTesting(false);
    }
  }

  async function handleRechunk() {
    if (
      !window.confirm(
        "Re-chunk the entire knowledge base?\n\nEvery document is re-embedded at the current chunk size and its chunks are replaced. This can take a while on a large KB and briefly rebuilds each document. Run during a quiet window."
      )
    )
      return;
    setRechunking(true);
    setRechunkResult(null);
    try {
      const res = await fetch(`${apiUrl}/kb/rechunk`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (!res.ok) {
        setRechunkResult({ ok: false, detail: data.detail || `Failed (${res.status})` });
      } else {
        setRechunkResult({ ok: true, ...data });
      }
    } catch (e: unknown) {
      setRechunkResult({
        ok: false,
        detail: e instanceof Error ? e.message : "Request failed from the browser.",
      });
    } finally {
      setRechunking(false);
    }
  }

  if (loading)
    return <div className="max-w-2xl mx-auto px-8 py-10 text-ink-500 text-sm">Loading…</div>;
  if (session?.user?.role !== "admin")
    return (
      <div className="max-w-2xl mx-auto px-8 py-16 text-ember-500">Access denied. Admins only.</div>
    );

  return (
    <div className="max-w-2xl mx-auto w-full px-8 py-10">
      <header className="mb-8 animate-fade-in-up">
        <p className="text-[11px] uppercase tracking-[0.2em] text-ink-500 font-bold">Administration</p>
        <h1 className="mt-2 font-display text-[38px] leading-[1.05] text-lc-black">
          API keys &amp; settings<span className="text-lc-red">.</span>
        </h1>
        <p className="mt-2 text-ink-600 text-[15px]">
          Manage API keys used by the system. Keys are stored encrypted and masked for display.
        </p>
      </header>

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-lc-red bg-lc-red/10 px-4 py-3 text-sm text-lc-red">
          <AlertTriangle size={14} />
          {error}
        </div>
      )}

      <div className="space-y-3 animate-fade-in-up" style={{ animationDelay: "0.05s" }}>
        {Object.entries(settings).map(([key, setting]) => (
          <div
            key={key}
            className="rounded-2xl border border-ink-200 bg-white p-5 animate-fade-in-up"
          >
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-bold text-ink-900">
                {setting.label}
              </label>
              <span
                className={
                  setting.is_set
                    ? "lc-pill lc-pill-ok"
                    : "lc-pill lc-pill-neutral"
                }
              >
                {setting.is_set ? "Configured" : "Not set"}
              </span>
            </div>

            {setting.is_set && setting.value && (
              <p className="text-xs text-ink-500 font-mono mb-2">
                Current: {setting.value}
              </p>
            )}

            <div className="flex flex-col sm:flex-row gap-2">
              <input
                type={key === "claude_model" ? "text" : "password"}
                value={drafts[key] || ""}
                onChange={(e) => setDrafts((prev) => ({ ...prev, [key]: e.target.value }))}
                placeholder={
                  key === "claude_model"
                    ? "e.g. claude-sonnet-4-6"
                    : `Paste your ${setting.label}…`
                }
                className="flex-1 bg-ink-50 border border-ink-300 rounded-lg px-3 py-2 text-sm text-lc-black placeholder:text-ink-400 focus:outline-none focus:border-lc-red focus:ring-2 focus:ring-lc-red/20 transition"
              />
              <button
                onClick={() => handleSave(key)}
                disabled={!drafts[key]?.trim() || saving === key}
                className="lc-btn-primary"
              >
                {saving === key ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                {saving === key ? "Saving…" : "Save"}
              </button>
            </div>

            {success === key && (
              <p className="mt-2 inline-flex items-center gap-1 text-xs text-jade-500 font-bold">
                <Check size={11} />
                Saved successfully.
              </p>
            )}
          </div>
        ))}
      </div>

      {/* Diagnostics */}
      <div
        className="mt-6 rounded-2xl border border-ink-800 bg-ink-900 p-5 animate-fade-in-up"
        style={{ animationDelay: "0.1s" }}
      >
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <p className="text-[11px] uppercase tracking-[0.16em] text-ink-400 font-bold flex items-center gap-2">
              <PlugZap size={12} />
              Diagnostics
            </p>
            <h2 className="mt-1 font-display text-lg text-lc-white">Test Anthropic connection</h2>
            <p className="mt-1 text-[13px] text-ink-300 max-w-lg">
              Pings Anthropic with the currently-saved key + model. Surfaces the exact failure
              mode (auth, model, network, rate-limit) so you don&apos;t need to read server logs.
            </p>
          </div>
          <button
            onClick={handleTestAnthropic}
            disabled={testing}
            className="inline-flex items-center gap-1.5 rounded-lg bg-lc-red text-lc-white px-4 py-2 text-sm font-bold hover:bg-lc-red/90 transition disabled:opacity-50"
          >
            {testing ? <Loader2 size={14} className="animate-spin" /> : <PlugZap size={14} />}
            {testing ? "Testing…" : "Run test"}
          </button>
        </div>

        {testResult && (
          <div
            className={`mt-4 rounded-lg border px-4 py-3 ${
              testResult.ok ? "border-ink-600 bg-ink-850" : "border-lc-red/50 bg-lc-red/5"
            }`}
          >
            <div className="flex items-center gap-2 mb-1.5">
              {testResult.ok ? (
                <Check size={14} className="text-lc-white" />
              ) : (
                <AlertTriangle size={14} className="text-lc-red" />
              )}
              <span className={`text-[11px] uppercase tracking-[0.16em] font-bold ${testResult.ok ? "text-lc-white" : "text-lc-red"}`}>
                {testResult.ok ? "Success" : `Failed — ${testResult.stage ?? "error"}`}
              </span>
            </div>
            <p className="text-[13px] text-ink-200">{testResult.detail}</p>
            {testResult.ok && testResult.model && (
              <p className="mt-1.5 text-[11px] text-ink-400 font-mono">
                model={testResult.model} · input_tokens={testResult.input_tokens} ·
                stop_reason={testResult.stop_reason}
              </p>
            )}
            {testResult.raw && (
              <p className="mt-1.5 text-[11px] text-ink-400 font-mono break-all">Raw: {testResult.raw}</p>
            )}
          </div>
        )}
      </div>

      {/* Knowledge base maintenance */}
      <div
        className="mt-6 rounded-2xl border border-ink-200 bg-white p-5 animate-fade-in-up"
        style={{ animationDelay: "0.12s" }}
      >
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <p className="text-[11px] uppercase tracking-[0.16em] text-ink-500 font-bold flex items-center gap-2">
              <Database size={12} />
              Knowledge base
            </p>
            <h2 className="mt-1 font-display text-lg text-lc-black">Re-chunk knowledge base</h2>
            <p className="mt-1 text-[13px] text-ink-600 max-w-lg">
              Re-embeds every document at the current chunk size. Documents added under the
              older, larger chunking gain the sharper retrieval of the current chunking.
              Lossless and safe to run more than once — but it re-embeds the whole KB, so run
              it during a quiet window.
            </p>
          </div>
          <button
            onClick={handleRechunk}
            disabled={rechunking}
            className="inline-flex items-center gap-1.5 rounded-lg bg-lc-black text-lc-white px-4 py-2 text-sm font-bold hover:bg-lc-black/90 transition disabled:opacity-50"
          >
            {rechunking ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            {rechunking ? "Re-chunking…" : "Re-chunk KB"}
          </button>
        </div>

        {rechunking && (
          <p className="mt-3 text-[12px] text-ink-500">
            This runs synchronously and may take a while on a large KB — keep this tab open.
          </p>
        )}

        {rechunkResult && (
          <div
            className={`mt-4 rounded-lg border px-4 py-3 ${
              rechunkResult.ok ? "border-jade-500/40 bg-jade-500/5" : "border-lc-red/50 bg-lc-red/5"
            }`}
          >
            <div className="flex items-center gap-2 mb-1.5">
              {rechunkResult.ok ? (
                <Check size={14} className="text-jade-500" />
              ) : (
                <AlertTriangle size={14} className="text-lc-red" />
              )}
              <span
                className={`text-[11px] uppercase tracking-[0.16em] font-bold ${
                  rechunkResult.ok ? "text-jade-500" : "text-lc-red"
                }`}
              >
                {rechunkResult.ok ? "Done" : "Failed"}
              </span>
            </div>
            {rechunkResult.ok ? (
              <>
                <p className="text-[13px] text-ink-700">
                  Re-chunked <strong>{rechunkResult.documents}</strong> document
                  {rechunkResult.documents === 1 ? "" : "s"} —{" "}
                  <span className="font-mono">
                    {rechunkResult.total_old_chunks} → {rechunkResult.total_new_chunks}
                  </span>{" "}
                  chunks.
                </p>
                {rechunkResult.failed && rechunkResult.failed.length > 0 && (
                  <p className="mt-1.5 text-[12px] text-lc-red">
                    {rechunkResult.failed.length} document
                    {rechunkResult.failed.length === 1 ? "" : "s"} failed:{" "}
                    <span className="font-mono break-all">{rechunkResult.failed.join(", ")}</span>
                  </p>
                )}
              </>
            ) : (
              <p className="text-[13px] text-ink-700">{rechunkResult.detail}</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
