// One place that knows where forecasts come from.
// Today: the mock file. On 26 Sept: set VITE_API_URL and it calls the real API.
const API_URL = import.meta.env.VITE_API_URL

export async function fetchTrain(trainNo) {
  // Preview build only: mock JSON is embedded in the page.
  if (import.meta.env.VITE_INLINE_MOCK) {
    const data = window.__SANKET_MOCK__?.[trainNo]
    if (!data) throw new NotFoundError(trainNo)
    return data
  }

  const url = API_URL ? `${API_URL}/eta/${trainNo}` : `/mock/${trainNo}.json`
  const res = await fetch(url)
  if (res.status === 404) throw new NotFoundError(trainNo)
  if (!res.ok) throw new Error(`Forecast request failed (${res.status})`)
  const type = res.headers.get('content-type') ?? ''
  // Vite dev server returns index.html for missing files
  if (!type.includes('json')) throw new NotFoundError(trainNo)
  return res.json()
}

export class NotFoundError extends Error {
  constructor(trainNo) {
    super(`No forecast for train ${trainNo}`)
    this.name = 'NotFoundError'
  }
}

// Station board: every corridor train due at `code`.
// Built from the per-train forecasts, so the frozen contract is unchanged.
// When the API gets a batch endpoint, only this function needs to change.
export async function fetchStationBoard(code, trainNos) {
  const results = await Promise.allSettled(trainNos.map((no) => fetchTrain(no)))
  const trains = results.filter((r) => r.status === 'fulfilled').map((r) => r.value)
  if (trains.length === 0) throw new Error('No train forecasts could be loaded')

  const arrivals = trains.flatMap((t) => {
    const s = t.stations.find((x) => x.code === code)
    return s ? [{ train: t, stop: s }] : []
  })
  const asOf = trains.map((t) => t.as_of).sort().at(-1)
  return { code, asOf, arrivals }
}
