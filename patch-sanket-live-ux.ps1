$ErrorActionPreference = "Stop"

function Write-Utf8NoBom($path, $content) {
    [System.IO.File]::WriteAllText(
        $path,
        $content,
        [System.Text.UTF8Encoding]::new($false)
    )
}

# TrainHeader.jsx
Write-Utf8NoBom ".\frontend\src\components\TrainHeader.jsx" @"
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
        <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden="true" />
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
"@

# StaleBanner.jsx
Write-Utf8NoBom ".\frontend\src\components\StaleBanner.jsx" @"
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
"@

# States.jsx
Write-Utf8NoBom ".\frontend\src\components\States.jsx" @"
import { Link } from 'react-router-dom'

export function LoadingState() {
  const bar = 'animate-pulse rounded-lg bg-card'

  return (
    <div role="status" aria-label="Loading forecast" className="space-y-10">
      <div className="space-y-3">
        <div className={`${bar} h-12 w-72`} />
        <div className={`${bar} h-5 w-60`} />
      </div>

      <div className="space-y-4 rounded-2xl bg-card p-6">
        {Array.from(
          { length: 5 },
          (_, i) => <div key={i} className={`${bar} h-14`} />
        )}
      </div>
    </div>
  )
}

export function ErrorState({ error, trainNo, onRetry }) {
  const notFound = error?.name === 'NotFoundError'

  const liveUnavailable =
    /502|live source|temporarily unavailable/i.test(
      error?.message ?? ''
    )

  return (
    <div className="max-w-md">
      <div className="mb-3 inline-flex rounded-full bg-accent-soft px-2.5 py-1 text-[11.5px] font-medium text-ink-2">
        {liveUnavailable
          ? 'LIVE SOURCE UNAVAILABLE'
          : notFound
            ? 'NOT FOUND'
            : 'SERVICE ERROR'}
      </div>

      <h1 className="tight text-[26px] font-medium">
        {notFound
          ? `No forecast for train ${trainNo}`
          : liveUnavailable
            ? 'Live forecast could not be refreshed'
            : 'Forecast could not load'}
      </h1>

      <p className="mt-2 text-[15px] text-ink-2">
        {notFound
          ? 'SANKET covers trains on the Delhi to Mumbai corridor for now.'
          : liveUnavailable
            ? 'The live source did not respond. Retry to request the latest forecast; replay data remains available when configured.'
            : 'The forecast service did not respond. Check your connection and try again.'}
      </p>

      <div className="mt-5 flex flex-wrap gap-2">
        {notFound ? (
          <Link
            to="/train/12951"
            className="rounded-full bg-card px-4 py-2 text-[15px] font-medium"
          >
            Open train 12951
          </Link>
        ) : (
          <button
            onClick={onRetry}
            className="rounded-full bg-card px-4 py-2 text-[15px] font-medium"
          >
            Try again
          </button>
        )}
      </div>
    </div>
  )
}
"@

# StationPage.jsx - targeted additions only
$stationPath = ".\frontend\src\pages\StationPage.jsx"
$station = Get-Content $stationPath -Raw

$old = @"
          <div>
            <p className="text-[14px] text-ink-3">Arrivals at</p>
"@

$new = @"
          <div>
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <p className="text-[14px] text-ink-3">Arrivals at</p>
              <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${
                data.isMock
                  ? 'bg-bar-muted text-ink-2'
                  : data.isLive
                    ? 'bg-accent-soft text-accent'
                    : 'bg-accent-soft/60 text-ink-2'
              }`}>
                {data.isMock ? 'REPLAY' : data.isLive ? 'LIVE BOARD' : 'CACHED BOARD'}
              </span>
            </div>
"@

if (-not $station.Contains($old)) {
    throw "StationPage first anchor not found"
}

$station = $station.Replace($old, $new)

$old2 = @"
            <p className="tnum text-[13px] text-ink-3">Forecast made {clockOf(data.asOf)}, ordered by likely arrival</p>
"@

$new2 = @"
            <p className="tnum text-[13px] text-ink-3">
              {data.isLive ? 'Live forecast' : data.isMock ? 'Replay forecast' : 'Cached forecast'}
              {' · '}made {clockOf(data.asOf)}, ordered by likely arrival
            </p>
"@

if (-not $station.Contains($old2)) {
    throw "StationPage second anchor not found"
}

$station = $station.Replace($old2, $new2)

Write-Utf8NoBom $stationPath $station

# CorridorsPage.jsx
$corridorPath = ".\frontend\src\pages\CorridorsPage.jsx"
$corridor = Get-Content $corridorPath -Raw

$corridor = $corridor.Replace(
"The first corridor SANKET forecasts. Trains run through Surat, Vadodara, Ratlam andKota.",
"The first corridor currently wired to the live SANKET forecast. Supported trains run between Delhi and Mumbai via Kota, Ratlam, Vadodara and Surat."
)

$corridor = $corridor.Replace(
"A second long-distance corridor, used to test whether the model holds on a route ithas never seen.",
"A future expansion corridor. It is listed here for the product roadmap and is not currently wired to the live endpoint."
)

Write-Utf8NoBom $corridorPath $corridor

Write-Host ""
Write-Host "SANKET frontend live/replay UX patched successfully." -ForegroundColor Green
Write-Host "Map files were NOT touched." -ForegroundColor Cyan
