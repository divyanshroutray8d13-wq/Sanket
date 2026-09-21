import CompassRose from './CompassRose'

// Fixed, decorative old-chart backdrop: aged paper, stains, a faint
// graticule, rhumb lines fanning out from the compass, and the rose itself.
// Pure SVG, no image files. Sits behind everything and ignores the mouse.
const INK = '#5c3f22'

// Where the compass sits, in the 1600 x 1000 artboard
const CX = 1330
const CY = 745

export default function MapBackdrop() {
  const rhumbs = Array.from({ length: 32 }, (_, i) => (i * 360) / 32)

  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 z-0 overflow-hidden" style={{ background: 'var(--parchment)' }}>
      <svg className="absolute inset-0 h-full w-full" viewBox="0 0 1600 1000" preserveAspectRatio="xMidYMid slice">
        <defs>
          {/* broad age stains */}
          <filter id="stains" x="0" y="0" width="100%" height="100%">
            <feTurbulence type="fractalNoise" baseFrequency="0.0032" numOctaves="4" seed="11" />
            <feColorMatrix values="0 0 0 0 0.45  0 0 0 0 0.31  0 0 0 0 0.16  0 0 0 1.9 -0.92" />
          </filter>
          {/* fine paper fibre */}
          <filter id="grain" x="0" y="0" width="100%" height="100%">
            <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed="3" stitchTiles="stitch" />
            <feColorMatrix values="0 0 0 0 0.36  0 0 0 0 0.25  0 0 0 0 0.13  0 0 0 0.75 -0.3" />
          </filter>
          <radialGradient id="vignette" cx="50%" cy="45%" r="75%">
            <stop offset="55%" stopColor={INK} stopOpacity="0" />
            <stop offset="100%" stopColor={INK} stopOpacity="0.28" />
          </radialGradient>
        </defs>

        <rect width="1600" height="1000" filter="url(#stains)" opacity="0.55" />
        <rect width="1600" height="1000" filter="url(#grain)" opacity="0.5" />

        {/* graticule */}
        <g stroke={INK} strokeWidth="0.7" strokeDasharray="2 7" opacity="0.16">
          {Array.from({ length: 17 }, (_, i) => (
            <line key={`v${i}`} x1={i * 100} y1="0" x2={i * 100} y2="1000" />
          ))}
          {Array.from({ length: 11 }, (_, i) => (
            <line key={`h${i}`} x1="0" y1={i * 100} x2="1600" y2={i * 100} />
          ))}
        </g>

        {/* rhumb lines from the rose, like a portolan chart */}
        <g stroke={INK} strokeWidth="0.8" opacity="0.13">
          {rhumbs.map((a) => (
            <line
              key={a}
              x1={CX}
              y1={CY}
              x2={CX + Math.sin((a * Math.PI) / 180) * 2400}
              y2={CY - Math.cos((a * Math.PI) / 180) * 2400}
              strokeDasharray={a % 45 === 0 ? 'none' : '6 5'}
            />
          ))}
        </g>

        <rect width="1600" height="1000" fill="url(#vignette)" />

        <g opacity="0.26" transform={`translate(${CX - 280} ${CY - 280})`}>
          <CompassRose size={560} />
        </g>
      </svg>
    </div>
  )
}
