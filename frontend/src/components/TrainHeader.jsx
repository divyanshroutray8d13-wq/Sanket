import { motion } from 'framer-motion'
import DelayChip from './DelayChip'
import { clockOf, dateOf } from '../lib/time'

function StatusBadge({ data }) {
  const ageMin = data.as_of
    ? (Date.now() - new Date(data.as_of).getTime()) / 60000
    : Infinity

  if (data.is_mock) {
    return (
      <span className="rounded-full bg-bar-muted px-2.5 py-1 text-[11.5px] font-medium text-ink-2">
        REPLAY · SAMPLE
      </span>
    )
  }

  if (data.is_live && ageMin < 30) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-accent-soft px-2.5 py-1 text-[11.5px] font-medium text-accent">
        <span className="live-dot h-1.5 w-1.5 rounded-full bg-accent" aria-hidden="true" />
        LIVE
      </span>
    )
  }

  return (
    <span className="rounded-full bg-accent-soft/60 px-2.5 py-1 text-[11.5px] font-medium text-ink-2">
      CACHED
    </span>
  )
}

export default function TrainHeader({ data }) {
  const last = data.stations.at(-1)

  return (
    <motion.section
      aria-label="Train summary"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.35 }}
      className="grid gap-x-12 gap-y-6 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end"
    >
      <div>
        <div className="flex flex-wrap items-center gap-2 text-[13px] text-ink-3">
          <span className="tnum">Train {data.train_no}</span>
          <StatusBadge data={data} />
        </div>

        <h1 className="tighter mt-1 text-[40px] font-medium leading-[1.05] sm:text-[46px]">
          {data.train_name}
        </h1>

        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[15px] text-ink-2">
          {last && (
            <span>
              Forecast runs to {last.name}, due {last.scheduled}
            </span>
          )}

          {data.corridor && (
            <>
              <span className="text-ink-3" aria-hidden="true">·</span>
              <span>
                {data.corridor === 'delhi-mumbai'
                  ? 'Delhi → Mumbai Corridor'
                  : data.corridor}
              </span>
            </>
          )}
        </div>
      </div>

      <dl className="flex gap-10 sm:gap-12">
        <div>
          <dt className="text-[13px] text-ink-3">Running</dt>
          <dd className="mt-2">
            <DelayChip minutes={data.current.delay_min} selected big />
          </dd>
        </div>

        <div>
          <dt className="text-[13px] text-ink-3">
            {data.is_live ? 'Updated' : 'Forecast made'}
          </dt>

          <dd className="tnum tight mt-2 text-[22px] font-medium leading-none">
            {clockOf(data.as_of)}
            <span className="text-[14px] font-normal text-ink-3">
              {' '}{dateOf(data.as_of)}
            </span>
          </dd>
        </div>
      </dl>
    </motion.section>
  )
}