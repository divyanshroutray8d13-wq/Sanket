import { clockOf, dateOf } from '../lib/time'

const STALE_AFTER_MIN = 30

// Sample data always says so. Real data says when live updates have stopped.
export default function StaleBanner({ asOf, isMock = false, isLive = true }) {
  if (!asOf) return null

  let text = null
  if (isMock) {
    text = 'Sample data. These forecasts show how SANKET works and are not live trains.'
  } else {
    const ageMin = (Date.now() - new Date(asOf).getTime()) / 60000
    if (!isLive || ageMin >= STALE_AFTER_MIN) {
      text = `Live updates are paused. Showing the last saved forecast from ${clockOf(asOf)}, ${dateOf(asOf)}.`
    }
  }
  if (!text) return null

  return (
    <div role="status" className="bg-accent-soft/50">
      <p className="mx-auto max-w-6xl px-6 py-2 text-[13.5px] text-ink">{text}</p>
    </div>
  )
}
