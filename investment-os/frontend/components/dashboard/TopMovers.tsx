"use client"

import { useQuery } from "@tanstack/react-query"
import { Skeleton } from "@/components/ui/skeleton"

export function TopMovers() {
  const { data: holdings, isLoading } = useQuery({
    queryKey: ["holdings"],
    queryFn: async () => {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/holdings`)
      if (!res.ok) throw new Error("Failed to fetch")
      return res.json()
    },
  })

  if (isLoading) return <Skeleton className="h-full w-full bg-gray-800" />

  // Sort by highest absolute PnL change (just using unrealized_pnl for now as proxy)
  const topMovers = [...(holdings || [])]
    .sort((a: any, b: any) => Math.abs(b.unrealized_pnl_pct || 0) - Math.abs(a.unrealized_pnl_pct || 0))
    .slice(0, 5)

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 h-full">
      <h2 className="text-sm font-medium text-gray-400 mb-4">Top 5 Movers</h2>
      <div className="space-y-3">
        <div className="grid grid-cols-3 text-xs text-gray-500 pb-2 border-b border-gray-800">
          <div>Asset</div>
          <div className="text-right">Price</div>
          <div className="text-right">Change %</div>
        </div>
        {topMovers.map((asset: any) => {
          const isPositive = asset.unrealized_pnl_pct >= 0
          return (
            <div key={asset.id} className="grid grid-cols-3 text-sm items-center">
              <div className="text-gray-300 truncate pr-2">{asset.asset_name}</div>
              <div className="text-right text-gray-400">₹{asset.current_price?.toFixed(2) || "-"}</div>
              <div className={`text-right ${isPositive ? "text-green-400" : "text-red-400"}`}>
                {isPositive ? "+" : ""}{asset.unrealized_pnl_pct?.toFixed(2) || "0.00"}%
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
