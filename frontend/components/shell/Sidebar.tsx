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
import { AppMark } from '@/components/brand/LCLogo'

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
    <aside className="hidden md:flex w-56 shrink-0 flex-col bg-white border-r border-ink-200">
      {/* Brand — canonical sidebar header.
          AppMark = first letter of the app ("W"); brand-title in serif 14/500. */}
      <div className="flex items-center gap-3 px-[18px] py-[18px] border-b border-ink-200">
        <Link href="/dashboard" className="flex items-center gap-3 min-w-0 flex-1 group">
          <AppMark size={32} letter="W" />
          <span className="flex flex-col min-w-0">
            <span className="font-sans text-[9px] uppercase tracking-[0.16em] text-ink-600 font-semibold leading-none mb-[3px]">
              Lighthouse Canton
            </span>
            <span
              className="font-display text-lc-black"
              style={{
                fontWeight: 500,
                fontSize: 14,
                lineHeight: 1.18,
                letterSpacing: '-0.01em',
              }}
            >
              Wealth Planning
            </span>
          </span>
        </Link>
      </div>

      {/* Nav — canonical: 10/20 padding, 14/500 text, 18px stroke icons,
          2px crimson left border + white-smoke fill on .active. */}
      <nav className="flex-1 overflow-y-auto py-4 space-y-5">
        {NAV_ITEMS.map((group) => {
          const visible = group.items.filter(
            (it) => !it.rolesAllowed || it.rolesAllowed.includes(role),
          )
          if (visible.length === 0) return null
          return (
            <div key={group.section}>
              <div className="px-5 mb-1 text-[10px] uppercase tracking-[0.18em] text-ink-500 font-semibold">
                {group.section}
              </div>
              <ul>
                {visible.map((it) => {
                  const active =
                    pathname === it.href ||
                    (it.href !== '/dashboard' && pathname?.startsWith(it.href))
                  const Icon = it.icon
                  return (
                    <li key={it.href}>
                      <Link
                        href={it.href}
                        className={`group flex items-center gap-3 text-sm font-medium transition-colors border-l-2 ${
                          active
                            ? 'bg-smoke text-lc-black border-lc-red font-semibold'
                            : 'text-ink-600 border-transparent hover:bg-ink-50 hover:text-lc-black'
                        }`}
                        style={{ padding: '10px 20px 10px 18px' }}
                      >
                        <Icon size={18} strokeWidth={1.6} className="shrink-0" />
                        <span className="flex-1 truncate">{it.label}</span>
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
      <div className="border-t border-ink-200 p-3">
        <div className="flex items-center gap-3 rounded-lg px-2 py-2">
          <div className="h-8 w-8 rounded-full bg-ink-100 border border-ink-300 flex items-center justify-center text-xs font-medium text-brass-400">
            {name.slice(0, 1).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm text-ink-900 truncate">{name}</div>
            <div className="text-[11px] text-ink-500 truncate capitalize">{role}</div>
          </div>
          <button
            onClick={() => signOut({ callbackUrl: '/login' })}
            title="Sign out"
            className="p-1.5 rounded-md text-ink-500 hover:text-ink-900 hover:bg-ink-100 transition"
          >
            <LogOut size={15} />
          </button>
        </div>
      </div>
    </aside>
  )
}
