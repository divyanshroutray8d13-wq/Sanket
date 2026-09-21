import { clockOf, dateOf } from '../lib/time'

const STALE_AFTER_MIN = 30

export default function StaleBanner({ asOf }) {
  if (!asOf) return null
  const ageMin = (Date.now() - new Date(asOf).getTime()) / 60000
  if (ageMin < STALE_AFTER_MIN) return null

  return (
    <div role="status" className="bg-accent-soft/50">
      <p className="mx-auto max-w-6xl px-6 py-2 text-[13.5px] text-ink">
        Live updates are paused. Showing the last saved forecast from {clockOf(asOf)}, {dateOf(asOf)}.
      </p>
    </div>
  )
}
