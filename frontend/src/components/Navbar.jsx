import { useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'

const LINKS = [
  { to: '/train/12951', label: 'Train', match: '/train' },
  { to: '/station/ST', label: 'Stations', match: '/station' },
  { to: '/corridors', label: 'Corridors', match: '/corridors' },
  { to: '/results', label: 'Results', match: '/results' },
  { to: '/about', label: 'About', match: '/about' },
]

export default function Navbar() {
  const [q, setQ] = useState('')
  const navigate = useNavigate()
  const { pathname } = useLocation()

  const go = (e) => {
    e.preventDefault()
    if (/^\d{4,5}$/.test(q.trim())) {
      navigate(`/train/${q.trim()}`)
      setQ('')
    }
  }

  return (
    <header>
      <nav className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-10 gap-y-3 px-6 py-5">
        <NavLink
          to="/train/12951"
          className="tight flex items-center gap-2 text-[17px] font-semibold"
          aria-label="SANKET home"
        >
          <img
            src="/sanket-logo.webp"
            alt="SANKET logo"
            className="h-20 w-20 object-contain"
          />
          <span>SANKET</span>
        </NavLink>

        <ul className="order-3 flex gap-6 sm:order-none">
          {LINKS.map((l) => {
            const active = pathname.startsWith(l.match)
            return (
              <li key={l.to}>
                <NavLink
                  to={l.to}
                  aria-current={active ? 'page' : undefined}
                  className={`text-[15px] ${active ? 'font-medium text-ink' : 'text-ink-3 hover:text-ink-2'}`}
                >
                  {l.label}
                </NavLink>
              </li>
            )
          })}
        </ul>

        <form onSubmit={go} className="ml-auto" role="search">
          <label htmlFor="train-search" className="sr-only">Train number</label>
          <input
            id="train-search"
            value={q}
            onChange={(e) => setQ(e.target.value.replace(/\D/g, '').slice(0, 5))}
            inputMode="numeric"
            placeholder="Train number"
            className="tnum w-36 rounded-full bg-card px-3.5 py-1.5 text-[14px] text-ink placeholder:text-ink-3 focus:outline-none"
          />
        </form>
      </nav>
    </header>
  )
}
