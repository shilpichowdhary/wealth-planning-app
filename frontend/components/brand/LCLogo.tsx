// Lighthouse Canton brand marks.
//
// LC contract:
//   - The sidebar brand-mark is the FIRST LETTER OF THE APP (W for Wealth
//     Planning), not "L" or "LC". This differentiates apps at a glance.
//   - The firm "L" mark only appears on the login + invite editorial
//     surfaces, paired with "Lighthouse Canton" as the firm logo.
//
// AppMark    — sidebar / favicon glyph; serif single letter on crimson.
// LCFirmMark — login/invite firm logo; serif "L" on crimson.
// LCWordmark — "LIGHTHOUSE CANTON" wordmark in Public Sans Bold.

interface MarkProps {
  size?: number
  className?: string
  letter?: string
}

// Sidebar / favicon mark — square crimson tile, white serif glyph.
// Default letter is "W" (Wealth Planning); pass `letter` to override.
export function AppMark({ size = 32, letter = 'W', className = '' }: MarkProps) {
  return (
    <span
      role="img"
      aria-label={`${letter} — Wealth Planning`}
      className={`inline-flex items-center justify-center ${className}`}
      style={{ background: '#E50025', width: size, height: size }}
    >
      <span
        style={{
          color: '#FFFFFF',
          fontFamily: 'var(--font-display)',
          fontWeight: 500,
          fontSize: Math.round(size * 0.62),
          letterSpacing: '-0.02em',
          lineHeight: 1,
        }}
      >
        {letter}
      </span>
    </span>
  )
}

// Firm "L" mark — only for login + invite editorial column.
export function LCFirmMark({ size = 44, className = '' }: { size?: number; className?: string }) {
  return (
    <span
      role="img"
      aria-label="Lighthouse Canton"
      className={`inline-flex items-center justify-center ${className}`}
      style={{ background: '#E50025', width: size, height: size }}
    >
      <span
        style={{
          color: '#FFFFFF',
          fontFamily: 'var(--font-display)',
          fontWeight: 500,
          fontSize: Math.round(size * 0.55),
          letterSpacing: '-0.02em',
          lineHeight: 1,
        }}
      >
        L
      </span>
    </span>
  )
}

// Backwards-compat shim — older imports still resolve. Defaults to the
// firm mark since that's what the existing call sites (login/invite) need.
export function LCLogoMark({ size = 44, className = '' }: { size?: number; className?: string }) {
  return <LCFirmMark size={size} className={className} />
}

export function LCWordmark({ className = '' }: { className?: string }) {
  return (
    <span
      className={`font-sans ${className}`}
      style={{
        fontWeight: 700,
        letterSpacing: '0.16em',
        fontSize: 12,
        textTransform: 'uppercase',
      }}
    >
      Lighthouse <span style={{ color: '#E50025' }}>·</span> Canton
    </span>
  )
}
