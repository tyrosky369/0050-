import type { TemperatureData, HistoryPoint } from './types'

// In production, VITE_API_URL points to the deployed backend (e.g. https://xxx.onrender.com)
// In development, Vite proxies /api → http://localhost:8000
const BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api`
  : '/api'

export async function fetchTemperature(): Promise<TemperatureData> {
  const res = await fetch(`${BASE}/temperature`)
  if (!res.ok) throw new Error(`API error ${res.status}`)
  return res.json()
}

export async function fetchHistory(): Promise<HistoryPoint[]> {
  const res = await fetch(`${BASE}/history`)
  if (!res.ok) throw new Error(`API error ${res.status}`)
  const json = await res.json()
  return json.data as HistoryPoint[]
}
