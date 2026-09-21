import { AnimatePresence, motion } from 'framer-motion'
import { causeGroup } from '../lib/causes'
import { minutesLate } from '../lib/time'

export default function WhyLatePanel({ station: s }) {
  if (!s) return null
  const late = minutesLate(s.scheduled, s.eta_median)
  const vsBaseline = minutesLate(s.baseline_eta, s.eta_median)
  const total = s.attribution.reduce((sum, a) => sum + a.minutes, 0) || 1
  const causes = [...s.attribution].sort((a, b) => b.minutes - a.minutes)
  const chance = Math.round(s.confidence * 10)

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

          <h3 className="mt-6 text-[13px] text-ink-3">Where the {total} minutes come from</h3>
          <ul className="mt-3 space-y-4">
            {causes.map((a) => {
              const g = causeGroup(a.cause)
              const detail = /[A-Z]{2,}/.test(a.cause) ? a.cause : null
              return (
                <li key={a.cause}>
                  <span className="flex items-baseline justify-between gap-4">
                    <span className="text-[14.5px]">{g.label}</span>
                    <span className="tnum tight text-[15px] font-medium">{a.minutes} min</span>
                  </span>
                  {detail && <span className="mt-0.5 block text-[12.5px] text-ink-3">{detail}</span>}
                  <motion.span
                    aria-hidden="true"
                    className="mt-2 block h-[3px] rounded-full bg-accent-soft"
                    initial={{ width: 0 }}
                    animate={{ width: `${(a.minutes / total) * 100}%` }}
                    transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
                  />
                </li>
              )
            })}
          </ul>
        </motion.div>
      </AnimatePresence>
    </section>
  )
}
