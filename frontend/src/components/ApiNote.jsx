const VIEWS = [
  { label: 'Passenger app', query: '?profile=app', note: 'Window and confidence' },
  { label: 'Station display', query: '?profile=board', note: 'One time per station' },
  { label: 'Control room', query: '', note: 'Full forecast and causes' },
]

export default function ApiNote({ trainNo }) {
  return (
    <section aria-labelledby="api-title" className="rounded-2xl bg-card p-6">
      <h2 id="api-title" className="tight text-[17px] font-medium">One forecast, three screens</h2>
      <p className="mt-1 text-[14px] text-ink-2">The same API call feeds every screen, each in the shape it needs.</p>
      <dl className="mt-4 grid gap-x-8 gap-y-4 sm:grid-cols-3">
        {VIEWS.map(({ label, query, note }) => (
          <div key={label}>
            <dt className="text-[14px]">{label}</dt>
            <dd className="mt-1 text-[12.5px] text-ink-3">
              <code>GET /eta/{trainNo}{query}</code>
              <span className="mt-0.5 block">{note}</span>
            </dd>
          </div>
        ))}
      </dl>
    </section>
  )
}
