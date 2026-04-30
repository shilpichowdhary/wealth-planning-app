"use client";
import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";
import {
  Plus,
  UserPlus,
  KeyRound,
  AlertTriangle,
  Copy,
  Check,
  Send,
  Mail,
  MailWarning,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface Advisor {
  user_id: string;
  name: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
  case_count: number;
}

interface InviteResult {
  advisor: Advisor;
  login_url: string;
  email_sent?: boolean;
  email_error?: string | null;
  purpose?: "invite" | "reset";
}

type FormMode = "invite" | "password";

export default function AdminAdvisorsPage() {
  const { data: session } = useSession();
  const token = session?.accessToken ?? "";
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const [advisors, setAdvisors] = useState<Advisor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // New-advisor form
  const [showForm, setShowForm] = useState(false);
  const [mode, setMode] = useState<FormMode>("invite");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [creating, setCreating] = useState(false);

  // Post-action result shown above the table
  const [inviteResult, setInviteResult] = useState<InviteResult | null>(null);
  const [acting, setActing] = useState<string | null>(null);

  useEffect(() => {
    if (!token || session?.user?.role !== "admin") {
      setLoading(false);
      return;
    }
    loadAdvisors();
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setActionError(null);
    try {
      if (mode === "invite") {
        const res = await fetch(`${apiUrl}/admin/advisors/invite`, {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
          body: JSON.stringify({ name, email }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: "Failed" }));
          throw new Error(err.detail || "Failed to send invite");
        }
        const data: InviteResult = await res.json();
        setAdvisors((prev) => [data.advisor, ...prev]);
        setInviteResult({ ...data, purpose: "invite" });
      } else {
        const res = await fetch(`${apiUrl}/admin/advisors`, {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
          body: JSON.stringify({ name, email, password }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: "Failed" }));
          throw new Error(err.detail || "Failed to create advisor");
        }
        const newAdvisor = await res.json();
        setAdvisors((prev) => [newAdvisor, ...prev]);
      }
      setName("");
      setEmail("");
      setPassword("");
      setShowForm(false);
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setCreating(false);
    }
  }

  async function handleResendInvite(advisor: Advisor) {
    setActing(advisor.user_id);
    setActionError(null);
    try {
      const res = await fetch(`${apiUrl}/admin/advisors/${advisor.user_id}/resend-invite`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Failed" }));
        throw new Error(err.detail || "Failed to resend access email");
      }
      const data = await res.json();
      setInviteResult({ advisor, ...data, purpose: "invite" } as InviteResult);
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : "Failed to resend access email");
    } finally {
      setActing(null);
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
        prev.map((a) => (a.user_id === advisor.user_id ? { ...a, is_active: !a.is_active } : a)),
      );
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : `Failed to ${action}`);
    } finally {
      setActing(null);
    }
  }

  if (loading)
    return <div className="max-w-5xl mx-auto px-8 py-10 text-ink-500 text-sm">Loading…</div>;
  if (session?.user?.role !== "admin")
    return (
      <div className="max-w-5xl mx-auto px-8 py-16 text-ember-500">Access denied. Admins only.</div>
    );

  const active = advisors.filter((a) => a.is_active).length;

  return (
    <div className="max-w-5xl mx-auto w-full px-8 py-10">
      <header className="mb-8 flex items-start justify-between gap-6 animate-fade-in-up">
        <div>
          <p className="text-[11px] uppercase tracking-[0.2em] text-ink-500 font-bold">Administration</p>
          <h1 className="mt-2 font-display text-[38px] leading-[1.05] text-lc-black">
            Advisors<span className="text-lc-red">.</span>
          </h1>
          <p className="mt-2 text-ink-600 text-[15px]">
            {active} active · {advisors.length - active} inactive · {advisors.length} total
          </p>
        </div>
        <button
          onClick={() => {
            setShowForm((v) => !v);
            setActionError(null);
          }}
          className="lc-btn-primary"
        >
          <UserPlus size={16} />
          {showForm ? "Cancel" : "Add advisor"}
        </button>
      </header>

      {/* New-advisor form */}
      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="rounded-2xl border border-ink-200 bg-white p-5 mb-6 space-y-4 animate-fade-in-up"
        >
          {/* Mode toggle */}
          <div className="inline-flex rounded-lg border border-ink-300 overflow-hidden">
            <ModeTab active={mode === "invite"} onClick={() => setMode("invite")} icon={Send} label="Email SSO sign-in" />
            <ModeTab active={mode === "password"} onClick={() => setMode("password")} icon={KeyRound} label="Set password" />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Full name"
              className="bg-ink-50 border border-ink-300 rounded-lg px-3 py-2.5 text-sm text-lc-black placeholder:text-ink-400 focus:outline-none focus:border-lc-red focus:ring-2 focus:ring-lc-red/20 transition"
            />
            <input
              required
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Email address"
              className="bg-ink-50 border border-ink-300 rounded-lg px-3 py-2.5 text-sm text-lc-black placeholder:text-ink-400 focus:outline-none focus:border-lc-red focus:ring-2 focus:ring-lc-red/20 transition"
            />
          </div>

          {mode === "password" && (
            <input
              required
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Initial password (min 12 chars)"
              minLength={12}
              className="w-full bg-ink-50 border border-ink-300 rounded-lg px-3 py-2.5 text-sm text-lc-black placeholder:text-ink-400 focus:outline-none focus:border-lc-red focus:ring-2 focus:ring-lc-red/20 transition"
            />
          )}

          <p className="text-[11px] text-ink-500 leading-relaxed">
            {mode === "invite"
              ? "We'll create the advisor's account and email them a sign-in link. They authenticate via Microsoft SSO (\"Sign in with LC Account\") — no password to set or share."
              : "Use this only if SSO isn't available for the advisor. You'll need to share the password with them securely out-of-band."}
          </p>
          <button
            type="submit"
            disabled={creating}
            className="lc-btn-primary"
          >
            {mode === "invite" ? <Send size={14} /> : <Plus size={14} />}
            {creating ? "Working…" : mode === "invite" ? "Send sign-in email" : "Create advisor"}
          </button>
        </form>
      )}

      {(error || actionError) && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-lc-red bg-lc-red/10 px-4 py-3 text-sm text-lc-red">
          <AlertTriangle size={14} />
          {error || actionError}
        </div>
      )}

      {inviteResult && (
        <InvitePanel result={inviteResult} onDismiss={() => setInviteResult(null)} />
      )}

      {advisors.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-ink-300 bg-white/30 p-12 text-center">
          <p className="text-sm text-ink-600">No advisors yet. Add your first advisor above.</p>
        </div>
      ) : (
        <div className="rounded-2xl border border-ink-200 bg-white overflow-hidden animate-fade-in-up">
          <table className="w-full text-sm">
            <thead className="bg-ink-50 border-b border-ink-200">
              <tr>
                <Th>Name</Th>
                <Th>Email</Th>
                <Th className="text-right">Cases</Th>
                <Th>Status</Th>
                <Th>Added</Th>
                <Th className="text-right">Actions</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-200">
              {advisors.map((advisor) => (
                <tr
                  key={advisor.user_id}
                  className={`hover:bg-ink-50 transition ${!advisor.is_active ? "opacity-60" : ""}`}
                >
                  <td className="px-4 py-3 font-bold text-lc-black">{advisor.name}</td>
                  <td className="px-4 py-3 text-ink-600">{advisor.email}</td>
                  <td className="px-4 py-3 text-ink-600 text-right tabular-nums">{advisor.case_count}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-bold border ${
                        advisor.is_active
                          ? "border-ink-400 bg-ink-100 text-lc-black"
                          : "border-ink-300 bg-ink-50 text-ink-500"
                      }`}
                    >
                      <span
                        className={`h-1.5 w-1.5 rounded-full ${
                          advisor.is_active ? "bg-lc-white" : "bg-ink-500"
                        }`}
                      />
                      {advisor.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-ink-500">
                    {new Date(advisor.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-3 justify-end">
                      <button
                        onClick={() => handleResendInvite(advisor)}
                        disabled={acting === advisor.user_id}
                        className="inline-flex items-center gap-1 text-[12px] text-ink-600 hover:text-lc-red transition disabled:opacity-40"
                        title="Re-email the SSO sign-in link"
                      >
                        <Mail size={12} />
                        Resend sign-in email
                      </button>
                      <button
                        onClick={() => handleToggleActive(advisor)}
                        disabled={acting === advisor.user_id}
                        className={`text-[12px] font-bold transition disabled:opacity-40 ${
                          advisor.is_active ? "text-lc-red hover:text-lc-red/70" : "text-lc-black hover:text-ink-800"
                        }`}
                      >
                        {acting === advisor.user_id
                          ? "…"
                          : advisor.is_active
                          ? "Deactivate"
                          : "Reactivate"}
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

function Th({ children, className = "" }: { children?: React.ReactNode; className?: string }) {
  return (
    <th
      className={`text-left px-4 py-2.5 text-[11px] uppercase tracking-[0.14em] font-bold text-ink-500 ${className}`}
    >
      {children}
    </th>
  );
}

function ModeTab({
  active,
  onClick,
  icon: Icon,
  label,
}: {
  active: boolean
  onClick: () => void
  icon: LucideIcon
  label: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-2 px-3 py-1.5 text-[12px] font-bold border-b-2 transition ${
        active
          ? "border-lc-red text-lc-black"
          : "border-transparent text-ink-500 hover:text-lc-black"
      }`}
    >
      <Icon size={12} />
      {label}
    </button>
  );
}

/**
 * Status panel shown after add-advisor / resend-sign-in.
 * Confirms the SSO sign-in email was sent. If SMTP failed, shows the login URL
 * so the admin can pass it to the advisor manually.
 */
function InvitePanel({
  result,
  onDismiss,
}: {
  result: InviteResult;
  onDismiss: () => void;
}) {
  const advisor = result.advisor;
  const loginUrl = result.login_url;
  const emailSent = result.email_sent === true;
  const emailError = result.email_error ?? null;
  const headline = emailSent
    ? `Sign-in email sent to ${advisor.name}`
    : `Couldn't email ${advisor.name}`;

  return (
    <div className="mb-4 rounded-2xl border border-lc-red/40 bg-lc-red/5 p-5 animate-fade-in-up">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-lc-red font-bold flex items-center gap-2">
            {emailSent ? <Mail size={12} /> : <MailWarning size={12} />}
            {headline}
          </p>
          <p className="mt-1 text-[13px] text-ink-800">
            {advisor.email} · authenticates via Microsoft SSO ("Sign in with LC Account")
          </p>
        </div>
        <button
          onClick={onDismiss}
          className="p-1 rounded-md text-ink-500 hover:text-lc-black hover:bg-ink-100 transition"
          title="Dismiss"
        >
          <X size={14} />
        </button>
      </div>

      {emailSent ? (
        <div className="mt-3 flex items-center gap-2 rounded-lg border border-ink-300 bg-ink-50 px-3 py-2 text-[12px] text-ink-800">
          <Check size={12} className="text-lc-red" />
          Delivered to <span className="text-lc-black">{advisor.email}</span>. They can sign in immediately.
        </div>
      ) : (
        <>
          <div className="mt-3 flex items-start gap-2 rounded-lg border border-amber-400 bg-amber-600 px-3 py-2 text-[12px] text-amber-500">
            <MailWarning size={14} className="mt-0.5 shrink-0" />
            <span>
              Email not sent{emailError ? `: ${emailError}` : ""}. Share the sign-in link below directly with the advisor.
            </span>
          </div>
          <CopyBlock label="Sign-in URL" value={loginUrl} mono />
        </>
      )}
    </div>
  );
}

function CopyBlock({
  label,
  value,
  mono = false,
  multiline = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
  multiline?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const doCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      // clipboard API may be unavailable in insecure contexts; fall through silently
    }
  };

  return (
    <div className="mt-3">
      <div className="flex items-center justify-between mb-1.5">
        <p className="text-[10px] uppercase tracking-[0.16em] text-ink-500 font-bold">{label}</p>
        <button
          onClick={doCopy}
          className="inline-flex items-center gap-1 rounded-md border border-ink-300 bg-white px-2 py-1 text-[11px] font-bold text-ink-800 hover:bg-ink-50 hover:text-lc-black transition"
        >
          {copied ? <Check size={11} className="text-lc-red" /> : <Copy size={11} />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <div
        className={`rounded-lg border border-ink-300 bg-ink-50 px-3 py-2 text-[12px] leading-relaxed text-ink-800 ${
          mono ? "font-mono break-all" : ""
        } ${multiline ? "whitespace-pre-wrap" : "truncate"}`}
      >
        {value}
      </div>
    </div>
  );
}
