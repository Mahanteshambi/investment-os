"use client"

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell, ReferenceLine, ResponsiveContainer,
} from "recharts"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { SectorScore } from "@/types"

interface Props {
  scores: SectorScore[]
}

const SCORE_COLOR = (s: number) =>
  s >= 7 ? "#34d399" : s >= 5 ? "#fbbf24" : "#f87171"

const DECISION_LABEL: Record<string, string> = {
  BUY: "BUY",
  HOLD: "HOLD",
  AVOID: "AVOID",
  "AVOID+EXIT": "EXIT",
  EXITED: "EXITED",
  WATCH: "WATCH",
}

export function SectorScoreChart({ scores }: Props) {
  const data = [...scores]
    .sort((a, b) => b.composite_score - a.composite_score)
    .map((s) => ({
      name: s.etf.replace("NSE:", ""),
      composite: s.composite_score,
      tech: s.technical_score,
      fund: s.fundamental_score,
      fii: s.fii_dii_score,
      decision: DECISION_LABEL[s.decision] ?? s.decision,
    }))

  return (
    <Card className="bg-gray-900 border-gray-800">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm text-gray-400">Composite Scores — All 12 Sectors</CardTitle>
        <p className="text-xs text-gray-600">
          <span className="text-emerald-400">■</span> ≥7 BUY &nbsp;
          <span className="text-yellow-400">■</span> 5–7 HOLD &nbsp;
          <span className="text-red-400">■</span> &lt;5 AVOID
        </p>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={320}>
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 4, right: 60, left: 0, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" horizontal={false} />
            <XAxis
              type="number"
              domain={[0, 10]}
              ticks={[0, 2, 4, 5, 6, 7, 8, 10]}
              tick={{ fill: "#6b7280", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              type="category"
              dataKey="name"
              tick={{ fill: "#d1d5db", fontSize: 12, fontWeight: 500 }}
              tickLine={false}
              axisLine={false}
              width={96}
            />
            <ReferenceLine x={7} stroke="#34d399" strokeDasharray="4 3" strokeOpacity={0.4} />
            <ReferenceLine x={5} stroke="#fbbf24" strokeDasharray="4 3" strokeOpacity={0.4} />
            <Tooltip
              cursor={{ fill: "#1f2937", opacity: 0.5 }}
              contentStyle={{ background: "#111827", border: "1px solid #374151", borderRadius: 8 }}
              labelStyle={{ color: "#f3f4f6", fontWeight: 600, marginBottom: 6 }}
              formatter={(val: unknown, name: unknown) => [
                typeof val === "number" ? val.toFixed(1) : String(val ?? ""),
                typeof name === "string" ? name.charAt(0).toUpperCase() + name.slice(1) : String(name),
              ]}
            />
            <Bar dataKey="composite" name="Composite" radius={[0, 4, 4, 0]} maxBarSize={18}
              label={{ position: "right", fill: "#9ca3af", fontSize: 11, formatter: (v: unknown) => typeof v === "number" ? v.toFixed(1) : "" }}
            >
              {data.map((entry, i) => (
                <Cell key={i} fill={SCORE_COLOR(entry.composite)} fillOpacity={0.85} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}
