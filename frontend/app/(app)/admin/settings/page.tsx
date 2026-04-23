"use client";
import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";
import {
  KeyRound,
  Check,
  AlertTriangle,
  PlugZap,
  Loader2,
} from "lucide-react";

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

  if (loading)
    return <div className="max-w-3xl mx-auto px-8 py-10 text-ink-400 text-sm">Loading…</div>;
  if (session?.user?.role !== "admin")
    return (
      <div className="max-w-3xl mx-auto px-8 py-16 text-ember-500">Access denied. Admins only.</div>
    );

  return (
    <div className="max-w-3xl mx-auto w-full px-8 py-10">
      <header className="mb-8 animate-fade-in-up">
        <p className="text-[11px] uppercase tracking-[0.2em] text-ink-400 font-bold">Administration</p>
        <h1 className="mt-2 font-display text-[38px] leading-[1.05] text-lc-white">
          Settings<span className="text-lc-red">.</span>
        </h1>
        <p className="mt-2 text-ink-300 text-[15px]">
          API keys stored server-side and masked in the UI. Values override `.env`.
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
          <div key={key} className="rounded-2xl border border-ink-800 bg-ink-900 p-5">
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-bold text-lc-white flex items-center gap-2">
                <KeyRound size={14} className="text-ink-400" />
                {setting.label}
              </label>
              <span
                className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-bold border ${
                  setting.is_set
                    ? "border-ink-600 bg-ink-800 text-lc-white"
                    : "border-lc-red/50 bg-lc-red/10 text-lc-red"
                }`}
              >
                <span className={`h-1.5 w-1.5 rounded-full ${setting.is_set ? "bg-lc-white" : "bg-lc-red"}`} />
                {setting.is_set ? "Configured" : "Not set"}
              </span>
            </div>

            {setting.is_set && setting.value && (
              <p className="text-[11px] text-ink-400 font-mono mb-3 break-all">Current: {setting.value}</p>
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
                className="flex-1 bg-ink-850 border border-ink-700 rounded-lg px-3 py-2.5 text-sm text-lc-white placeholder:text-ink-500 focus:outline-none focus:border-lc-red focus:ring-2 focus:ring-lc-red/20 transition"
              />
              <button
                onClick={() => handleSave(key)}
                disabled={!drafts[key]?.trim() || saving === key}
                className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-lc-red text-lc-white px-4 py-2.5 text-sm font-bold hover:bg-lc-red/90 transition disabled:opacity-50"
              >
                {saving === key ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                {saving === key ? "Saving…" : "Save"}
              </button>
            </div>

            {success === key && (
              <p className="text-[12px] text-lc-white mt-2 inline-flex items-center gap-1">
                <Check size={12} className="text-lc-red" />
                Saved.
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
    </div>
  );
}
