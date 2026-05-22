import type { TemperatureData } from '../types'
import { getScoreColor } from '../types'

interface Props {
  data: TemperatureData
}

const DISPLAY_ORDER = {
  technical: ['rsi', 'kd', 'macd', 'bias', 'bollinger', 'volume_ratio'],
  chip:      ['foreign', 'margin', 'short', 'etf_holders', 'big_holder'],
}

function IndicatorCard({
  id,
  score,
  label,
  weight,
  isReal,
}: {
  id: string
  score: number
  label: string
  weight: number
  isReal: boolean
}) {
  const color = getScoreColor(score)

  return (
    <div className="bg-white rounded-xl p-3 shadow-sm border border-gray-100 flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-gray-500 truncate">{label}</span>
        {!isReal && (
          <span className="text-[10px] text-amber-500 bg-amber-50 rounded px-1 leading-4 shrink-0">
            估計
          </span>
        )}
      </div>

      <div className="flex items-end justify-between">
        <span
          className="text-2xl font-bold leading-none"
          style={{ color }}
        >
          {score.toFixed(0)}
        </span>
        <span className="text-[10px] text-gray-400">
          權重 {(weight * 100).toFixed(0)}%
        </span>
      </div>

      {/* Score bar */}
      <div className="bg-gray-100 rounded-full h-1.5 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${score}%`, backgroundColor: color }}
        />
      </div>
    </div>
  )
}

export default function IndicatorGrid({ data }: Props) {
  const { scores, data_real, meta } = data

  const tech_score = DISPLAY_ORDER.technical.reduce(
    (sum, id) => sum + (scores[id] ?? 50) * (meta[id]?.weight ?? 0), 0
  )
  const tech_weight = DISPLAY_ORDER.technical.reduce(
    (sum, id) => sum + (meta[id]?.weight ?? 0), 0
  )

  const chip_score = DISPLAY_ORDER.chip.reduce(
    (sum, id) => sum + (scores[id] ?? 50) * (meta[id]?.weight ?? 0), 0
  )
  const chip_weight = DISPLAY_ORDER.chip.reduce(
    (sum, id) => sum + (meta[id]?.weight ?? 0), 0
  )

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Technical section */}
      <div className="bg-gray-50 rounded-2xl p-4 border border-gray-200">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-700">技術面指標</h3>
          <span className="text-xs text-gray-400">小計</span>
          <span className="text-sm font-bold text-gray-700">
            {(tech_score / tech_weight).toFixed(1)}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {DISPLAY_ORDER.technical.map((id) => (
            <IndicatorCard
              key={id}
              id={id}
              score={scores[id] ?? 50}
              label={meta[id]?.label ?? id}
              weight={meta[id]?.weight ?? 0}
              isReal={data_real[id] ?? false}
            />
          ))}
        </div>
      </div>

      {/* Chip section */}
      <div className="bg-gray-50 rounded-2xl p-4 border border-gray-200">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-700">籌碼面指標</h3>
          <span className="text-xs text-gray-400">小計</span>
          <span className="text-sm font-bold text-gray-700">
            {(chip_score / chip_weight).toFixed(1)}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {DISPLAY_ORDER.chip.map((id) => (
            <IndicatorCard
              key={id}
              id={id}
              score={scores[id] ?? 50}
              label={meta[id]?.label ?? id}
              weight={meta[id]?.weight ?? 0}
              isReal={data_real[id] ?? false}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
