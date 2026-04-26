"use client"

import { useQuery } from "@tanstack/react-query"
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { getPortfolioAllocation } from "@/lib/api"
import { formatINR, formatINRCompact } from "@/lib/utils"
import { getPortfolioSummary } from "@/lib/api"

const CLASS_COLORS: Record<string, string> = {
  equity: "#6366f1",
  mf: "#8b5cf6",
  etf: "#a78bfa",
  gold: "#f59e0b",
  cash: "#10b981",
  debt: "#64748b",
}

const CLASS_LABELS: Record<string, string> = {
  equity: "Equity",
  mf: "Mutual Funds",
  etf: "ETF",
  gold: "Gold",
  cash: "Cash",
  debt: "Debt",
}

export function AllocationDonut() {
  const { data: alloc, isLoading: allocLoading } = useQuery({
    queryKey: ["portfolioAllocation"],
    queryFn: getPortfolioAllocation,
    refetchInterval: 60_000,
  })
  const { data: summary } = useQuery({
    queryKey: ["portfolioSummary"],
    queryFn: getPortfolioSummary,
  })

  if (allocLoading || !alloc) {
    return (
      <Card className="bg-gray-900 border-gray-800 h-full">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm text-gray-400">Allocation</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-48 w-full bg-gray-800 rounded-full mx-auto" style={{ borderRadius: "50%" }} />
        </CardContent>
      </Card>
    )
  }

  const pieData = Object.entries(alloc.by_class).map(([cls, pct]) => ({
    name: CLASS_LABELS[cls] || cls,
    value: pct,
    cls,
  }))

  if (pieData.length === 0) {
    return (
      <Card className="bg-gray-900 border-gray-800 h-full">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm text-gray-400">Allocation</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center h-48 text-gray-600 text-sm">
          No holdings synced yet.
        </CardContent>
      </Card>
    )
  }

  const totalValue = summary?.total_value ?? 0

  return (
    <Card className="bg-gray-900 border-gray-800 h-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm text-gray-400">Allocation</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="relative">
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={90}
                dataKey="value"
                strokeWidth={2}
                stroke="#111827"
              >
                {pieData.map((entry) => (
                  <Cell key={entry.cls} fill={CLASS_COLORS[entry.cls] || "#6b7280"} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ background: "#1f2937", border: "1px solid #374151", borderRadius: 8 }}
                labelStyle={{ color: "#e5e7eb" }}
                formatter={(val) => [`${Number(val ?? 0).toFixed(1)}%`, ""]}
              />
            </PieChart>
          </ResponsiveContainer>
          {totalValue > 0 && (
            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
              <p className="text-xs text-gray-500">Total</p>
              <p className="text-sm font-semibold text-white">{formatINRCompact(totalValue)}</p>
            </div>
          )}
        </div>

        <div className="mt-3 space-y-1.5">
          {pieData.map((entry) => (
            <div key={entry.cls} className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <span
                  className="inline-block h-2.5 w-2.5 rounded-sm"
                  style={{ background: CLASS_COLORS[entry.cls] || "#6b7280" }}
                />
                <span className="text-gray-400">{entry.name}</span>
              </div>
              <div className="flex items-center gap-2 text-gray-300">
                <span>{entry.value.toFixed(1)}%</span>
                {totalValue > 0 && (
                  <span className="text-gray-600">{formatINR((entry.value / 100) * totalValue)}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
