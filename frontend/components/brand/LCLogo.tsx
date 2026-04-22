// Lighthouse Canton brand marks.
// - LCLogoMark: the monogram square (LC), red on black/white or reversed.
//   Per guideline, the monogram is only for favicons/social avatars — and
//   small UI chrome counts as "avatar-scale" for our purposes.
// - LCWordmark: "LIGHTHOUSE CANTON" text wordmark in Public Sans Bold.

interface MarkProps {
  size?: number
  variant?: 'red-on-white' | 'white-on-red' | 'white-on-black' | 'black-on-white'
  className?: string
}

const PALETTE = {
  'red-on-white': { bg: '#FFFFFF', fg: '#E50025' },
  'white-on-red': { bg: '#E50025', fg: '#FFFFFF' },
  'white-on-black': { bg: '#000000', fg: '#FFFFFF' },
  'black-on-white': { bg: '#FFFFFF', fg: '#000000' },
} as const

export function LCLogoMark({ size = 32, variant = 'white-on-red', className = '' }: MarkProps) {
  const p = PALETTE[variant]
  return (
    <span
      role="img"
      aria-label="Lighthouse Canton"
      className={`inline-flex items-center justify-center rounded-md ${className}`}
      style={{ background: p.bg, width: size, height: size }}
    >
      <span
        className="font-sans"
        style={{
          color: p.fg,
          fontSize: size * 0.42,
          fontWeight: 700,
          letterSpacing: '-0.03em',
          lineHeight: 1,
        }}
      >
        LC
      </span>
    </span>
  )
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
