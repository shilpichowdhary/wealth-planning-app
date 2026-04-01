"use client";
import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";

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

  if (loading) return <div className="p-8 text-slate-500">Loading...</div>;
  if (session?.user?.role !== "admin")
    return <div className="p-8 text-red-600">Access denied. Admins only.</div>;

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">API Keys & Settings</h1>
        <p className="text-slate-500 text-sm mt-1">
          Manage API keys used by the system. Keys are stored encrypted and masked for display.
        </p>
      </div>

      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="space-y-4">
        {Object.entries(settings).map(([key, setting]) => (
          <div
            key={key}
            className="bg-white rounded-xl border border-slate-200 p-5"
          >
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-semibold text-slate-800">
                {setting.label}
              </label>
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                  setting.is_set
                    ? "bg-green-100 text-green-700"
                    : "bg-amber-100 text-amber-700"
                }`}
              >
                {setting.is_set ? "Configured" : "Not Set"}
              </span>
            </div>

            {setting.is_set && setting.value && (
              <p className="text-xs text-slate-400 font-mono mb-2">
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
                    : `Paste your ${setting.label}...`
                }
                className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                onClick={() => handleSave(key)}
                disabled={!drafts[key]?.trim() || saving === key}
                className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition disabled:opacity-50"
              >
                {saving === key ? "Saving..." : "Save"}
              </button>
            </div>

            {success === key && (
              <p className="text-xs text-green-600 mt-2">Saved successfully.</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
