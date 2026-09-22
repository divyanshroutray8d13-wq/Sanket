import { useCallback, useEffect, useState } from 'react'
import { Link, NavLink, useParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { fetchStationBoard } from '../lib/api'
import { BOARD_STATIONS, CORRIDOR_TRAINS } from '../lib/corridor'
import { minutesLate, toMin, clockOf } from '../lib/time'
import DelayChip from '../components/DelayChip'
import ArrivalStrip from '../components/ArrivalStrip'
import StaleBanner from '../components/StaleBanner'
import { ErrorState, LoadingState } from '../components/States'

// Minutes from the forecast time until `hhmm`, wrapping past midnight.
const minutesUntil = (asOf, hhmm) => {
  const now = toMin(clockOf(asOf))
  return (toMin(hhmm) - now + 1440) % 1440
}

function StationPicker({ current }) {
  return (
    <nav aria-label="Choose a station" className="flex flex-wrap gap-2">
      {BOARD_STATIONS.map((s) => (
        <NavLink
          key={s.code}
          to={`/station/${s.code}`}
          className={`rounded-full px-3.5 py-1.5 text-[14px] ${
            s.code === current ? 'bg-accent-soft font-medium text-accent' : 'bg-card text-ink-2 hover:text-ink'
          }`}
        >
          {s.name}
        </NavLink>
      ))}
    </nav>
  )
}

export default function StationPage() {
  const { code = '' } = useParams()
  const upper = code.toUpperCase()
  const known = BOARD_STATIONS.find((s) => s.code === upper)
  const [state, setState] = useState({ status: 'loading' })

  const load = useCallback(() => {
    setState({ status: 'loading' })
    fetchStationBoard(upper, CORRIDOR_TRAINS)
      .then((data) => setState({ status: 'ready', data }))
      .catch((error) => setState({ status: 'error', error }))
  }, [upper])

  useEffect(load, [load])

  if (!known) {
    return (
      <main className="mx-auto max-w-6xl px-6 pt-12">
        <div className="max-w-md">
          <h1 className="tight text-[19px] font-medium">No board for {upper}</h1>
          <p className="mt-2 text-[15px] text-ink-2">
            Boards cover stations on the Delhi to Mumbai corridor. Pick one below.
          </p>
          <div className="mt-5 flex justify-center"><StationPicker /></div>
        </div>
      </main>
    )
  }

  if (state.status === 'loading') return <Shell><LoadingState /></Shell>
  if (state.status === 'error') return <Shell><ErrorState error={state.error} onRetry={load} /></Shell>

  const { data } = state
  const rows = [...data.arrivals].sort(
    (a, b) => minutesUntil(data.asOf, a.stop.eta_median) - minutesUntil(data.asOf, b.stop.eta_median),
  )
  const lates = rows.flatMap((r) => [
    minutesLate(r.stop.scheduled, r.stop.eta_high),
    minutesLate(r.stop.scheduled, r.stop.baseline_eta),
  ])
  const max = Math.ceil((Math.max(45, ...lates) + 5) / 15) * 15
  const ticks = []
  for (let t = 15; t < max; t += 15) ticks.push(t)
  const scale = { min: -6, max, ticks }

  return (
    <>
      <StaleBanner asOf={data.asOf} isMock={data.isMock} isLive={data.isLive} />
      <Shell>
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div>
            <p className="text-[14px] text-ink-3">Arrivals at</p>
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} className="mt-2">
              <span className="tighter block text-[34px] font-medium leading-tight">{known.name}</span>
            </motion.div>
          </div>
          <StationPicker current={upper} />
        </div>

        <section aria-labelledby="board-title" className="mt-8 rounded-2xl bg-card px-3 py-6 sm:px-6">
          <div className="flex flex-wrap items-baseline justify-between gap-2 px-3 pb-2">
            <h1 id="board-title" className="tight text-[19px] font-medium">
              {rows.length} {rows.length === 1 ? 'train' : 'trains'} due
            </h1>
            <p className="tnum text-[13px] text-ink-3">Forecast made {clockOf(data.asOf)}, ordered by likely arrival</p>
          </div>

          <div className="hidden grid-cols-[13rem_5rem_minmax(0,1fr)_9.5rem] gap-x-8 px-3 pt-3 text-[11.5px] text-ink-3 md:grid" aria-hidden="true">
            <span>Train</span><span>Due</span><span>How late</span><span className="text-right">SANKET window</span>
          </div>

          <ol>
            {rows.map(({ train, stop }, i) => (
              <li key={train.train_no} className="border-t border-line">
                <Link
                  to={`/train/${train.train_no}?station=${upper}`}
                  className="group grid grid-cols-[minmax(0,1fr)] items-center gap-x-8 gap-y-3 rounded-xl px-3 py-5 transition-colors hover:bg-paper/60 md:grid-cols-[13rem_5rem_minmax(0,1fr)_9.5rem]"
                >
                  <span className="min-w-0">
                    <span className="tnum text-[13px] text-ink-3">{train.train_no}</span>
                    <span className="tight block truncate text-[17px] font-medium" title={train.train_name}>{train.train_name}</span>
                  </span>
                  <span className="tnum text-right text-[15px] text-ink-2 md:text-left">
                    <span className="text-[12px] text-ink-3 md:hidden">Scheduled </span>{stop.scheduled}
                  </span>
                  <span className="col-span-2 md:col-span-1">
                    <ArrivalStrip
                      low={minutesLate(stop.scheduled, stop.eta_low)}
                      mid={minutesLate(stop.scheduled, stop.eta_median)}
                      high={minutesLate(stop.scheduled, stop.eta_high)}
                      baseline={minutesLate(stop.scheduled, stop.baseline_eta)}
                      scale={scale}
                      index={i}
                      compact
                    />
                  </span>
                  <span className="col-span-2 flex items-center justify-between gap-3 md:col-span-1 md:block md:text-right">
                    <span className="tnum tight block whitespace-nowrap text-[19px] font-medium">
                      {stop.eta_low}–{stop.eta_high}
                    </span>
                    <span className="flex flex-wrap items-center justify-end gap-x-3 gap-y-1 md:mt-1 md:flex-col md:items-end">
                      <span className="tnum text-[13px] whitespace-nowrap text-ink-3">Apps show {stop.baseline_eta}</span>
                      <DelayChip minutes={minutesLate(stop.scheduled, stop.eta_median)} />
                    </span>
                  </span>
                  
                </Link>
              </li>
            ))}
          </ol>
          {rows.length === 0 && (
            <p className="px-6 py-10 text-center text-[15px] text-ink-2">No corridor trains are due here in this forecast.</p>
          )}
        </section>

        <p className="mt-5 px-1 text-[13px] text-ink-3">
          Open a train to see why it's late. On real station displays, this same data is sent as one time per train.
        </p>
      </Shell>
    </>
  )
}

function Shell({ children }) {
  return <main className="mx-auto max-w-6xl px-6 pt-12">{children}</main>
}
