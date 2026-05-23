import { getZone } from '../types'

// SVG gauge math:
// Center at (cx, cy). SVG angle 0°=right, 90°=bottom, 180°=left, 270°=top.
// Gauge arc goes from 180° (left, cold) → 270° (top) → 360° (right, hot).
// For temperature T ∈ [0,100]: svgAngle = 180 + (T/100)*180 degrees.
// sweep-flag=1 = clockwise in SVG = traces the top semicircle. ✓

interface GaugeProps {
  value: number
}

const CX = 200
const CY = 185
const OUTER_R = 155
const INNER_R = 105
const MID_R = (OUTER_R + INNER_R) / 2
const STROKE_W = OUTER_R - INNER_R
const NEEDLE_LEN = INNER_R - 8
const TICK_OUTER = OUTER_R + 14
const TICK_INNER = OUTER_R + 4

const ZONES = [
  { t1: 0,  t2: 20,  color: '#1D4ED8' },
  { t1: 20, t2: 40,  color: '#60A5FA' },
  { t1: 40, t2: 60,  color: '#10B981' },
  { t1: 60, t2: 80,  color: '#F59E0B' },
  { t1: 80, t2: 100, color: '#EF4444' },
]

const ZONE_LABELS = [
  { t: 10,  label: '極冷' },
  { t: 30,  label: '偏冷' },
  { t: 50,  label: '正常' },
  { t: 70,  label: '偏熱' },
  { t: 90,  label: '過熱' },
]

function toRad(deg: number) { return (deg * Math.PI) / 180 }

function pt(r: number, svgDeg: number) {
  const rad = toRad(svgDeg)
  return { x: CX + r * Math.cos(rad), y: CY + r * Math.sin(rad) }
}

function tToAngle(t: number) { return 180 + (t / 100) * 180 }

function arcPath(r: number, t1: number, t2: number): string {
  const a1 = tToAngle(t1)
  const a2 = tToAngle(t2)
  const p1 = pt(r, a1)
  const p2 = pt(r, a2)
  const large = a2 - a1 > 180 ? 1 : 0
  return `M ${p1.x.toFixed(2)} ${p1.y.toFixed(2)} A ${r} ${r} 0 ${large} 1 ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}`
}

const TICK_TEMPS = [0, 20, 40, 60, 80, 100]

export default function Gauge({ value }: GaugeProps) {
  const clampedVal = Math.max(0, Math.min(100, value))
  const zone = getZone(clampedVal)

  const needleAngle = tToAngle(clampedVal)
  const needleTip   = pt(NEEDLE_LEN, needleAngle)
  const needleBase1 = pt(8, needleAngle + 90)
  const needleBase2 = pt(8, needleAngle - 90)

  return (
    <div className="flex flex-col items-center">
      <svg
        viewBox="0 0 400 200"
        className="w-full max-w-sm"
        aria-label={`溫度計 ${clampedVal}`}
      >
        {/* Background track */}
        <path
          d={arcPath(MID_R, 0, 100)}
          fill="none"
          stroke="#E5E7EB"
          strokeWidth={STROKE_W}
          strokeLinecap="butt"
        />

        {/* Colored zone arcs */}
        {ZONES.map(({ t1, t2, color }) => (
          <path
            key={t1}
            d={arcPath(MID_R, t1, t2)}
            fill="none"
            stroke={color}
            strokeWidth={STROKE_W}
            strokeLinecap="butt"
            opacity="0.85"
          />
        ))}

        {/* Active highlight: arc from 0 to current value */}
        <path
          d={arcPath(MID_R, 0, Math.max(0.5, clampedVal))}
          fill="none"
          stroke={zone.color}
          strokeWidth={STROKE_W}
          strokeLinecap="butt"
          opacity="1"
          filter="url(#glow)"
        />

        {/* Glow filter */}
        <defs>
          <filter id="glow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Tick marks */}
        {TICK_TEMPS.map((t) => {
          const angle = tToAngle(t)
          const outer = pt(TICK_OUTER, angle)
          const inner = pt(TICK_INNER, angle)
          return (
            <line
              key={t}
              x1={inner.x}
              y1={inner.y}
              x2={outer.x}
              y2={outer.y}
              stroke="#6B7280"
              strokeWidth={2}
              strokeLinecap="round"
            />
          )
        })}

        {/* Tick labels (0 / 50 / 100) */}
        {[0, 50, 100].map((t) => {
          const angle = tToAngle(t)
          const pos   = pt(TICK_OUTER + 14, angle)
          return (
            <text
              key={t}
              x={pos.x}
              y={pos.y + 4}
              textAnchor="middle"
              fontSize="11"
              fill="#6B7280"
              fontFamily="sans-serif"
            >
              {t}
            </text>
          )
        })}

        {/* Zone labels inside arc */}
        {ZONE_LABELS.map(({ t, label }) => {
          const angle = tToAngle(t)
          const pos   = pt(MID_R, angle)
          return (
            <text
              key={t}
              x={pos.x}
              y={pos.y + 4}
              textAnchor="middle"
              fontSize="9"
              fill="white"
              fontWeight="600"
              fontFamily="sans-serif"
              style={{ pointerEvents: 'none' }}
            >
              {label}
            </text>
          )
        })}

        {/* Needle (triangle) */}
        <polygon
          points={`${needleTip.x.toFixed(1)},${needleTip.y.toFixed(1)} ${needleBase1.x.toFixed(1)},${needleBase1.y.toFixed(1)} ${needleBase2.x.toFixed(1)},${needleBase2.y.toFixed(1)}`}
          fill="#1F2937"
          opacity="0.9"
        />

        {/* Center cap */}
        <circle cx={CX} cy={CY} r={12} fill="#1F2937" />
        <circle cx={CX} cy={CY} r={6}  fill="#F9FAFB" />

      </svg>

      {/* Large temperature number */}
      <div className="flex items-baseline gap-1 -mt-3">
        <span
          className="text-8xl font-black tabular-nums leading-none"
          style={{ color: zone.color }}
        >
          {clampedVal.toFixed(1)}
        </span>
        <span className="text-2xl font-semibold text-gray-400 mb-1">°</span>
      </div>

      {/* Zone badge */}
      <span
        className="mt-2 px-6 py-1.5 rounded-full text-white text-base font-bold tracking-widest"
        style={{ backgroundColor: zone.color }}
      >
        {zone.label}
      </span>
    </div>
  )
}
