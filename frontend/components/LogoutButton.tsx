"use client";
import { signOut } from "next-auth/react";

export default function LogoutButton() {
  return (
    <button
      onClick={() => signOut({ callbackUrl: "/login" })}
      className="text-slate-400 hover:text-white text-xs transition"
    >
      Sign Out
    </button>
  );
}
