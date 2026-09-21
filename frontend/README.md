# SANKET dashboard

Frontend for SANKET, the network-aware ETA engine (SIH 2026, PS 26028).

## Run it

```bash
npm install
npm run dev
```

Open http://localhost:5173. It redirects to `/train/12951` and reads `public/mock/12951.json`.
Station boards live at `/station/ST`, `/station/BRC`, `/station/RTM` and `/station/KOTA`.

Mock trains: 12951, 12953, 12925, 12909. Their times are illustrative, not real schedules.

## Switch to the real API (26 Sept)

Create `.env.local` with:

```
VITE_API_URL=http://localhost:8000
```

`src/lib/api.js` will then call `GET /eta/:trainNo` instead of the mock file. The JSON shape is frozen: do not rename fields.

## Structure

```
src/
  App.jsx                routes
  pages/TrainPage.jsx    one train: loads data, handles ?station=CODE
  pages/StationPage.jsx  station board: every corridor train due at a station
  pages/CorridorsPage.jsx  routes covered, with links into boards and trains
  pages/AboutPage.jsx    data sources, method, limits
  components/
    Navbar, StaleBanner, Footer          shared on every page
    TrainHeader                          train name, delay, forecast time
    JourneyPanel > StationRow > ArrivalStrip  the forecast list
    WhyLatePanel                         causes for the selected station
    ApiNote                              one API, three screens
    DelayChip, States                    small building blocks

Design ("Paper and moss", from the Figma explorations): warm off-white
canvas, white cards, soft charcoal ink, one muted moss accent used only
for the most likely arrival and the selected station. Tokens live in
src/index.css. Lateness always shows a number, never colour alone.

Backdrop: components/MapBackdrop.jsx draws an aged-chart background
(paper grain, stains, graticule, rhumb lines) and CompassRose.jsx an
original compass rose. Both are pure SVG, no image files. Move the rose
by changing CX / CY in MapBackdrop.jsx.
  lib/                   api, time maths (midnight-safe), colours,
                         corridor.js (demo trains and board stations)
```

## Preview build

`npm run build:preview` makes one self-contained `dist/index.html` for sharing. Not needed for development.
