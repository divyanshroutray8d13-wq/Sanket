import { severity } from '../lib/severity'

// Lateness as a quiet pill. Accent only when this station is selected.
export default function DelayChip({ minutes, selected = false, big = false }) {
  const { label } = severity(minutes)
  const text = minutes <= 0 ? 'On time' : `+${minutes} min late`
  return (
    <span
      title={label}
      className={`tnum inline-block whitespace-nowrap rounded-full px-2.5 py-1 font-medium ${
        big ? 'text-[15px]' : 'text-[13px]'
      } ${selected ? 'bg-accent-soft text-accent' : 'bg-paper text-ink-2'}`}
    >
      {text}
    </span>
  )
}
