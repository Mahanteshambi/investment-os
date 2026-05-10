"use client"

import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { RefreshCw, TrendingUp, Zap, AlertTriangle } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { syncSectorRotation } from "@/lib/api"
import type { SectorRotation } from "@/types"

interface Props {
  data: SectorRotation
}

export function SectorRotationHeader({ data }: Props) {
  const qc = useQueryClient()
  const { current_month, _last_technical_sync } = data

  const mutation = useMutation({
    mutationFn: syncSectorRotation,
    onSuccess: (res) => {
      qc.setQueryData(["sectorRotation"], res.data)
    },
  })

  const activeEtf = current_month.active_sector_etf.replace("NSE:", "")
  const score = current_month.active_sector_score
  const macro = current_month.macro_context
  const fii = current_month.fii_dii_data

  const syncLabel = _last_technical_sync
    ? `Technical data refreshed ${new Date(_last_technical_sync).toLocaleDateString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}`
    : `Qualitative scores as of ${current_month.generated_date}`

  return (
    <div className="space-y-4">
      {/* Active sector + sync */}
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <p className="text-xs text-gray-500 uppercase tracking-wider">Active Sector — {current_month.month}</p>
          <div className="flex items-center gap-3">
            <span className="text-2xl font-bold text-white">{activeEtf}</span>
            <ScorePill score={score} />
            <span className="text-sm text-gray-400">{current_month.active_sector_allocation} allocation · ₹60K/mo</span>
          </div>
          <p className="text-xs text-gray-500 max-w-2xl">{current_month.rotation_decision}</p>
        </div>

        <div className="flex flex-col items-end gap-2">
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
          >
            <RefreshCw className={`h-4 w-4 ${mutation.isPending ? "animate-spin" : ""}`} />
            {mutation.isPending ? "Syncing…" : "Sync Technical Data"}
          </button>
          <p className="text-xs text-gray-600 text-right max-w-xs">{syncLabel}</p>
          {mutation.isError && (
            <p className="text-xs text-red-400 flex items-center gap-1">
              <AlertTriangle className="h-3 w-3" />
              {(mutation.error as Error).message}
            </p>
          )}
          {mutation.isSuccess && mutation.data.errors.length > 0 && (
            <p className="text-xs text-yellow-400">{mutation.data.errors.length} sector(s) failed — using cached scores</p>
          )}
        </div>
      </div>

      {/* Macro strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MacroCard
          label="DXY"
          value={macro.dxy.toFixed(2)}
          sub={macro.dxy < 100 ? "Bullish for India" : "Headwind"}
          positive={macro.dxy < 100}
        />
        <MacroCard
          label="Brent Crude"
          value={`$${macro.brent_crude_usd.toFixed(0)}`}
          sub={macro.brent_crude_usd > 90 ? "High — E&P boost" : "Manageable"}
          positive={macro.brent_crude_usd > 90}
          positiveColor="text-amber-400"
        />
        <MacroCard
          label="FII/DII"
          value={`${fii.fii_stance} / ${fii.dii_stance}`}
          sub={`FII ₹${fii.fii_net_crore.toFixed(0)} Cr · ${fii.date}`}
          positive={fii.fii_stance === "BUYER"}
        />
        <MacroCard
          label="CAPE"
          value={`${macro.cape_ratio}`}
          sub={macro.cape_ratio > 30 ? "Elevated — prefer value" : "Moderate"}
          positive={macro.cape_ratio <= 30}
        />
      </div>
    </div>
  )
}

function ScorePill({ score }: { score: number }) {
  const color = score >= 7 ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
    : score >= 5 ? "bg-yellow-500/20 text-yellow-400 border-yellow-500/30"
    : "bg-red-500/20 text-red-400 border-red-500/30"
  return (
    <span className={`px-2.5 py-0.5 rounded-full text-sm font-semibold border ${color}`}>
      {score.toFixed(1)} / 10
    </span>
  )
}

function MacroCard({
  label, value, sub, positive, positiveColor,
}: {
  label: string; value: string; sub: string; positive: boolean; positiveColor?: string
}) {
  const color = positiveColor ?? (positive ? "text-emerald-400" : "text-red-400")
  return (
    <Card className="bg-gray-900 border-gray-800">
      <CardContent className="p-3">
        <p className="text-xs text-gray-500 mb-0.5">{label}</p>
        <p className={`text-sm font-semibold ${color}`}>{value}</p>
        <p className="text-xs text-gray-600">{sub}</p>
      </CardContent>
    </Card>
  )
}
