"use client"

import { useQuery } from "@tanstack/react-query"
import { Skeleton } from "@/components/ui/skeleton"
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts"
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

export function PlatformExposure() {
  const { data: holdings, isLoading } = useQuery({
    queryKey: ["holdings"],
    queryFn: async () => {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/holdings`)
      if (!res.ok) throw new Error("Failed to fetch")
      return res.json()
    },
  })

  if (isLoading) return <Skeleton className="h-full w-full bg-gray-900 border border-gray-800 rounded-xl" />

  // Group by platform, then by asset_class
  const platformData: Record<string, any> = {}
  
  ;(holdings || []).forEach((h: any) => {
    // If platform is empty or "Sheets", categorize it as "Other" instead of treating the data source as a platform
    let p = h.platform
    if (!p || p.toLowerCase() === "sheets" || p.toLowerCase() === "kite") {
      p = "Other"
    }
    
    const cls = h.asset_class || "other"
    
    if (!platformData[p]) {
      platformData[p] = { platform: p, total: 0 }
    }
    
    platformData[p][cls] = (platformData[p][cls] || 0) + (h.current_value || 0)
    platformData[p].total += (h.current_value || 0)
  })

  const chartData = Object.values(platformData).sort((a: any, b: any) => b.total - a.total)

  // Get unique asset classes used across all platforms
  const assetClasses = Array.from(
    new Set((holdings || []).map((h: any) => h.asset_class).filter(Boolean))
  ) as string[]

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 h-full flex flex-col">
      <h2 className="text-sm font-medium text-gray-400 mb-4">Distribution by Platform & Asset</h2>
      <div className="flex-1 w-full min-h-[250px]">
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 20 }}>
              <XAxis 
                dataKey="platform" 
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
                formatter={(value: number, name: string) => [
                  `₹${value.toLocaleString("en-IN")}`, 
                  CLASS_LABELS[name] || name
                ]}
              />
              {assetClasses.map((cls) => (
                <Bar 
                  key={cls} 
                  dataKey={cls} 
                  stackId="a" 
                  fill={CLASS_COLORS[cls] || "#6b7280"} 
                  name={cls}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-full flex items-center justify-center text-gray-600 text-sm">
            No platform data available.
          </div>
        )}
      </div>
    </div>
  )
}
