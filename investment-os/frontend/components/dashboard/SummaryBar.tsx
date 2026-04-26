"use client"

import { useEffect, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { TrendingUp, TrendingDown, Clock } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { getPortfolioSummary } from "@/lib/api"
import { formatINR, formatINRCompact, formatPct, relativeTime } from "@/lib/utils"

export function SummaryBar() {
  const [mounted, setMounted] = useState(false)
  const { data, isLoading } = useQuery({
    queryKey: ["portfolioSummary"],
    queryFn: getPortfolioSummary,
    refetchInterval: 60_000,
  })

  useEffect(() => {
    setMounted(true)
  }, [])

  if (isLoading || !data) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <Card key={i} className="bg-gray-900 border-gray-800">
            <CardContent className="p-4 space-y-2">
              <Skeleton className="h-3 w-20 bg-gray-800" />
              <Skeleton className="h-6 w-28 bg-gray-800" />
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  const pnlPositive = data.total_pnl >= 0
  const dayPositive = data.day_pnl >= 0

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
      <MetricCard
        label="Total Value"
        value={formatINR(data.total_value)}
        sub={formatINRCompact(data.total_value)}
      />
      <MetricCard
        label="Day P&L"
        value={formatINR(data.day_pnl)}
        sub={formatPct(data.day_pnl_pct)}
        positive={dayPositive}
        icon={dayPositive ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
      />
      <MetricCard
        label="Overall P&L"
        value={formatINR(data.total_pnl)}
        sub={formatPct(data.total_pnl_pct)}
        positive={pnlPositive}
        icon={pnlPositive ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
      />
      <MetricCard
        label="XIRR"
        value={data.xirr !== null ? `${data.xirr.toFixed(2)}%` : "—"}
        sub="Annualised return"
        tooltip="Extended Internal Rate of Return — accounts for timing of all investments"
      />
      <MetricCard
        label="Last Synced"
        value={mounted ? relativeTime(data.last_synced) : "—"}
        icon={<Clock className="h-4 w-4 text-gray-500" />}
      />
    </div>
  )
}

interface MetricCardProps {
  label: string
  value: string
  sub?: string
  positive?: boolean
  icon?: React.ReactNode
  tooltip?: string
}

function MetricCard({ label, value, sub, positive, icon, tooltip }: MetricCardProps) {
  const valueColor =
    positive === undefined
      ? "text-white"
      : positive
        ? "text-emerald-400"
        : "text-red-400"

  return (
    <Card className="bg-gray-900 border-gray-800">
      <CardContent className="p-4">
        <p className="text-xs text-gray-500 mb-1">{label}</p>
        <div className="flex items-center gap-1.5">
          {icon && <span className={valueColor}>{icon}</span>}
          <span className={`text-lg font-semibold ${valueColor}`} title={tooltip}>
            {value}
          </span>
        </div>
        {sub && <p className="text-xs text-gray-500 mt-0.5">{sub}</p>}
      </CardContent>
    </Card>
  )
}
