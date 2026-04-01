"use client";
import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";

interface Advisor {
  user_id: string;
  name: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
  case_count: number;
}

export default function AdminAdvisorsPage() {
  const { data: session } = useSession();
  const token = session?.accessToken ?? "";
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const [advisors, setAdvisors] = useState<Advisor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // New advisor form
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [creating, setCreating] = useState(false);

  // Password reset result
  const [resetResult, setResetResult] = useState<{ userId: string; password: string } | null>(null);
  const [acting, setActing] = useState<string | null>(null);

  useEffect(() => {
    if (!token || session?.user?.role !== "admin") { setLoading(false); return; }
    loadAdvisors();
  }, [token, session?.user?.role]);

  async function loadAdvisors() {
    setLoading(true);
    try {
      const res = await fetch(`${apiUrl}/admin/advisors`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`Failed to load: ${res.status}`);
      setAdvisors(await res.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load advisors");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setActionError(null);
    try {
      const res = await fetch(`${apiUrl}/admin/advisors`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ name, email }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Failed" }));
        throw new Error(err.detail || "Failed to create advisor");
      }
      const newAdvisor = await res.json();
      setAdvisors((prev) => [newAdvisor, ...prev]);
      setName(""); setEmail(""); setShowForm(false);
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : "Failed to create advisor");
    } finally {
      setCreating(false);
    }
  }

  async function handleToggleActive(advisor: Advisor) {
    setActing(advisor.user_id);
    setActionError(null);
    const action = advisor.is_active ? "deactivate" : "reactivate";
    try {
      const res = await fetch(`${apiUrl}/admin/advisors/${advisor.user_id}/${action}`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`Failed to ${action}`);
      setAdvisors((prev) =>
        prev.map((a) => a.user_id === advisor.user_id ? { ...a, is_active: !a.is_active } : a)
      );
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : `Failed to ${action}`);
    } finally {
      setActing(null);
    }
  }

  async function handleResetPassword(userId: string) {
    if (!confirm("Generate a new random password for this advisor?")) return;
    setActing(userId);
    setActionError(null);
    try {
      const res = await fetch(`${apiUrl}/admin/advisors/${userId}/reset-password`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed to reset password");
      const data = await res.json();
      setResetResult({ userId, password: data.new_password });
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : "Failed to reset password");
    } finally {
      setActing(null);
    }
  }

  if (loading) return <div className="p-8 text-slate-500">Loading...</div>;
  if (session?.user?.role !== "admin")
    return <div className="p-8 text-red-600">Access denied. Admins only.</div>;

  const active = advisors.filter((a) => a.is_active).length;

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Advisor Management</h1>
          <p className="text-slate-500 text-sm mt-1">
            {active} active · {advisors.length - active} inactive · {advisors.length} total
          </p>
        </div>
        <button
          onClick={() => { setShowForm((v) => !v); setActionError(null); }}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition"
        >
          {showForm ? "Cancel" : "+ Add Advisor"}
        </button>
      </div>

      {/* New advisor form */}
      {showForm && (
        <form onSubmit={handleCreate} className="bg-blue-50 border border-blue-200 rounded-xl p-5 mb-6 space-y-3">
          <h2 className="text-sm font-semibold text-slate-800">New Advisor Account</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <input
              required value={name} onChange={(e) => setName(e.target.value)}
              placeholder="Full name"
              className="border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <input
              required type="email" value={email} onChange={(e) => setEmail(e.target.value)}
              placeholder="LC email address"
              className="border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <p className="text-xs text-slate-500">The user will sign in using their LC account (SSO). No password needed.</p>
          <button
            type="submit" disabled={creating}
            className="bg-blue-600 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition disabled:opacity-50"
          >
            {creating ? "Creating..." : "Create Advisor"}
          </button>
        </form>
      )}

      {/* Error */}
      {(error || actionError) && (
        <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
          {error || actionError}
        </div>
      )}

      {/* Password reset result */}
      {resetResult && (
        <div className="mb-4 bg-amber-50 border border-amber-300 rounded-xl p-4">
          <p className="text-sm font-semibold text-amber-800 mb-1">New password generated</p>
          <p className="font-mono text-lg tracking-widest text-amber-900 bg-amber-100 rounded px-3 py-2 inline-block">
            {resetResult.password}
          </p>
          <p className="text-xs text-amber-700 mt-2">Share this securely. It will not be shown again.</p>
          <button onClick={() => setResetResult(null)} className="mt-2 text-xs text-amber-600 underline">Dismiss</button>
        </div>
      )}

      {/* Advisors table */}
      {advisors.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
          <p className="text-slate-500 text-sm">No advisors yet. Add your first advisor above.</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Name</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Email</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Cases</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Status</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Added</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {advisors.map((advisor) => (
                <tr key={advisor.user_id} className={`hover:bg-slate-50 transition ${!advisor.is_active ? "opacity-50" : ""}`}>
                  <td className="px-4 py-3 font-medium text-slate-900">{advisor.name}</td>
                  <td className="px-4 py-3 text-slate-600">{advisor.email}</td>
                  <td className="px-4 py-3 text-slate-600">{advisor.case_count}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                      advisor.is_active ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-500"
                    }`}>
                      {advisor.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-500 text-xs">
                    {new Date(advisor.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2 justify-end">
                      <button
                        onClick={() => handleResetPassword(advisor.user_id)}
                        disabled={acting === advisor.user_id}
                        className="text-xs text-slate-500 hover:text-slate-700 transition disabled:opacity-40"
                      >
                        Reset Password
                      </button>
                      <button
                        onClick={() => handleToggleActive(advisor)}
                        disabled={acting === advisor.user_id}
                        className={`text-xs font-medium transition disabled:opacity-40 ${
                          advisor.is_active
                            ? "text-red-500 hover:text-red-700"
                            : "text-green-600 hover:text-green-800"
                        }`}
                      >
                        {acting === advisor.user_id ? "..." : advisor.is_active ? "Deactivate" : "Reactivate"}
                      </button>
                    </div>
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
