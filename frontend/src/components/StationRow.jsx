import { motion } from 'framer-motion'
import ArrivalStrip from './ArrivalStrip'
import DelayChip from './DelayChip'
import { minutesLate } from '../lib/time'

export default function StationRow({ s, scale, index, selected, last, onSelect }) {
  const late = {
    low: minutesLate(s.scheduled, s.eta_low),
    mid: minutesLate(s.scheduled, s.eta_median),
    high: minutesLate(s.scheduled, s.eta_high),
    baseline: minutesLate(s.scheduled, s.baseline_eta),
  }

  return (
    <li className="border-t border-line">
      <button
        type="button"
        onClick={() => onSelect(s.code)}
        aria-pressed={selected}
        aria-label={`${s.name}: due ${s.scheduled}, SANKET expects ${s.eta_low} to ${s.eta_high}, train apps show ${s.baseline_eta}`}
        className="group relative flex w-full items-stretch gap-x-3 rounded-xl pr-3 pl-1 text-left transition-colors hover:bg-paper/60"
      >
        {selected && (
          <motion.span
            layoutId="row-highlight"
            className="absolute inset-0 rounded-xl bg-paper"
            transition={{ type: 'spring', stiffness: 420, damping: 36 }}
          />
        )}

        {/* Track segment and this station's stop */}
        <span className="relative z-[1] w-9 shrink-0" aria-hidden="true">
          <span className={`track absolute left-1/2 w-[17px] -translate-x-1/2 ${last ? 'top-0 h-1/2' : 'inset-y-0'}`} />
          <span
            className={`absolute top-1/2 left-1/2 size-[15px] -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-accent transition-colors ${
              selected ? 'bg-accent' : 'bg-card group-hover:bg-accent-soft'
            }`}
          />
        </span>

        <span className="relative grid min-w-0 flex-1 grid-cols-[minmax(0,1fr)] items-center gap-x-6 gap-y-3 py-5 md:grid-cols-[10rem_minmax(0,1fr)_9.5rem]">
          <span>
            <span className="tight block text-[17px] font-medium leading-tight">{s.name}</span>
            <span className="tnum mt-1 block text-[13px] text-ink-3">{s.code} · due {s.scheduled}</span>
          </span>

          <span>
            <ArrivalStrip {...late} scale={scale} index={index} selected={selected} />
          </span>

          <span className="flex items-center justify-between gap-3 md:block md:text-right">
            <span className="tnum tight block whitespace-nowrap text-[19px] font-medium">
              {s.eta_low}–{s.eta_high}
            </span>
            <span className="md:mt-2 md:block">
              <DelayChip minutes={late.mid} selected={selected} />
            </span>
            <span className="tnum hidden text-[12.5px] text-ink-3 md:mt-1.5 md:block">apps show {s.baseline_eta}</span>
          </span>
        </span>
      </button>
    </li>
  )
}
