// Railway-signal colours for lateness. Always shown next to a number.
export function severity(minLate) {
  if (minLate <= 5) return { key: 'green', label: 'On time', color: 'var(--sig-green)' }
  if (minLate <= 30) return { key: 'amber', label: 'Late', color: 'var(--sig-amber)' }
  return { key: 'red', label: 'Very late', color: 'var(--sig-red)' }
}
