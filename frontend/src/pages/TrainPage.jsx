import { useCallback, useEffect, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { fetchTrain } from '../lib/api'
import TrainHeader from '../components/TrainHeader'
import JourneyPanel from '../components/JourneyPanel'
import WhyLatePanel from '../components/WhyLatePanel'
import ApiNote from '../components/ApiNote'
import StaleBanner from '../components/StaleBanner'
import { ErrorState, LoadingState } from '../components/States'

export default function TrainPage() {
  const { trainNo } = useParams()
  const [params, setParams] = useSearchParams()
  const [state, setState] = useState({ status: 'loading' })

  const load = useCallback(() => {
    setState({ status: 'loading' })
    fetchTrain(trainNo)
      .then((data) => setState({ status: 'ready', data }))
      .catch((error) => setState({ status: 'error', error }))
  }, [trainNo])

  useEffect(load, [load])

  if (state.status === 'loading') return <Shell><LoadingState /></Shell>
  if (state.status === 'error')
    return <Shell><ErrorState error={state.error} trainNo={trainNo} onRetry={load} /></Shell>

  const { data } = state
  // ?station=CODE picks the station; default to the next one
  const selectedCode = data.stations.some((s) => s.code === params.get('station'))
    ? params.get('station')
    : data.stations[0]?.code
  const selected = data.stations.find((s) => s.code === selectedCode)
  const select = (code) => {
    setParams({ station: code }, { replace: true })
    // On narrow screens the "why late" panel sits below the list, so bring it into view
    if (window.matchMedia('(max-width: 1023px)').matches) {
      requestAnimationFrame(() =>
        document.getElementById('why-late')?.scrollIntoView({ behavior: 'smooth', block: 'start' }),
      )
    }
  }

  return (
    <>
      <StaleBanner asOf={data.as_of} isMock={data.is_mock} isLive={data.is_live} />
      <Shell>
        <TrainHeader data={data} />
        <div className="mt-12 grid items-start gap-10 lg:grid-cols-[minmax(0,1fr)_18rem]">
          <JourneyPanel data={data} selected={selectedCode} onSelect={select} />
          <div id="why-late" className="scroll-mt-4 lg:sticky lg:top-10">
            <WhyLatePanel station={selected} />
          </div>
        </div>
        <div className="mt-6">
          <ApiNote trainNo={data.train_no} />
        </div>
      </Shell>
    </>
  )
}

function Shell({ children }) {
  return <main className="mx-auto max-w-6xl px-6 pt-12">{children}</main>
}
