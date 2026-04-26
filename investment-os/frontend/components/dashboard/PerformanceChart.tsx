"use client"

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { getPortfolioPerformance } from "@/lib/api"
import { formatINRCompact } from "@/lib/utils"
import { format } from "date-fns"

const TABS = [
  { label: "1M", days: 30 },
  { label: "3M", days: 90 },
  { label: "6M", days: 180 },
  { label: "1Y", days: 365 },
  { label: "All", days: 1825 },
]

export function PerformanceChart() {
  const [activeDays, setActiveDays] = useState(90)

  const { data: snapshots, isLoading } = useQuery({
    queryKey: ["portfolioPerformance", activeDays],
    queryFn: () => getPortfolioPerformance(activeDays),
    refetchInterval: 60_000,
  })

  const chartData = buildChartData(snapshots ?? [])

  return (
    <Card className="bg-gray-900 border-gray-800 h-full">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm text-gray-400">Performance</CardTitle>
          <div className="flex gap-1">
            {TABS.map((t) => (
              <button
                key={t.label}
                onClick={() => setActiveDays(t.days)}
                className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                  activeDays === t.days
                    ? "bg-indigo-700 text-white"
                    : "text-gray-500 hover:text-gray-300"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-[260px] w-full bg-gray-800" />
        ) : chartData.length === 0 ? (
          <div className="flex items-center justify-center h-[260px] text-gray-600 text-sm">
            No performance data yet. Click Sync Now to start tracking.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={chartData} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="portfolioGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis
                dataKey="date"
                tick={{ fill: "#6b7280", fontSize: 11 }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                tickFormatter={(v) => formatINRCompact(v)}
                tick={{ fill: "#6b7280", fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                width={64}
              />
              <Tooltip
                contentStyle={{ background: "#1f2937", border: "1px solid #374151", borderRadius: 8 }}
                labelStyle={{ color: "#e5e7eb", fontSize: 12 }}
                formatter={(val, name) => [formatINRCompact(Number(val ?? 0)), String(name)]}
              />
              <Legend
                wrapperStyle={{ fontSize: 12, color: "#6b7280" }}
                iconType="circle"
                iconSize={8}
              />
              <Area
                type="monotone"
                dataKey="portfolio"
                name="Portfolio"
                stroke="#6366f1"
                strokeWidth={2}
                fill="url(#portfolioGrad)"
                dot={false}
              />
              <Area
                type="monotone"
                dataKey="nifty"
                name="Nifty 50 (indexed)"
                stroke="#374151"
                strokeWidth={1.5}
                strokeDasharray="5 3"
                fill="none"
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  )
}

interface Snapshot {
  snapshot_date: string
  total_value: number | null
  nifty50_value: number | null
}

function buildChartData(snapshots: Snapshot[]) {
  if (!snapshots || snapshots.length === 0) return []

  const firstPortfolio = snapshots[0]?.total_value ?? 1
  const firstNifty = snapshots[0]?.nifty50_value ?? 1

  return snapshots.map((s) => {
    const niftyIndexed =
      s.nifty50_value && firstNifty
        ? (s.nifty50_value / firstNifty) * firstPortfolio
        : null

    return {
      date: format(new Date(s.snapshot_date), "dd MMM"),
      portfolio: s.total_value ?? 0,
      nifty: niftyIndexed,
    }
  })
}
