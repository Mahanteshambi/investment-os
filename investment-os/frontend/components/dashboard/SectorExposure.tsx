"use client"

import { useQuery } from "@tanstack/react-query"
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  ResponsiveContainer,
} from "recharts"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { getPortfolioAllocation } from "@/lib/api"
import { formatINRCompact } from "@/lib/utils"

const NEUTRAL_TARGET_PCT = 10

export function SectorExposure() {
  const { data: alloc, isLoading } = useQuery({
    queryKey: ["portfolioAllocation"],
    queryFn: getPortfolioAllocation,
    refetchInterval: 60_000,
  })

  const sectors = alloc?.by_sector ?? []

  return (
    <Card className="bg-gray-900 border-gray-800 h-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm text-gray-400">Sector Exposure</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-[260px] w-full bg-gray-800" />
        ) : sectors.length === 0 ? (
          <div className="flex items-center justify-center h-[260px] text-gray-600 text-sm">
            No sector data yet.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <BarChart
              data={sectors}
              layout="vertical"
              margin={{ top: 4, right: 8, left: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" horizontal={false} />
              <XAxis
                type="number"
                dataKey="value"
                tickFormatter={(v) => formatINRCompact(v)}
                tick={{ fill: "#6b7280", fontSize: 11 }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                type="category"
                dataKey="sector"
                tick={{ fill: "#9ca3af", fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                width={110}
              />
              <Tooltip
                contentStyle={{ background: "#1f2937", border: "1px solid #374151", borderRadius: 8 }}
                labelStyle={{ color: "#e5e7eb", fontSize: 12 }}
                formatter={(val, _name, item) => [
                  `${formatINRCompact(Number(val ?? 0))} (${(item?.payload as { pct?: number })?.pct?.toFixed(1) ?? "0"}%)`,
                  "Value",
                ]}
              />
              <Bar dataKey="value" radius={[0, 3, 3, 0]}>
                {sectors.map((entry: { pct: number }, index: number) => (
                  <Cell
                    key={index}
                    fill={entry.pct > NEUTRAL_TARGET_PCT ? "#f87171" : "#34d399"}
                    fillOpacity={0.8}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  )
}
