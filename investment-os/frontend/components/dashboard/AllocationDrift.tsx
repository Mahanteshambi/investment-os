"use client"

import { useQuery } from "@tanstack/react-query"
import { Skeleton } from "@/components/ui/skeleton"

export function AllocationDrift() {
  const { data: portfolio, isLoading } = useQuery({
    queryKey: ["portfolio-summary"],
    queryFn: async () => {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/portfolio`)
      if (!res.ok) throw new Error("Failed to fetch")
      return res.json()
    },
  })

  if (isLoading) return <Skeleton className="h-full w-full bg-gray-800" />

  // Placeholder data mapping; ideally this compares against target_allocation.json
  const driftData = [
    { label: "Equity", current: portfolio?.equity_pct || 0, target: 40 },
    { label: "Mid/Small", current: 10, target: 15 }, // Mocked example
    { label: "Gold", current: portfolio?.gold_pct || 0, target: 15 },
    { label: "Debt/Cash", current: (portfolio?.debt_pct || 0) + (portfolio?.cash_pct || 0), target: 5 },
  ]

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 h-full">
      <h2 className="text-sm font-medium text-gray-400 mb-4">Allocation Drift (Current vs Target)</h2>
      <div className="space-y-4">
        {driftData.map((item) => {
          const drift = item.current - item.target
          const isOverweight = drift > 0
          const colorClass = isOverweight ? "bg-red-500" : "bg-green-500"

          return (
            <div key={item.label}>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-gray-300">{item.label}</span>
                <span className="text-gray-500">
                  {item.current.toFixed(1)}% / {item.target}%
                  <span className={`ml-2 ${isOverweight ? "text-red-400" : "text-green-400"}`}>
                    ({drift > 0 ? "+" : ""}{drift.toFixed(1)}%)
                  </span>
                </span>
              </div>
              <div className="h-2 w-full bg-gray-800 rounded-full overflow-hidden flex">
                <div
                  className={`h-full ${colorClass}`}
                  style={{ width: `${Math.min(item.current, 100)}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
