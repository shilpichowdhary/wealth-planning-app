'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { signOut } from 'next-auth/react'
import {
  LayoutDashboard,
  Plus,
  BookOpenText,
  Upload,
  ClipboardCheck,
  ShieldCheck,
  Settings,
  LogOut,
  type LucideIcon,
} from 'lucide-react'
import { LCLogoMark } from '@/components/brand/LCLogo'

interface SidebarProps {
  role: string
  name: string
  email: string
}

interface NavItem {
  href: string
  label: string
  icon: LucideIcon
  rolesAllowed?: string[]
}

const NAV_ITEMS: { section: string; items: NavItem[] }[] = [
  {
    section: 'Workspace',
    items: [
      { href: '/dashboard', label: 'Cases', icon: LayoutDashboard },
      { href: '/cases/new', label: 'New case', icon: Plus },
    ],
  },
  {
    section: 'Knowledge base',
    items: [
      { href: '/kb/documents', label: 'Documents', icon: BookOpenText, rolesAllowed: ['advisor', 'admin'] },
      { href: '/kb/upload', label: 'Upload', icon: Upload, rolesAllowed: ['advisor', 'admin'] },
      { href: '/kb/review', label: 'Review queue', icon: ClipboardCheck, rolesAllowed: ['advisor', 'admin'] },
    ],
  },
  {
    section: 'Administration',
    items: [
      { href: '/admin/advisors', label: 'Advisors', icon: ShieldCheck, rolesAllowed: ['admin'] },
      { href: '/admin/settings', label: 'Settings', icon: Settings, rolesAllowed: ['admin'] },
    ],
  },
]

export default function Sidebar({ role, name, email }: SidebarProps) {
  const pathname = usePathname()

  return (
    <aside className="hidden md:flex w-64 shrink-0 flex-col bg-ink-900 border-r border-ink-800">
      {/* Brand */}
      <div className="px-5 pt-6 pb-5">
        <Link href="/dashboard" className="flex items-center gap-2.5 group">
          <LCLogoMark size={32} />
          <span className="flex flex-col leading-tight">
            <span className="font-sans text-[11px] uppercase tracking-[0.16em] text-lc-white font-bold">
              Lighthouse <span className="text-lc-red">·</span> Canton
            </span>
            <span className="text-[10px] uppercase tracking-[0.16em] text-ink-400 mt-0.5">Wealth Planning</span>
          </span>
        </Link>
      </div>

      <div className="divider mx-5" />

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-3 py-5 space-y-6">
        {NAV_ITEMS.map((group) => {
          const visible = group.items.filter(
            (it) => !it.rolesAllowed || it.rolesAllowed.includes(role),
          )
          if (visible.length === 0) return null
          return (
            <div key={group.section}>
              <div className="px-3 mb-1.5 text-[10px] uppercase tracking-[0.18em] text-ink-400 font-medium">
                {group.section}
              </div>
              <ul className="space-y-0.5">
                {visible.map((it) => {
                  const active =
                    pathname === it.href ||
                    (it.href !== '/dashboard' && pathname?.startsWith(it.href))
                  const Icon = it.icon
                  return (
                    <li key={it.href}>
                      <Link
                        href={it.href}
                        className={`group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
                          active
                            ? 'bg-ink-800 text-ink-100 shadow-inner-line'
                            : 'text-ink-300 hover:bg-ink-850 hover:text-ink-100'
                        }`}
                      >
                        <Icon
                          size={16}
                          className={active ? 'text-brass-400' : 'text-ink-400 group-hover:text-ink-200'}
                        />
                        <span className="flex-1">{it.label}</span>
                      </Link>
                    </li>
                  )
                })}
              </ul>
            </div>
          )
        })}
      </nav>

      {/* User footer */}
      <div className="border-t border-ink-800 p-3">
        <div className="flex items-center gap-3 rounded-lg px-2 py-2">
          <div className="h-8 w-8 rounded-full bg-ink-800 border border-ink-700 flex items-center justify-center text-xs font-medium text-brass-400">
            {name.slice(0, 1).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm text-ink-100 truncate">{name}</div>
            <div className="text-[11px] text-ink-400 truncate capitalize">{role}</div>
          </div>
          <button
            onClick={() => signOut({ callbackUrl: '/login' })}
            title="Sign out"
            className="p-1.5 rounded-md text-ink-400 hover:text-ink-100 hover:bg-ink-800 transition"
          >
            <LogOut size={15} />
          </button>
        </div>
      </div>
    </aside>
  )
}
