"use client"

import { useQuery } from "@tanstack/react-query"
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { getPortfolioAllocation, getPortfolioSummary } from "@/lib/api"
import { formatINRCompact } from "@/lib/utils"

const CLASS_COLORS: Record<string, string> = {
  equity: "#6366f1",
  mf: "#8b5cf6",
  etf: "#a78bfa",
  gold: "#f59e0b",
  cash: "#10b981",
  debt: "#64748b",
  fd: "#3b82f6",     // blue
  ppf: "#ec4899",    // pink
  pf: "#d946ef",     // fuchsia
  rd: "#14b8a6",     // teal
  savings: "#06b6d4" // cyan
}

const CLASS_LABELS: Record<string, string> = {
  equity: "Equity",
  mf: "Mutual Funds",
  etf: "ETF",
  gold: "Gold",
  cash: "Cash",
  debt: "Debt",
  fd: "Fixed Deposit",
  ppf: "PPF",
  pf: "PF",
  rd: "RD",
  savings: "Savings Acc"
}

export function AllocationBar() {
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
      <Card className="bg-gray-900 border-gray-800 w-full">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm text-gray-400">Allocation Breakdown</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-64 w-full bg-gray-800 rounded-lg mb-4" />
        </CardContent>
      </Card>
    )
  }

  const totalValue = summary?.total_value ?? 0

  const rawData = Object.entries(alloc.by_class).map(([cls, amount]) => ({
    name: CLASS_LABELS[cls] || cls,
    value: amount,
    pct: totalValue > 0 ? (amount / totalValue) * 100 : 0,
    cls,
  }))

  const chartData = rawData.sort((a, b) => b.value - a.value)

  if (chartData.length === 0) {
    return (
      <Card className="bg-gray-900 border-gray-800 w-full">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm text-gray-400">Allocation Breakdown</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center h-64 text-gray-600 text-sm">
          No holdings synced yet.
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="bg-gray-900 border-gray-800 w-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm text-gray-400">Allocation Breakdown</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-64 w-full relative">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <XAxis 
                dataKey="name" 
                tick={{ fill: "#9ca3af", fontSize: 12 }} 
                tickLine={false} 
                axisLine={{ stroke: "#374151" }} 
              />
              <YAxis 
                tick={{ fill: "#9ca3af", fontSize: 12 }} 
                tickLine={false} 
                axisLine={{ stroke: "#374151" }} 
                tickFormatter={(val) => formatINRCompact(val)} 
              />
              <Tooltip
                cursor={{ fill: "#1f2937", opacity: 0.4 }}
                contentStyle={{ background: "#1f2937", border: "1px solid #374151", borderRadius: 8 }}
                labelStyle={{ color: "#f3f4f6", fontWeight: "bold", marginBottom: 8 }}
                itemStyle={{ color: "#d1d5db" }}
                formatter={(value: number, name: string, props: any) => [
                  `₹${value.toLocaleString("en-IN")} (${props.payload.pct.toFixed(1)}%)`,
                  "Value"
                ]}
              />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {chartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={CLASS_COLORS[entry.cls] || "#6b7280"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}
