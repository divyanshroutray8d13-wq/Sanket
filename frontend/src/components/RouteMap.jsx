import { useEffect, useMemo, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Maximize2 } from 'lucide-react'
import { minutesLate } from '../lib/time'
import { buildRoute } from '../lib/route'

// Base map: OpenStreetMap's own tiles, free with no API key (credit required, shown bottom-right).
// Warmed with a CSS filter in index.css so it sits on the cream page.
// To try another style, set VITE_MAP_TILES (and VITE_MAP_ATTRIBUTION) in frontend/.env.local.
// If tiles can't load, the route still draws on paper.
const TILES = import.meta.env.VITE_MAP_TILES || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
const ATTRIBUTION =
  (import.meta.env.VITE_MAP_ATTRIBUTION ||
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors') +
  ' · stations: datameet (CC0)'

const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim()

// lucide "train-front", inlined because Leaflet markers take an HTML string
const TRAIN_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 3.1V7a4 4 0 0 0 8 0V3.1"/><path d="m9 15-1-1"/><path d="m15 15 1-1"/><path d="M9 19c-2.8 0-5-2.2-5-5v-4a8 8 0 0 1 16 0v4c0 2.8-2.2 5-5 5Z"/><path d="m8 19-2 3"/><path d="m16 19 2 3"/></svg>'

function tipHtml(p) {
  const s = p.stop
  const late = minutesLate(s.scheduled, s.eta_median)
  const lateText = late > 0 ? `+${late} min late` : 'On time'
  return `<strong>${p.name}</strong><br><span class="tnum">Likely ${s.eta_low}–${s.eta_high}</span> · ${lateText}`
}

export default function RouteMap({ data, geo, selected, onSelect }) {
  const box = useRef(null)
  const map = useRef(null)
  const stops = useRef(new Map())
  const bounds = useRef(null)
  const [tilesDown, setTilesDown] = useState(false)
  const pick = useRef(onSelect)
  useEffect(() => {
    pick.current = onSelect
  })
  const route = useMemo(() => buildRoute(data, geo), [data, geo])

  // Build the map once per train
  useEffect(() => {
    if (!box.current || route.points.length < 2) return
    const ink = css('--ink'), ink3 = css('--ink-3'), rail = css('--rail'), card = css('--card')

    const m = L.map(box.current, {
      zoomControl: false,
      zoomSnap: 0.25, // fit the route snugly instead of jumping a whole zoom level
      scrollWheelZoom: false, // don't steal page scrolling; click the map first
      dragging: !L.Browser.mobile, // one finger scrolls the page on phones; pinch still zooms
      attributionControl: true,
    })
    m.attributionControl.setPrefix(false)
    L.control.zoom({ position: 'topleft' }).addTo(m)
    L.tileLayer(TILES, { attribution: ATTRIBUTION, maxZoom: 12, minZoom: 3 })
      .on('tileerror', () => setTilesDown(true))
      .addTo(m)
    m.on('click', () => m.scrollWheelZoom.enable())
    m.on('mouseout', () => m.scrollWheelZoom.disable())

    const { travelled, ahead } = route
    // Already travelled: faint and dashed. Still to go: solid rail line.
    if (travelled.length) L.polyline(travelled, { color: rail, weight: 3, opacity: 0.45, dashArray: '2 7', lineCap: 'round' }).addTo(m)
    L.polyline(ahead, { color: card, weight: 7, opacity: 0.9, lineJoin: 'round' }).addTo(m)
    L.polyline(ahead, { color: ink, weight: 3, opacity: 0.85, lineJoin: 'round' }).addTo(m)

    // Stops without a forecast: small dots, name on hover
    for (const p of route.points) {
      if (p.stop || p === route.now) continue
      L.circleMarker([p.lat, p.lon], { radius: 3, color: ink3, weight: 1.5, fillColor: card, fillOpacity: 1 })
        .bindTooltip(p.name, { direction: 'top', offset: [0, -4], className: 'map-tip' })
        .addTo(m)
    }

    // Forecast stops: bigger, labelled, and clickable (same as picking the row below)
    stops.current = new Map()
    for (const p of route.points) {
      if (!p.stop) continue
      const mk = L.circleMarker([p.lat, p.lon], { radius: 7, weight: 2.5, fillOpacity: 1, bubblingMouseEvents: false })
        .bindTooltip(p.name, { permanent: true, direction: 'right', offset: [9, 0], className: 'map-label' })
        .on('click', () => pick.current(p.code))
        .on('mouseover', function () { this.bindPopup(tipHtml(p), { closeButton: false, className: 'map-pop', offset: [0, -6] }).openPopup() })
        .on('mouseout', function () { this.closePopup() })
        .addTo(m)
      stops.current.set(p.code, mk)
    }

    // The train, where it was last reported
    if (route.now) {
      L.marker([route.now.lat, route.now.lon], {
        icon: L.divIcon({ className: 'train-pin', html: `<span>${TRAIN_SVG}</span>`, iconSize: [34, 34] }),
        keyboard: false,
        zIndexOffset: 1000,
      })
        .bindTooltip(`Last reported near ${route.now.name}`, { direction: 'top', offset: [0, -18], className: 'map-tip' })
        .addTo(m)
    }

    bounds.current = L.latLngBounds([...travelled, ...ahead, ...route.points.map((p) => [p.lat, p.lon])])
    m.fitBounds(bounds.current, { padding: [36, 36] })
    map.current = m
    // The card can change size after first paint (fonts, layout); keep tiles filling it
    const ro = new ResizeObserver(() => m.invalidateSize())
    ro.observe(box.current)
    return () => {
      ro.disconnect()
      m.remove()
      map.current = null
    }
  }, [route])

  // Highlight the selected stop and bring it into view if it's off screen
  useEffect(() => {
    const accent = css('--accent'), card = css('--card'), rail = css('--rail')
    for (const [code, mk] of stops.current) {
      const on = code === selected
      mk.setStyle({ color: on ? accent : rail, fillColor: on ? accent : card, radius: on ? 9 : 7 })
      mk.getTooltip()?.getElement()?.classList.toggle('is-selected', on)
      if (on) {
        mk.bringToFront()
        map.current?.panInside(mk.getLatLng(), { padding: [60, 60] })
      }
    }
  }, [selected, route])

  if (route.points.length < 2) return null

  return (
    <section aria-labelledby="map-title" className="rounded-2xl bg-card p-3 sm:p-4">
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2 px-2 pt-2 pb-4 sm:px-3">
        <div>
          <h2 id="map-title" className="tight text-[18px] font-medium">Where it is now</h2>
          <p className="mt-1 text-[14px] text-ink-2">
            {route.now ? <>Last reported near <span className="font-medium text-ink">{route.now.name}</span>. </> : null}
            Tap a station to see its forecast.
          </p>
        </div>
        <button
          type="button"
          onClick={() => map.current?.flyToBounds(bounds.current, { padding: [36, 36], duration: 0.6 })}
          className="inline-flex items-center gap-1.5 rounded-full bg-paper px-3 py-1.5 text-[13px] text-ink-2 hover:text-ink"
        >
          <Maximize2 size={13} strokeWidth={2} aria-hidden="true" />
          Whole route
        </button>
      </div>

      <div
        ref={box}
        role="region"
        aria-label={`Map of train ${data.train_no}'s route. The station list below has the same information.`}
        className="sanket-map h-[280px] overflow-hidden rounded-xl sm:h-[380px]"
      />

      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 px-2 pt-3 text-[12.5px] text-ink-3 sm:px-3">
        <span className="flex items-center gap-1.5">
          <span className="h-[3px] w-5 rounded-full bg-ink" aria-hidden="true" />Still to go
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-5 border-t-2 border-dotted border-[var(--rail)]" aria-hidden="true" />Already travelled
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-full border-2 border-[var(--rail)] bg-card" aria-hidden="true" />Forecast stop
        </span>
        {tilesDown && <span>Map background unavailable offline; the route is still accurate.</span>}
        <span className="ml-auto hidden sm:inline">Click the map to zoom with the scroll wheel</span>
      </div>
    </section>
  )
}
