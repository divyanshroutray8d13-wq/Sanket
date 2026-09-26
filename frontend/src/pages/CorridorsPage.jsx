import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { BOARD_STATIONS, CORRIDOR_TRAINS, HOWRAH_TRAINS, OVERLAP_TRAINS } from '../lib/corridor'

const CORRIDORS = [
  {
    name: 'Delhi to Mumbai',
    status: 'Live',
    summary:
      '38 trains, the corridor SANKET was built on. Runs through Surat, Vadodara, Ratlam and Kota. ' +
      'Most of the evaluation on the Results page is drawn from here.',
    trains: CORRIDOR_TRAINS,
    stations: BOARD_STATIONS,
  },
  {
    name: 'Delhi to Howrah',
    status: 'Live',
    summary:
      '14 trains, added to test whether the model holds on a route it wasn\u2019t built around. ' +
      'Forecasts are live; accuracy on this corridor specifically hasn\u2019t been checked on its own yet.',
    trains: HOWRAH_TRAINS,
  },
  {
    name: 'Mumbai corridor overlap',
    status: 'Live',
    summary:
      '18 trains that share block sections with the Delhi\u2013Mumbai corridor without running its full length. ' +
      'Forecasts are live; like Howrah, not yet checked as its own group.',
    trains: OVERLAP_TRAINS,
  },
]

export default function CorridorsPage() {
  return (
    <main className="mx-auto max-w-6xl px-6 pt-12">
      <h1 className="tighter text-[40px] font-medium leading-tight">Corridors</h1>
      <p className="mt-2 max-w-xl text-[15px] text-ink-2">
        SANKET now forecasts three corridors, all from the same model. Whether accuracy actually holds corridor by
        corridor, rather than just on average across all three, is still an open question &mdash; see the Results page.
      </p>

      <div className="mt-10 grid items-start gap-5 lg:grid-cols-3">
        {CORRIDORS.map((c, i) => (
          <motion.section
            key={c.name}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 * i, duration: 0.4 }}
            className="rounded-2xl bg-card p-6"
          >
            <span
              className={`inline-block rounded-full px-2.5 py-1 text-[12.5px] font-medium ${
                c.status === 'Live' ? 'bg-accent-soft text-accent' : 'bg-paper text-ink-2'
              }`}
            >
              {c.status}
            </span>
            <h2 className="tight mt-3 text-[22px] font-medium leading-tight">{c.name}</h2>
            <p className="mt-2 text-[14.5px] leading-relaxed text-ink-2">{c.summary}</p>

            {c.stations && (
              <>
                <h3 className="mt-6 text-[13px] text-ink-3">Station boards</h3>
                <ul className="mt-2 flex flex-wrap gap-2">
                  {c.stations.map((s) => (
                    <li key={s.code}>
                      <Link
                        to={`/station/${s.code}`}
                        className="inline-block rounded-full bg-paper px-3 py-1.5 text-[13.5px] text-ink-2 hover:text-ink"
                      >
                        {s.name}
                      </Link>
                    </li>
                  ))}
                </ul>
              </>
            )}

            {c.trains && (
              <>
                <h3 className="mt-5 text-[13px] text-ink-3">Trains with a forecast</h3>
                <ul className="tnum mt-2 flex flex-wrap gap-2">
                  {c.trains.map((no) => (
                    <li key={no}>
                      <Link
                        to={`/train/${no}`}
                        className="inline-block rounded-full bg-paper px-3 py-1.5 text-[13.5px] text-ink-2 hover:text-ink"
                      >
                        {no}
                      </Link>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </motion.section>
        ))}
      </div>
    </main>
  )
}
