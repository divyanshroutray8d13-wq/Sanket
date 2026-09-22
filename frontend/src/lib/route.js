// The train's whole path in order, with every forecast stop on it.
// Uses the timetable path when we have one; forecast stops missing from it are added at the end.
// The path ends at the last forecast stop.
export function buildRoute(data, geo) {
  const forecast = new Map(data.stations.map((s) => [s.code, s]))
  const path = [...(geo?.paths?.[data.train_no] ?? [])]
  if (!path.length && data.current?.station_code) path.push(data.current.station_code)
  for (const s of data.stations) if (!path.includes(s.code)) path.push(s.code)

  const all = path
    .map((code) => {
      const g = geo?.stations?.[code]
      if (!g) return null
      const stop = forecast.get(code)
      return { code, lat: g[0], lon: g[1], name: stop?.name ?? g[2], stop }
    })
    .filter(Boolean)
  // Stop the map at the last station we forecast; the rest of the journey isn't part of this forecast
  const lastForecast = all.findLastIndex((p) => p.stop)
  const points = lastForecast >= 0 ? all.slice(0, lastForecast + 1) : all

  // Where the train is. Codes can differ for the same station (MMCT and BCT are both
  // Mumbai Central), so fall back to matching the station's position.
  const cur = data.current?.station_code
  const here = geo?.stations?.[cur]
  let nowIdx = points.findIndex((p) => p.code === cur)
  if (nowIdx < 0 && here) nowIdx = points.findIndex((p) => p.lat === here[0] && p.lon === here[1])
  if (nowIdx >= 0 && data.current.station_name) points[nowIdx].name = data.current.station_name
  const { travelled, ahead } = trackLines(points, Math.max(nowIdx, 0), geo?.tracks)
  return { points, now: nowIdx >= 0 ? points[nowIdx] : null, nowIdx, travelled, ahead }
}

// The line between two stops along the real track, when the map data has it; else straight.
function section(a, b, tracks) {
  const fwd = tracks?.[`${a.code}>${b.code}`]
  if (fwd) return fwd
  const back = tracks?.[`${b.code}>${a.code}`]
  if (back) return [...back].reverse()
  return [[a.lat, a.lon], [b.lat, b.lon]]
}

// Two lines: stops already passed (up to where the train is), and the stretch still to go.
function trackLines(points, cut, tracks) {
  const join = (from, to) => {
    const out = []
    for (let i = from; i < to; i++) {
      const seg = section(points[i], points[i + 1], tracks)
      out.push(...(out.length ? seg.slice(1) : seg))
    }
    return out
  }
  return { travelled: join(0, cut), ahead: join(cut, points.length - 1) }
}
