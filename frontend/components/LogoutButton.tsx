"use client";
import { signOut } from "next-auth/react";

export default function LogoutButton() {
  return (
    <button
      onClick={() => signOut({ callbackUrl: "/login" })}
      className="text-ink-500 hover:text-lc-black text-xs transition"
    >
      Sign Out
    </button>
  );
}
