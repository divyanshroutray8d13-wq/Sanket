import { motion } from 'framer-motion'
import { TrainFront } from 'lucide-react'
import StationRow from './StationRow'
import DelayChip from './DelayChip'
import { minutesLate } from '../lib/time'

// One shared scale for every strip, so windows can be compared down the journey.
function buildScale(stations) {
  const worst = Math.max(
    45,
    ...stations.flatMap((s) => [minutesLate(s.scheduled, s.eta_high), minutesLate(s.scheduled, s.baseline_eta)]),
  )
  const max = Math.ceil((worst + 6) / 15) * 15
  const ticks = []
  for (let t = 30; t < max; t += 30) ticks.push(t)
  return { min: -8, max, ticks }
}

export default function JourneyPanel({ data, selected, onSelect }) {
  const scale = buildScale(data.stations)

  return (
    <section aria-labelledby="journey-title" className="rounded-2xl bg-card px-3 py-6 sm:px-6">
      <div className="px-3">
        <h2 id="journey-title" className="tight text-[18px] font-medium">Arrival forecast</h2>
        <p className="mt-1 text-[14px] text-ink-2">
          Each bar is the window the train will most likely arrive in
        </p>
      </div>

      {/* Where the train is now: top of the track */}
      <div className="mt-5 flex items-stretch gap-x-3 pl-1">
        <span className="relative w-9 shrink-0" aria-hidden="true">
          <span className="track absolute top-1/2 bottom-0 left-1/2 w-[17px] -translate-x-1/2" />
          <motion.span
            className="absolute top-1/2 left-1/2 grid size-9 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-accent text-card shadow-[0_0_0_4px_var(--card)]"
            initial={{ y: -24, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          >
            <TrainFront size={18} strokeWidth={2} />
          </motion.span>
        </span>
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1 py-4 text-[14.5px] text-ink-2">
          <span>
            Last reported near <span className="font-medium text-ink">{data.current.station_name}</span>, running
          </span>
          <DelayChip minutes={data.current.delay_min} selected />
        </p>
      </div>

      <ol>
        {data.stations.map((s, i) => (
          <StationRow
            key={s.code}
            s={s}
            index={i}
            scale={scale}
            selected={s.code === selected}
            last={i === data.stations.length - 1}
            onSelect={onSelect}
          />
        ))}
      </ol>
    </section>
  )
}
