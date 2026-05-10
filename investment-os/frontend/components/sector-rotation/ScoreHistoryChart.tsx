"use client"

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { HistoryEntry } from "@/types"

interface Props {
  history: HistoryEntry[]
}

const SECTOR_COLORS: Record<string, string> = {
  CPSEETF:    "#6366f1",
  PHARMABEES: "#34d399",
  MODEFENCE:  "#f59e0b",
  METALIETF:  "#f87171",
  PSUBNKBEES: "#a78bfa",
  BANKBEES:   "#60a5fa",
  ITBEES:     "#6b7280",
  INFRABEES:  "#10b981",
  AUTOBEES:   "#fb923c",
  ENERGY:     "#e879f9",
  MOREALTY:   "#38bdf8",
  BFSI:       "#facc15",
}

export function ScoreHistoryChart({ history }: Props) {
  if (!history || history.length === 0) {
    return (
      <Card className="bg-gray-900 border-gray-800">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm text-gray-400">Score History</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center h-48 text-gray-600 text-sm">
          No history data yet.
        </CardContent>
      </Card>
    )
  }

  // Collect all unique ETF names across history
  const etfSet = new Set<string>()
  history.forEach((h) => Object.keys(h.scores).forEach((k) => etfSet.add(k)))

  // Top ETFs by latest score
  const latest = history[history.length - 1]?.scores ?? {}
  const topEtfs = [...etfSet]
    .sort((a, b) => (latest[b] ?? 0) - (latest[a] ?? 0))
    .slice(0, 6)

  const chartData = [...history]
    .sort((a, b) => a.month.localeCompare(b.month))
    .map((h) => ({
      month: h.month.replace("2026-", ""),
      ...Object.fromEntries(topEtfs.map((e) => [e, h.scores[e] ?? null])),
    }))

  return (
    <Card className="bg-gray-900 border-gray-800">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm text-gray-400">Score History — Top 6 Sectors</CardTitle>
        <p className="text-xs text-gray-600">Rolling monthly scores from history log</p>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={chartData} margin={{ top: 4, right: 16, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis
              dataKey="month"
              tick={{ fill: "#6b7280", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              domain={[0, 10]}
              ticks={[0, 2, 4, 5, 6, 7, 8, 10]}
              tick={{ fill: "#6b7280", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              contentStyle={{ background: "#111827", border: "1px solid #374151", borderRadius: 8 }}
              labelStyle={{ color: "#f3f4f6", fontWeight: 600, marginBottom: 6 }}
              formatter={(val: unknown) => typeof val === "number" ? val.toFixed(1) : "N/A"}
            />
            <Legend
              wrapperStyle={{ fontSize: 11, color: "#9ca3af" }}
              iconType="circle"
              iconSize={8}
            />
            {topEtfs.map((etf) => (
              <Line
                key={etf}
                type="monotone"
                dataKey={etf}
                stroke={SECTOR_COLORS[etf] ?? "#6b7280"}
                strokeWidth={2}
                dot={{ r: 3, fill: SECTOR_COLORS[etf] ?? "#6b7280" }}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}
