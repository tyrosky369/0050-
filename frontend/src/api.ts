import type { TemperatureData, HistoryPoint } from './types'

// import.meta.env.BASE_URL is set by Vite:
//   - local dev:  "/"
//   - GitHub Pages: "/0050-/"  (via VITE_BASE_PATH in CI)
const DATA = `${import.meta.env.BASE_URL}data`

export async function fetchTemperature(): Promise<TemperatureData> {
  const res = await fetch(`${DATA}/latest.json`, { cache: 'no-store' })
  if (!res.ok) throw new Error('無法載入資料')
  return res.json()
}

export async function fetchHistory(): Promise<HistoryPoint[]> {
  const res = await fetch(`${DATA}/history.json`, { cache: 'no-store' })
  if (!res.ok) throw new Error('無法載入歷史資料')
  const json = await res.json()
  return json.data as HistoryPoint[]
}
