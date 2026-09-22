import { AnimatePresence, motion } from 'framer-motion'
import { causeGroup } from '../lib/causes'
import { minutesLate } from '../lib/time'

const ease = [0.22, 1, 0.36, 1]

// One cause: label, minutes, and a bar sized against the biggest cause.
function Cause({ a, scale, made }) {
  const g = causeGroup(a.cause, a.minutes)
  const detail = /[A-Z]{2,}/.test(a.cause) ? a.cause : null
  const size = Math.abs(a.minutes)
  return (
    <li>
      <span className="flex items-baseline justify-between gap-4">
        <span className="text-[14.5px]">{g.label}</span>
        <span className={`tnum tight shrink-0 whitespace-nowrap text-[15px] font-medium ${made ? 'text-accent' : ''}`}>
          {made ? `−${size}` : `+${size}`} min
        </span>
      </span>
      {detail && <span className="mt-0.5 block text-[12.5px] text-ink-3">{detail}</span>}
      <motion.span
        aria-hidden="true"
        className={`mt-2 block h-[3px] rounded-full ${made ? 'bg-accent' : 'bg-[var(--rail)]'}`}
        initial={{ width: 0 }}
        animate={{ width: `${(size / scale) * 100}%` }}
        transition={{ duration: 0.45, ease }}
      />
    </li>
  )
}

export default function WhyLatePanel({ station: s }) {
  if (!s) return null
  const late = minutesLate(s.scheduled, s.eta_median)
  const vsBaseline = minutesLate(s.baseline_eta, s.eta_median)
  const chance = Math.round(s.confidence * 10)

  // Positive minutes add delay; negative minutes are time the train made up.
  const added = s.attribution.filter((a) => a.minutes > 0).sort((a, b) => b.minutes - a.minutes)
  const madeUp = s.attribution.filter((a) => a.minutes < 0).sort((a, b) => a.minutes - b.minutes)
  const addedTotal = added.reduce((t, a) => t + a.minutes, 0)
  const madeUpTotal = -madeUp.reduce((t, a) => t + a.minutes, 0)
  const net = addedTotal - madeUpTotal
  const scale = Math.max(1, ...s.attribution.map((a) => Math.abs(a.minutes)))

  return (
    <section aria-labelledby="why-title" aria-live="polite" className="rounded-2xl bg-card p-6">
      <AnimatePresence mode="wait">
        <motion.div key={s.code} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }}>
          <p className="text-[13px] text-ink-3">Why it's late at</p>
          <h2 id="why-title" className="tight mt-1 text-[24px] font-medium leading-tight">{s.name}</h2>

          <p className="mt-4 text-[14.5px] leading-relaxed text-ink-2">
            {chance} in 10 chance it arrives between{' '}
            <span className="tnum font-medium text-ink">{s.eta_low}</span> and{' '}
            <span className="tnum font-medium text-ink">{s.eta_high}</span>. Apps show{' '}
            <span className="tnum text-ink">{s.baseline_eta}</span>
            {vsBaseline > 0 && <>, {vsBaseline} min earlier than SANKET expects</>}.
          </p>

          {added.length > 0 && (
            <>
              <h3 className="mt-6 text-[13px] text-ink-3">Adds delay</h3>
              <ul className="mt-3 space-y-4">
                {added.map((a) => <Cause key={a.cause} a={a} scale={scale} />)}
              </ul>
            </>
          )}

          {madeUp.length > 0 && (
            <>
              <h3 className="mt-6 text-[13px] text-ink-3">Made up on the way</h3>
              <ul className="mt-3 space-y-4">
                {madeUp.map((a) => <Cause key={a.cause} a={a} scale={scale} made />)}
              </ul>
            </>
          )}

          <p className="mt-6 flex items-baseline justify-between gap-4 border-t border-line pt-4 text-[14px] text-ink-2">
            <span>
              {madeUp.length > 0 ? `${addedTotal} lost, ${madeUpTotal} made up` : 'Total'}
            </span>
            <span className="tnum tight shrink-0 whitespace-nowrap text-[15px] font-medium text-ink">
              {net > 0 ? `${net} min late` : net < 0 ? `${-net} min early` : 'On time'}
            </span>
          </p>
          {net !== late && (
            <p className="mt-1 text-[12px] text-ink-3">Causes are rounded, so they may differ slightly from the {late} min forecast.</p>
          )}
        </motion.div>
      </AnimatePresence>
    </section>
  )
}
