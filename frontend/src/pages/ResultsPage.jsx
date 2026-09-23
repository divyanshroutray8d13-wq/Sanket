import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { fetchResults } from '../lib/api'
import { LoadingState } from '../components/States'

const ease = [0.22, 1, 0.36, 1]

// Small gaps need two decimals: rounding 0.05 to "0.1" overstates it. One row, one number of
// decimals, and always a real minus sign.
const decimalsFor = (c) => (Math.max(Math.abs(c.gain), Math.abs(c.lo), Math.abs(c.hi)) < 1 ? 2 : 1)
const mins = (v, d) => `${v < 0 ? '−' : ''}${Math.abs(v).toFixed(d)}`

// "2026-09-21" -> "21 Sep 2026"
const dayOf = (iso) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
const TARGET = 0.8

// Baselines are neutral, SANKET models carry the accent. Two roles, one legend.
const barColor = (role) => (role === 'baseline' ? 'bg-[var(--rail)]' : 'bg-accent')

function Legend() {
  return (
    <p className="flex flex-wrap gap-x-5 gap-y-1 text-[12.5px] text-ink-3">
      <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-[var(--rail)]" />Baseline</span>
      <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-accent" />SANKET model</span>
    </p>
  )
}

function Card({ title, note, children }) {
  return (
    <section className="rounded-2xl bg-card p-6">
      <h2 className="tight text-[18px] font-medium">{title}</h2>
      {note && <p className="mt-1 text-[14px] text-ink-2">{note}</p>}
      <div className="mt-5">{children}</div>
    </section>
  )
}

// One row per idea: where an experiment has a tuned twin, they share an error, so show it once.
function byIdea(experiments) {
  const names = new Set(experiments.map((e) => e.experiment))
  return experiments
    .filter((e) => !names.has(`${e.experiment}_cal`))
    .map((e) => (names.has(idea(e.experiment)) ? { ...e, label: labelOf(experiments, idea(e.experiment)) } : e))
}
const labelOf = (experiments, name) => experiments.find((e) => e.experiment === name)?.label ?? name

// Average error: one bar per experiment, best on top.
function ErrorBars({ experiments }) {
  const top = Math.max(...experiments.map((e) => e.mae))
  return (
    <ul className="space-y-4">
      {experiments.map((e, i) => (
        <li key={e.experiment} title={`${e.label}: ${e.mae.toFixed(1)} min average error`}>
          <span className="flex items-baseline justify-between gap-3 text-[14.5px]">
            <span>{e.label}</span>
            <span className="tnum shrink-0 font-medium">{e.mae.toFixed(1)} min</span>
          </span>
          <span className="mt-1.5 block h-2.5 rounded-r-full bg-line/60">
            <motion.span
              className={`block h-full rounded-r-full ${barColor(e.role)}`}
              initial={{ width: 0 }}
              animate={{ width: `${(e.mae / top) * 100}%` }}
              transition={{ duration: 0.6, delay: 0.08 * i, ease }}
            />
          </span>
        </li>
      ))}
    </ul>
  )
}

// Coverage against the 80% target, with the window width beside it.
function CoverageBars({ experiments }) {
  return (
    <div className="relative">
      <ul className="space-y-4">
        {experiments.map((e, i) => (
          <li key={e.experiment} title={`${e.label}: ${Math.round(e.coverage * 100)}% inside a ${Math.round(e.mean_width)} min window`}>
            <span className="flex items-baseline justify-between gap-3 text-[14.5px]">
              <span>{e.label}</span>
              <span className="tnum shrink-0">
                <span className="font-medium">{Math.round(e.coverage * 100)}%</span>
                <span className="text-ink-3"> · {Math.round(e.mean_width)} min wide</span>
              </span>
            </span>
            <span className="relative mt-1.5 block h-2.5 rounded-r-full bg-line/60">
              <motion.span
                className={`block h-full rounded-r-full ${barColor(e.role)}`}
                initial={{ width: 0 }}
                animate={{ width: `${e.coverage * 100}%` }}
                transition={{ duration: 0.6, delay: 0.08 * i, ease }}
              />
              <span className="absolute -inset-y-1 w-0.5 bg-ink" style={{ left: `${TARGET * 100}%` }} aria-hidden="true" />
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-[12.5px] text-ink-3">Black line: 80% target. A wide enough window always hits it, so read it with the width.</p>
    </div>
  )
}

// The scoring writes a plain question for model-vs-model, and a file-name one for the baselines.
const questionText = (c) =>
  c.question.endsWith('vs the best baseline')
    ? `Does ${c.a_label.replace(/ \(tuned window\)$/, '')} beat the best baseline?`
    : c.question

// Gap in average error, with the 95% range. Zero line = no difference.
function Comparisons({ comparisons }) {
  const span = Math.max(1, ...comparisons.flatMap((c) => [Math.abs(c.lo), Math.abs(c.hi)])) * 1.15
  const x = (v) => `${50 + (v / span) * 50}%`
  return (
    <ul className="space-y-7">
      {comparisons.map((c) => {
        const clear = c.verdict !== 'not distinguishable from'
        const d = decimalsFor(c)
        return (
          <li key={c.question}>
            <p className="text-[14.5px] font-medium">{questionText(c)}</p>
            <p className="mt-0.5 text-[13.5px] text-ink-2">
              {c.a_label} is <span className="font-medium text-ink">{c.verdict}</span> {c.b_label}
              {clear && <>, by {mins(Math.abs(c.gain), d)} min per section</>}.
            </p>
            <div className="relative mt-3 h-7" aria-hidden="true">
              <span className="absolute inset-x-0 top-1/2 h-px bg-line" />
              <span className="absolute top-0 bottom-0 w-px bg-ink-3" style={{ left: x(0) }} />
              <motion.span
                className={`absolute top-1/2 h-1 -translate-y-1/2 rounded-full ${clear ? 'bg-accent' : 'bg-[var(--rail)]'}`}
                initial={{ left: x(0), width: 0 }}
                animate={{ left: x(c.lo), width: `${((c.hi - c.lo) / span) * 50}%` }}
                transition={{ duration: 0.6, ease }}
              />
              <motion.span
                className={`absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-card ${clear ? 'bg-accent' : 'bg-[var(--rail)]'}`}
                initial={{ left: x(0) }}
                animate={{ left: x(c.gain) }}
                transition={{ duration: 0.6, ease }}
              />
            </div>
            <p className="tnum mt-1 flex justify-between text-[12px] text-ink-3">
              <span>worse</span>
              <span>
                {c.gain >= 0 ? '+' : ''}{mins(c.gain, d)} min (95% range {mins(c.lo, d)} to {mins(c.hi, d)})
              </span>
              <span>better</span>
            </p>
          </li>
        )
      })}
    </ul>
  )
}

// Tuning only widens the window, so "model_network_cal" answers the same question as "model_network"
const idea = (name) => name.replace(/_cal$/, '')

function headline(data) {
  const lines = []
  // Lead with the result that matters to a passenger: is SANKET better than a simple rule?
  const vsBaseline = data.comparisons.find((c) => c.b.startsWith('baseline') && c.verdict === 'clearly better than')
  if (vsBaseline)
    lines.push(`SANKET's forecasts are ${vsBaseline.gain.toFixed(1)} minutes closer per section than the best simple rule.`)

  const net = data.comparisons.find((c) => idea(c.a) === 'model_network' && idea(c.b) === 'model_base')
  if (net?.verdict === 'clearly better than')
    lines.push(`Knowing what other trains are doing cut the average error by a further ${net.gain.toFixed(1)} minutes.`)
  else if (net?.verdict === 'clearly worse than')
    lines.push(`Adding what other trains are doing made the forecasts worse, by ${Math.abs(net.gain).toFixed(1)} minutes.`)
  else if (net)
    lines.push('Adding what other trains are doing did not clearly change the error, on the data so far.')

  return lines.join(' ') || null
}

export default function ResultsPage() {
  const [state, setState] = useState({ status: 'loading' })

  useEffect(() => {
    fetchResults()
      .then((data) => setState({ status: 'ready', data }))
      .catch(() => setState({ status: 'missing' }))
  }, [])

  if (state.status === 'loading') return <Shell><LoadingState /></Shell>
  if (state.status === 'missing')
    return (
      <Shell>
        <h1 className="tighter text-[40px] font-medium leading-tight">Results</h1>
        <p className="mt-3 max-w-xl text-[15px] text-ink-2">
          The comparison has not been run yet. Results appear here once the evaluation writes them.
        </p>
      </Shell>
    )

  const { data } = state
  const line = headline(data)

  return (
    <>
      {data.is_sample && (
        <div role="status" className="bg-accent-soft/50">
          <p className="mx-auto max-w-6xl px-6 py-2 text-[13.5px] text-ink">
            Sample results. These numbers come from practice data and are not SANKET's real result.
          </p>
        </div>
      )}
      <Shell>
        <h1 className="tighter text-[40px] font-medium leading-tight">Results</h1>
        <p className="mt-2 max-w-2xl text-[15px] text-ink-2">
          Does knowing what other trains are doing make SANKET's forecasts better? We compared {byIdea(data.experiments).length} ways
          of predicting the minutes a train loses between stations, all on the same test sections.
        </p>
        {line && <p className="tight mt-6 max-w-3xl text-[22px] font-medium leading-snug">{line}</p>}

        <div className="mt-8 grid items-start gap-5 lg:grid-cols-2">
          <Card
            title="How far off each forecast is"
            note="Average error in minutes, per section. Lower is better. Tuning the window does not change it."
          >
            <Legend />
            <div className="mt-4"><ErrorBars experiments={byIdea(data.experiments)} /></div>
          </Card>
          <Card title="How often the window catches the real delay" note="Share of sections where the real minutes fell inside the predicted window.">
            <Legend />
            <div className="mt-4"><CoverageBars experiments={data.experiments} /></div>
          </Card>
        </div>

        {data.comparisons.length > 0 && (
          <div className="mt-5">
            <Card
              title="Is the difference real, or luck?"
              note="We resampled whole train runs 5,000 times. If the range crosses zero, we can't say which is better."
            >
              <Comparisons comparisons={data.comparisons} />
            </Card>
          </div>
        )}

        <p className="mt-5 text-[13px] text-ink-3">
          {data.n_sections} test sections from {data.n_train_runs} train runs, tested on {data.test_dates.map(dayOf).join(', ')}.
          Sections of one train share its delays, so the real amount of evidence is closer to the number of train runs.
        </p>
      </Shell>
    </>
  )
}

function Shell({ children }) {
  return <main className="mx-auto max-w-6xl px-6 pt-12">{children}</main>
}
