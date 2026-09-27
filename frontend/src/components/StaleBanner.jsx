import { clockOf, dateOf } from '../lib/time'

const STALE_AFTER_MIN = 30

export default function StaleBanner({
  asOf,
  isMock = false,
  isLive = true,
}) {
  if (!asOf) return null

  if (isMock) {
    return (
      <div role="status" className="bg-accent-soft/50">
        <p className="mx-auto max-w-6xl px-6 py-2 text-[13.5px] text-ink">
          Replay mode. This is sample forecast data and does not represent a live train.
        </p>
      </div>
    )
  }

  const ageMin = Math.max(
    0,
    (Date.now() - new Date(asOf).getTime()) / 60000
  )

  if (isLive && ageMin < STALE_AFTER_MIN) {
    return (
      <div role="status" className="bg-accent-soft/30">
        <p className="mx-auto max-w-6xl px-6 py-2 text-[13.5px] text-ink">
          <span className="font-medium text-accent">Live forecast</span>
          {' · '}
          RailRadar position data with SANKET prediction. Updated{' '}
          {clockOf(asOf)}, {dateOf(asOf)}.
        </p>
      </div>
    )
  }

  return (
    <div role="status" className="bg-accent-soft/50">
      <p className="mx-auto max-w-6xl px-6 py-2 text-[13.5px] text-ink">
        <span className="font-medium">Cached forecast</span>
        {' · '}
        Live source is temporarily unavailable or the update is stale.
        Showing the latest available forecast from {clockOf(asOf)},{' '}
        {dateOf(asOf)}.
      </p>
    </div>
  )
}