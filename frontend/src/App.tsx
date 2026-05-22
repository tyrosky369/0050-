import { useEffect, useState, useCallback } from 'react'
import Gauge from './components/Gauge'
import IndicatorGrid from './components/IndicatorGrid'
import HistoryChart from './components/HistoryChart'
import type { TemperatureData, HistoryPoint } from './types'
import { getZone } from './types'
import { fetchTemperature, fetchHistory } from './api'

const REFRESH_MS = 5 * 60 * 1000

function ZoneGuide() {
  const zones = [
    { range: '0–20',   label: '極度低溫', desc: '超跌機會',   color: '#1D4ED8' },
    { range: '20–40',  label: '偏低溫',   desc: '分批佈局',   color: '#60A5FA' },
    { range: '40–60',  label: '正常',     desc: '維持配置',   color: '#10B981' },
    { range: '60–80',  label: '偏高溫',   desc: '減少新增',   color: '#F59E0B' },
    { range: '80–100', label: '極度過熱', desc: '逢高減碼',   color: '#EF4444' },
  ]
  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">溫度區間說明</h3>
      <div className="space-y-2">
        {zones.map(({ range, label, desc, color }) => (
          <div key={range} className="flex items-center gap-3">
            <span
              className="w-12 text-xs font-mono text-center rounded px-1 py-0.5 text-white shrink-0"
              style={{ backgroundColor: color }}
            >
              {range}
            </span>
            <span className="text-sm font-medium text-gray-700 w-20 shrink-0">{label}</span>
            <span className="text-xs text-gray-400">{desc}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function App() {
  const [tempData, setTempData]     = useState<TemperatureData | null>(null)
  const [history,  setHistory]      = useState<HistoryPoint[]>([])
  const [loading,  setLoading]      = useState(true)
  const [error,    setError]        = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true)
    setError(null)
    try {
      const [td, hist] = await Promise.all([fetchTemperature(), fetchHistory()])
      setTempData(td)
      setHistory(hist)
    } catch (e: any) {
      setError(e.message ?? '資料載入失敗')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    load()
    const timer = setInterval(() => load(true), REFRESH_MS)
    return () => clearInterval(timer)
  }, [load])

  const zone = tempData ? getZone(tempData.temperature) : null

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xl">🌡️</span>
            <div>
              <h1 className="text-base font-bold text-gray-900 leading-tight">0050 溫度計</h1>
              <p className="text-[10px] text-gray-400 leading-tight">元大台灣 50 ETF 市場溫度儀錶</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {tempData && (
              <span className="text-xs text-gray-400 hidden sm:block">
                更新：{tempData.updated_at}
              </span>
            )}
            <button
              onClick={() => load(true)}
              disabled={refreshing}
              className="text-xs px-3 py-1.5 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-600 transition disabled:opacity-50"
            >
              {refreshing ? '載入中…' : '重新整理'}
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        {loading && (
          <div className="flex flex-col items-center justify-center py-24 gap-4">
            <div className="w-12 h-12 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
            <p className="text-gray-500 text-sm">
              正在從 Yahoo Finance 與 TWSE 抓取資料…
              <br />
              <span className="text-xs text-gray-400">首次載入需約 30–60 秒</span>
            </p>
          </div>
        )}

        {error && !loading && (
          <div className="bg-red-50 border border-red-200 rounded-2xl p-6 text-center">
            <p className="text-red-600 font-medium mb-2">載入失敗</p>
            <p className="text-red-400 text-sm mb-4">{error}</p>
            <button
              onClick={() => load()}
              className="px-4 py-2 bg-red-600 text-white rounded-lg text-sm hover:bg-red-700"
            >
              重試
            </button>
          </div>
        )}

        {tempData && !loading && (
          <>
            {/* Top card: Gauge + Price + Action hint */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
                {/* Gauge */}
                <div className="flex flex-col items-center">
                  <Gauge value={tempData.temperature} />
                  <div className="mt-3 text-center">
                    <div className="flex items-baseline gap-2 justify-center">
                      <span className="text-2xl font-bold text-gray-900">
                        NT${tempData.price.toFixed(1)}
                      </span>
                      <span
                        className={`text-sm font-semibold ${
                          tempData.price_change_pct >= 0
                            ? 'text-red-500'
                            : 'text-green-600'
                        }`}
                      >
                        {tempData.price_change_pct >= 0 ? '▲' : '▼'}{' '}
                        {Math.abs(tempData.price_change_pct).toFixed(2)}%
                      </span>
                    </div>
                    <p className="text-xs text-gray-400 mt-0.5">元大台灣 50 ETF (0050)</p>
                  </div>
                </div>

                {/* Right side: score summary + action */}
                <div className="space-y-4">
                  {/* Score breakdown bars */}
                  <div className="space-y-3">
                    {[
                      {
                        label: '技術面',
                        keys: ['rsi','kd','macd','bias','bollinger','volume_ratio'],
                        color: '#6366F1',
                      },
                      {
                        label: '籌碼面',
                        keys: ['foreign','margin','short','etf_holders','big_holder'],
                        color: '#F59E0B',
                      },
                    ].map(({ label, keys, color }) => {
                      const totalW = keys.reduce((s, k) => s + (tempData.meta[k]?.weight ?? 0), 0)
                      const weightedScore = keys.reduce(
                        (s, k) => s + (tempData.scores[k] ?? 50) * (tempData.meta[k]?.weight ?? 0),
                        0,
                      ) / (totalW || 1)

                      return (
                        <div key={label}>
                          <div className="flex justify-between text-xs text-gray-500 mb-1">
                            <span>{label}</span>
                            <span className="font-semibold" style={{ color }}>
                              {weightedScore.toFixed(1)}
                            </span>
                          </div>
                          <div className="bg-gray-100 rounded-full h-2.5 overflow-hidden">
                            <div
                              className="h-full rounded-full transition-all duration-700"
                              style={{
                                width: `${weightedScore}%`,
                                backgroundColor: color,
                              }}
                            />
                          </div>
                        </div>
                      )
                    })}
                  </div>

                  {/* Action suggestion */}
                  <div
                    className="rounded-xl p-4 border-l-4"
                    style={{ borderColor: zone!.color, backgroundColor: zone!.color + '12' }}
                  >
                    <p className="text-sm font-semibold mb-1" style={{ color: zone!.color }}>
                      {zone!.label}
                    </p>
                    <p className="text-xs text-gray-600 leading-relaxed">
                      {tempData.temperature < 20
                        ? '市場情緒恐慌，可能超跌。可考慮分批積極建倉。'
                        : tempData.temperature < 40
                        ? '市場偏悲觀，籌碼面若有外資回補可提高比例。'
                        : tempData.temperature < 60
                        ? '市場均衡，維持現有配置，定期定額持續執行。'
                        : tempData.temperature < 80
                        ? '市場偏樂觀，減少新增買進，可部分獲利了結。'
                        : '市場過熱，建議停止追高，逢高分批減碼。'}
                    </p>
                  </div>

                  {/* Disclaimer */}
                  <p className="text-[10px] text-gray-400 leading-relaxed">
                    ⚠ 本儀錶僅為輔助參考，不構成投資建議。投資前請自行評估風險。
                  </p>
                </div>
              </div>
            </div>

            {/* Indicator breakdown */}
            <IndicatorGrid data={tempData} />

            {/* History chart */}
            {history.length > 0 && <HistoryChart data={history} />}

            {/* Zone guide */}
            <ZoneGuide />
          </>
        )}
      </main>

      <footer className="text-center text-xs text-gray-400 py-6">
        資料來源：Yahoo Finance・TWSE 臺灣證交所 ・ 本工具僅供學習研究
      </footer>
    </div>
  )
}
