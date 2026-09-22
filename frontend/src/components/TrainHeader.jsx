import { motion } from 'framer-motion'
import DelayChip from './DelayChip'
import { clockOf, dateOf } from '../lib/time'

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
        <p className="flex items-center gap-2 text-[13px] text-ink-3">
          <span className="tnum">Train {data.train_no}</span>
          {data.is_mock && (
            <span className="rounded-full bg-bar-muted px-2 py-0.5 text-[11.5px] font-medium text-ink-2">Sample data</span>
          )}
        </p>
        <h1 className="tighter mt-1 text-[40px] font-medium leading-[1.05] sm:text-[46px]">{data.train_name}</h1>
        {last && (
          <p className="mt-2 text-[15px] text-ink-2">Forecast runs to {last.name}, due {last.scheduled}</p>
        )}
      </div>

      <dl className="flex gap-10 sm:gap-12">
        <div>
          <dt className="text-[13px] text-ink-3">Running</dt>
          <dd className="mt-2"><DelayChip minutes={data.current.delay_min} selected big /></dd>
        </div>
        <div>
          <dt className="text-[13px] text-ink-3">Forecast made</dt>
          <dd className="tnum tight mt-2 text-[22px] font-medium leading-none">
            {clockOf(data.as_of)} <span className="text-[14px] font-normal text-ink-3">{dateOf(data.as_of)}</span>
          </dd>
        </div>
      </dl>
    </motion.section>
  )
}
