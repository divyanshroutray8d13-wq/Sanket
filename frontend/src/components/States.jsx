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
        {Array.from({ length: 5 }, (_, i) => <div key={i} className={`${bar} h-14`} />)}
      </div>
    </div>
  )
}

export function ErrorState({ error, trainNo, onRetry }) {
  const notFound = error?.name === 'NotFoundError'
  return (
    <div className="max-w-md">
      <h1 className="tight text-[26px] font-medium">
        {notFound ? `No forecast for train ${trainNo}` : 'Forecast could not load'}
      </h1>
      <p className="mt-2 text-[15px] text-ink-2">
        {notFound
          ? 'SANKET covers trains on the Delhi to Mumbai corridor for now.'
          : 'The forecast service did not respond. Check your connection and try again.'}
      </p>
      <div className="mt-5">
        {notFound ? (
          <Link to="/train/12951" className="rounded-full bg-card px-4 py-2 text-[15px] font-medium">Open train 12951</Link>
        ) : (
          <button onClick={onRetry} className="rounded-full bg-card px-4 py-2 text-[15px] font-medium">Try again</button>
        )}
      </div>
    </div>
  )
}
