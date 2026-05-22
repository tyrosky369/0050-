import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Legend,
} from 'recharts'
import type { HistoryPoint } from '../types'

interface Props {
  data: HistoryPoint[]
}

const ZONE_COLORS = [
  { value: 20,  color: '#1D4ED8', label: '低溫' },
  { value: 40,  color: '#60A5FA', label: '偏冷' },
  { value: 60,  color: '#10B981', label: '正常' },
  { value: 80,  color: '#F59E0B', label: '偏熱' },
]

function formatDate(dateStr: string) {
  const d = new Date(dateStr)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-lg px-3 py-2 text-sm">
      <p className="text-gray-500 text-xs mb-1">{label}</p>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: p.color }} />
          <span className="text-gray-600">{p.name}:</span>
          <span className="font-semibold" style={{ color: p.color }}>
            {p.dataKey === 'price'
              ? `NT$${p.value.toFixed(1)}`
              : p.value.toFixed(1)}
          </span>
        </div>
      ))}
    </div>
  )
}

export default function HistoryChart({ data }: Props) {
  if (!data.length) return null

  const prices  = data.map((d) => d.price)
  const priceMin = Math.floor(Math.min(...prices) * 0.98)
  const priceMax = Math.ceil(Math.max(...prices) * 1.02)

  const displayData = data.map((d) => ({
    ...d,
    date: formatDate(d.date),
  }))

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-700">歷史走勢（近 90 日）</h3>
        <span className="text-xs text-amber-600 bg-amber-50 px-2 py-0.5 rounded">
          溫度 = 技術面指標
        </span>
      </div>

      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={displayData} margin={{ top: 4, right: 20, left: 4, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />

          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fill: '#9CA3AF' }}
            tickLine={false}
            interval="preserveStartEnd"
          />

          {/* Left axis: price */}
          <YAxis
            yAxisId="price"
            domain={[priceMin, priceMax]}
            tick={{ fontSize: 11, fill: '#9CA3AF' }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => `$${v}`}
            width={52}
          />

          {/* Right axis: temperature */}
          <YAxis
            yAxisId="temp"
            orientation="right"
            domain={[0, 100]}
            tick={{ fontSize: 11, fill: '#9CA3AF' }}
            tickLine={false}
            axisLine={false}
            ticks={[0, 20, 40, 60, 80, 100]}
            width={36}
          />

          <Tooltip content={<CustomTooltip />} />
          <Legend
            iconType="circle"
            iconSize={8}
            wrapperStyle={{ fontSize: 12, color: '#6B7280' }}
          />

          {/* Zone reference lines */}
          {ZONE_COLORS.map(({ value, color, label }) => (
            <ReferenceLine
              key={value}
              yAxisId="temp"
              y={value}
              stroke={color}
              strokeDasharray="4 3"
              strokeWidth={1}
              label={{
                value: label,
                position: 'insideRight',
                fontSize: 9,
                fill: color,
              }}
            />
          ))}

          {/* Price area */}
          <Area
            yAxisId="price"
            type="monotone"
            dataKey="price"
            name="0050 股價"
            stroke="#6366F1"
            fill="#EEF2FF"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />

          {/* Technical temperature line */}
          <Line
            yAxisId="temp"
            type="monotone"
            dataKey="tech_temp"
            name="市場溫度"
            stroke="#F59E0B"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
