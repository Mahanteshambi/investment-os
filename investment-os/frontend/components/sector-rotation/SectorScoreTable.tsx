"use client"

import { useState } from "react"
import { ChevronDown, ChevronRight } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { SectorScore } from "@/types"

interface Props {
  scores: SectorScore[]
}

const DECISION_STYLE: Record<string, string> = {
  BUY:          "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30",
  HOLD:         "bg-yellow-500/20 text-yellow-400 border border-yellow-500/30",
  AVOID:        "bg-red-500/20 text-red-400 border border-red-500/30",
  "AVOID+EXIT": "bg-red-500/20 text-red-400 border border-red-500/30",
  EXITED:       "bg-gray-500/20 text-gray-500 border border-gray-600/30",
  WATCH:        "bg-indigo-500/20 text-indigo-400 border border-indigo-500/30",
}

function ScoreBar({ value, max = 10, color }: { value: number; max?: number; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 bg-gray-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${(value / max) * 100}%` }} />
      </div>
      <span className="text-xs tabular-nums">{value.toFixed(1)}</span>
    </div>
  )
}

export function SectorScoreTable({ scores }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null)
  const sorted = [...scores].sort((a, b) => b.composite_score - a.composite_score)

  return (
    <Card className="bg-gray-900 border-gray-800">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm text-gray-400">Score Breakdown</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="text-left text-xs text-gray-500 font-medium px-4 py-2 w-6">#</th>
                <th className="text-left text-xs text-gray-500 font-medium px-4 py-2">Sector</th>
                <th className="text-left text-xs text-gray-500 font-medium px-4 py-2">ETF</th>
                <th className="text-left text-xs text-gray-500 font-medium px-4 py-2">Price</th>
                <th className="text-left text-xs text-gray-500 font-medium px-4 py-2">Technical</th>
                <th className="text-left text-xs text-gray-500 font-medium px-4 py-2">Fundamental</th>
                <th className="text-left text-xs text-gray-500 font-medium px-4 py-2">FII/DII</th>
                <th className="text-left text-xs text-gray-500 font-medium px-4 py-2">Composite</th>
                <th className="text-left text-xs text-gray-500 font-medium px-4 py-2">Decision</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((s) => {
                const etf = s.etf.replace("NSE:", "")
                const isExpanded = expanded === etf
                const compositeColor = s.composite_score >= 7 ? "text-emerald-400"
                  : s.composite_score >= 5 ? "text-yellow-400"
                  : "text-red-400"

                return (
                  <>
                    <tr
                      key={etf}
                      className="border-b border-gray-800/60 hover:bg-gray-800/30 cursor-pointer transition-colors"
                      onClick={() => setExpanded(isExpanded ? null : etf)}
                    >
                      <td className="px-4 py-3 text-gray-500 text-xs">{s.rank}</td>
                      <td className="px-4 py-3 text-gray-300 font-medium">{s.sector}</td>
                      <td className="px-4 py-3 text-gray-400 font-mono text-xs">{etf}</td>
                      <td className="px-4 py-3 text-gray-300 tabular-nums">
                        ₹{s.current_price.toFixed(2)}
                      </td>
                      <td className="px-4 py-3">
                        <ScoreBar value={s.technical_score} color="bg-blue-400" />
                      </td>
                      <td className="px-4 py-3">
                        <ScoreBar value={s.fundamental_score} color="bg-purple-400" />
                      </td>
                      <td className="px-4 py-3">
                        <ScoreBar value={s.fii_dii_score} color="bg-cyan-400" />
                      </td>
                      <td className="px-4 py-3">
                        <span className={`text-sm font-bold tabular-nums ${compositeColor}`}>
                          {s.composite_score.toFixed(1)}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5">
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${DECISION_STYLE[s.decision] ?? DECISION_STYLE.HOLD}`}>
                            {s.decision}
                          </span>
                          {isExpanded
                            ? <ChevronDown className="h-3 w-3 text-gray-600" />
                            : <ChevronRight className="h-3 w-3 text-gray-600" />
                          }
                        </div>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr key={`${etf}-detail`} className="border-b border-gray-800/60 bg-gray-800/20">
                        <td colSpan={9} className="px-6 py-4">
                          <TechnicalDetailRow detail={s.technical_detail} notes={s.notes} allocation={s.monthly_allocation_inr} />
                        </td>
                      </tr>
                    )}
                  </>
                )
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  )
}

function TechnicalDetailRow({ detail, notes, allocation }: {
  detail: SectorScore["technical_detail"]
  notes: string
  allocation: number
}) {
  const items = [
    { label: "200-DMA", value: detail.price_vs_200dma ?? "N/A" },
    { label: "50-DMA", value: detail.price_vs_50dma },
    { label: "RSI-14", value: detail.rsi14.toFixed(1), color: detail.rsi14 >= 60 ? "text-emerald-400" : detail.rsi14 <= 40 ? "text-red-400" : "text-yellow-400" },
    { label: "52-Week Position", value: `${detail["52w_position_pct"].toFixed(1)}%` },
    { label: "Vol Ratio 20d/60d", value: detail.vol_ratio_20d_60d.toFixed(2), color: detail.vol_ratio_20d_60d >= 1.2 ? "text-emerald-400" : "text-gray-300" },
    { label: "Monthly Allocation", value: allocation > 0 ? `₹${(allocation / 1000).toFixed(0)}K` : "—" },
  ]

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
        {items.map(({ label, value, color }) => (
          <div key={label}>
            <p className="text-xs text-gray-600 mb-0.5">{label}</p>
            <p className={`text-xs font-medium ${color ?? "text-gray-300"}`}>{value}</p>
          </div>
        ))}
      </div>
      {notes && (
        <p className="text-xs text-gray-500 border-t border-gray-700/50 pt-2 leading-relaxed max-w-4xl">
          {notes}
        </p>
      )}
    </div>
  )
}
