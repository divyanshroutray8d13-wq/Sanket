// "HH:MM" -> minutes after midnight
export const toMin = (hhmm) => {
  const [h, m] = hhmm.split(':').map(Number)
  return h * 60 + m
}

// Minutes late of time `t` against scheduled `sched`, safe across midnight.
// e.g. sched 23:50, t 00:10 -> +20 (not -1420)
export const minutesLate = (sched, t) => {
  let d = toMin(t) - toMin(sched)
  if (d < -720) d += 1440
  if (d > 720) d -= 1440
  return d
}

export const signed = (n) => (n > 0 ? `+${n}` : n < 0 ? `−${Math.abs(n)}` : '0')

export const clockOf = (iso) =>
  new Date(iso).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Kolkata' })

export const dateOf = (iso) =>
  new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', timeZone: 'Asia/Kolkata' })
