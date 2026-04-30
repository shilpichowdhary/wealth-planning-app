"use client";
import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";
import { AlertTriangle, Check } from "lucide-react";

interface SettingEntry {
  label: string;
  value: string;
  is_set: boolean;
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

  // Editable values per key
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!token || session?.user?.role !== "admin") { setLoading(false); return; }
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
      setTimeout(() => setSuccess(null), 3000);
      await loadSettings();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save setting");
    } finally {
      setSaving(null);
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

      <div className="space-y-4">
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

            <div className="flex gap-2">
              <input
                type="password"
                value={drafts[key] || ""}
                onChange={(e) =>
                  setDrafts((prev) => ({ ...prev, [key]: e.target.value }))
                }
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
    </div>
  );
}
