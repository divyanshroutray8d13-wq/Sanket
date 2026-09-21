import { motion } from 'framer-motion'

// One station's arrival window on a shared "minutes late" scale.
// Markers label themselves, so no legend is needed:
//   | due    the timetable time
//   ○ apps   what train apps show today
//   bar      the window SANKET expects; the tick inside it is the most likely time
export default function ArrivalStrip({ low, mid, high, baseline, scale, index = 0, selected = false, compact = false }) {
  const pct = (m) => ((m - scale.min) / (scale.max - scale.min)) * 100
  const zero = `${pct(0)}%`
  const left = pct(low)
  const width = pct(high) - pct(low)

  return (
    <div className={`relative ${compact ? 'h-8' : 'h-11'}`} aria-hidden="true">
      <span className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-line" />

      <motion.span
        className={`absolute top-1/2 h-[9px] -translate-y-1/2 rounded-full ${selected ? 'bg-accent-soft' : 'bg-bar-muted'}`}
        initial={{ left: zero, width: 0 }}
        animate={{ left: `${left}%`, width: `${width}%` }}
        transition={{ delay: 0.35 + index * 0.08, duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      />
      <motion.span
        className="absolute top-1/2 h-[18px] w-[3px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent"
        initial={{ left: zero, opacity: 0 }}
        animate={{ left: `${pct(mid)}%`, opacity: 1 }}
        transition={{ delay: 0.35 + index * 0.08, duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      />

      <span className="absolute top-1/2 h-4 w-px -translate-x-1/2 -translate-y-1/2 bg-ink-3" style={{ left: zero }} />
      <span
        className="absolute top-1/2 size-[8px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-ink-3 bg-card"
        style={{ left: `${pct(baseline)}%` }}
      />

      {!compact && (
        <>
          <span className="absolute top-[calc(50%+10px)] -translate-x-1/2 text-[10.5px] text-ink-3" style={{ left: zero }}>
            due
          </span>
          <span
            className="absolute bottom-[calc(50%+9px)] -translate-x-1/2 text-[10.5px] text-ink-3"
            style={{ left: `${pct(baseline)}%` }}
          >
            apps
          </span>
        </>
      )}
    </div>
  )
}
