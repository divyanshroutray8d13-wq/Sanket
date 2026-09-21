const SECTIONS = [
  {
    title: 'What SANKET does',
    body: [
      'Most train apps take the delay a train has now and carry it forward, minus whatever recovery time the timetable allows. That treats each train as if it were alone on the network.',
      'SANKET predicts the minutes a train loses on every block section against its booked sectional running time, then chains those sections forward to give an arrival window at each station ahead. Because the model also sees the state of the network around the train, it can predict a delay before the train has run into it.',
    ],
  },
  {
    title: 'Why a window and not a time',
    body: [
      'A single predicted time hides how sure the forecast is. SANKET gives a range instead, along with the most likely time inside it. The further ahead a station is, the wider that range becomes, which is honest rather than confident.',
      'Each forecast also carries its causes, so a delay reads as named reasons rather than one opaque number.',
    ],
  },
  {
    title: 'Where the data comes from',
    body: [
      'Timetables come from the Indian Railways schedule published on data.gov.in, which gives every train, its stops and its booked running times. Live running data comes from the RailRadar API.',
      'The live feed is rate limited, so a scheduled job refreshes one snapshot on a timer and the dashboard reads that file. If a refresh fails or the quota runs out, the page shows the last saved forecast with the time it was made, rather than an error.',
    ],
  },
  {
    title: 'What it cannot do yet',
    body: [
      'Coverage is one corridor, Delhi to Mumbai, with more planned. Forecasts are for scheduled stopping stations, not continuous positions, so anything shown between stations is an estimate.',
      'This is a prototype built for Smart India Hackathon 2026, not a production service, and it should not be used to plan a connection.',
    ],
  },
]

export default function AboutPage() {
  return (
    <main className="mx-auto max-w-6xl px-6 pt-12">
      <h1 className="tighter text-[40px] font-medium leading-tight">About SANKET</h1>
      <p className="mt-2 max-w-2xl text-[15px] text-ink-2">
        A network-aware arrival forecast for Indian Railways, built for problem statement 26028.
      </p>

      <div className="mt-10 grid items-start gap-5 lg:grid-cols-2">
        {SECTIONS.map((s) => (
          <section key={s.title} className="rounded-2xl bg-card p-6">
            <h2 className="tight text-[20px] font-medium">{s.title}</h2>
            {s.body.map((p) => (
              <p key={p} className="mt-3 text-[14.5px] leading-relaxed text-ink-2">{p}</p>
            ))}
          </section>
        ))}
      </div>

      <section className="mt-5 rounded-2xl bg-card p-6">
        <h2 className="tight text-[20px] font-medium">The team</h2>
        <p className="mt-3 max-w-2xl text-[14.5px] leading-relaxed text-ink-2">
          Team Claymore, Smart India Hackathon 2026. Data from RailRadar and data.gov.in. Timetable times shown in the
          dashboard are Indian Standard Time.
        </p>
      </section>
    </main>
  )
}
