// Map the free-text cause from the API to a colour + plain-English group.
const GROUPS = [
  { test: /carried|earlier/i, key: 'carried', label: 'Delay carried forward', color: '#8a8677' },
  { test: /speed|caution|restriction/i, key: 'speed', label: 'Speed restriction', color: '#b5533b' },
  { test: /precedence|held/i, key: 'precedence', label: 'Held for another train', color: '#4c6b8a' },
  { test: /platform/i, key: 'platform', label: 'Platform occupied', color: '#2f7d6a' },
  { test: /ahead|inherited/i, key: 'ahead', label: 'Train ahead running late', color: '#c08a2e' },
]
const OTHER = { key: 'other', label: 'Other', color: '#9a958a' }

export const causeGroup = (cause) => GROUPS.find((g) => g.test.test(cause)) ?? OTHER
