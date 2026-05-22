export interface IndicatorMeta {
  label: string
  weight: number
  category: 'technical' | 'chip'
}

export interface TemperatureData {
  temperature: number
  scores: Record<string, number>
  data_real: Record<string, boolean>
  price: number
  price_change_pct: number
  updated_at: string
  meta: Record<string, IndicatorMeta>
}

export interface HistoryPoint {
  date: string
  tech_temp: number
  price: number
}

export type Period = 'short' | 'mid' | 'long'

export interface ZoneInfo {
  label: string
  labelEn: string
  color: string
  bg: string
  text: string
  border: string
}

export const ZONES: ZoneInfo[] = [
  { label: '極度低溫', labelEn: 'Very Cold',   color: '#1D4ED8', bg: 'bg-blue-700',  text: 'text-blue-700',  border: 'border-blue-700' },
  { label: '偏低溫',   labelEn: 'Cool',         color: '#60A5FA', bg: 'bg-blue-400',  text: 'text-blue-400',  border: 'border-blue-400' },
  { label: '正常',     labelEn: 'Neutral',      color: '#10B981', bg: 'bg-emerald-500', text: 'text-emerald-600', border: 'border-emerald-500' },
  { label: '偏高溫',   labelEn: 'Warm',         color: '#F59E0B', bg: 'bg-amber-500', text: 'text-amber-500', border: 'border-amber-500' },
  { label: '極度過熱', labelEn: 'Overheated',   color: '#EF4444', bg: 'bg-red-500',   text: 'text-red-500',   border: 'border-red-500' },
]

export function getZone(temp: number): ZoneInfo {
  if (temp < 20)  return ZONES[0]
  if (temp < 40)  return ZONES[1]
  if (temp < 60)  return ZONES[2]
  if (temp < 80)  return ZONES[3]
  return ZONES[4]
}

export function getScoreColor(score: number): string {
  if (score < 20)  return '#1D4ED8'
  if (score < 40)  return '#60A5FA'
  if (score < 60)  return '#10B981'
  if (score < 80)  return '#F59E0B'
  return '#EF4444'
}
