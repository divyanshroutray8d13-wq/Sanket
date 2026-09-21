// An original 32-point compass rose in the old chart-maker's style.
// Drawn in code: scales cleanly and needs no image file.
const INK = '#5c3f22'
const PAPER = '#f4e6c8'

// One two-tone point: dark left half, light right half.
function Point({ angle, length, width }) {
  const left = `0,0 ${-width},${-width} 0,${-length}`
  const right = `0,0 ${width},${-width} 0,${-length}`
  return (
    <g transform={`rotate(${angle})`}>
      <polygon points={left} fill={INK} />
      <polygon points={right} fill={PAPER} stroke={INK} strokeWidth="1.4" strokeLinejoin="round" />
    </g>
  )
}

export default function CompassRose({ size = 560, ...props }) {
  const ticks = Array.from({ length: 72 }, (_, i) => i * 5)
  const minor = Array.from({ length: 16 }, (_, i) => 11.25 + i * 22.5)
  const letters = [
    ['N', 0], ['E', 90], ['S', 180], ['W', 270],
  ]

  return (
    <svg viewBox="-330 -330 660 660" width={size} height={size} aria-hidden="true" {...props}>
      {/* rings */}
      <circle r="272" fill="none" stroke={INK} strokeWidth="2.2" />
      <circle r="264" fill="none" stroke={INK} strokeWidth="0.9" />
      <circle r="236" fill="none" stroke={INK} strokeWidth="1.4" />
      <circle r="228" fill="none" stroke={INK} strokeWidth="0.6" strokeDasharray="1.5 5" />
      <circle r="150" fill="none" stroke={INK} strokeWidth="0.7" />

      {/* degree band */}
      {ticks.map((a) => (
        <line
          key={a}
          x1="0" y1={-264} x2="0" y2={a % 15 === 0 ? -246 : -254}
          stroke={INK} strokeWidth={a % 45 === 0 ? 1.8 : 0.9}
          transform={`rotate(${a})`}
        />
      ))}
      {/* alternating chequer on the outer band */}
      {Array.from({ length: 36 }, (_, i) => (
        <path
          key={i}
          d="M0,-272 A272,272 0 0,1 47.2,-267.9 L45.8,-260 A264,264 0 0,0 0,-264 Z"
          fill={i % 2 ? INK : 'none'}
          transform={`rotate(${i * 10})`}
          opacity="0.9"
        />
      ))}

      {/* 16 small points, then 4 half-winds, then 4 cardinals on top */}
      {minor.map((a) => <Point key={a} angle={a} length={118} width={11} />)}
      {[22.5, 67.5, 112.5, 157.5, 202.5, 247.5, 292.5, 337.5].map((a) => (
        <Point key={a} angle={a} length={160} width={17} />
      ))}
      {[45, 135, 225, 315].map((a) => <Point key={a} angle={a} length={196} width={26} />)}
      {[0, 90, 180, 270].map((a) => <Point key={a} angle={a} length={262} width={34} />)}

      <circle r="13" fill={PAPER} stroke={INK} strokeWidth="2" />
      <circle r="4.5" fill={INK} />

      {/* cardinal letters */}
      {letters.map(([l, a]) => (
        <text
          key={l}
          transform={`rotate(${a}) translate(0,-292) rotate(${-a})`}
          textAnchor="middle"
          dominantBaseline="central"
          fontFamily="Georgia, 'Times New Roman', serif"
          fontSize="40"
          fontWeight="700"
          fill={INK}
        >
          {l}
        </text>
      ))}
    </svg>
  )
}
