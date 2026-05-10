"use client"

import { AlertTriangle, CheckCircle, Eye } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { ExitAlert, WatchCandidate } from "@/types"

interface Props {
  exitAlerts: ExitAlert[]
  watchCandidates?: WatchCandidate[]
}

export function ExitAlerts({ exitAlerts, watchCandidates }: Props) {
  const active = exitAlerts.filter((a) => a.status !== "EXECUTED")
  const executed = exitAlerts.filter((a) => a.status === "EXECUTED")

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Exit alerts */}
      <Card className="bg-gray-900 border-gray-800">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm text-gray-400 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-yellow-400" />
            Exit Alerts
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {active.length === 0 && executed.length === 0 && (
            <p className="text-sm text-gray-600">No active exit alerts.</p>
          )}
          {active.map((alert) => (
            <div key={alert.symbol} className="border border-yellow-500/30 bg-yellow-500/5 rounded-lg p-3">
              <div className="flex items-center justify-between mb-1">
                <span className="font-semibold text-yellow-400 text-sm">{alert.symbol}</span>
                <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded-full">
                  {alert.alert_type.replace(/_/g, " ")}
                </span>
              </div>
              {alert.consecutive_months && (
                <p className="text-xs text-gray-400 mb-1">
                  {alert.consecutive_months} consecutive months below score 4
                </p>
              )}
              {alert.action && (
                <p className="text-xs text-gray-300 leading-relaxed">{alert.action}</p>
              )}
              {alert.conviction_note && (
                <p className="text-xs text-gray-500 mt-1 italic">{alert.conviction_note}</p>
              )}
            </div>
          ))}
          {executed.map((alert) => (
            <div key={alert.symbol} className="border border-gray-700/30 bg-gray-800/20 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-1">
                <CheckCircle className="h-3.5 w-3.5 text-emerald-500" />
                <span className="font-semibold text-gray-400 text-sm line-through">{alert.symbol}</span>
                <span className="text-xs text-emerald-500">EXECUTED</span>
              </div>
              <p className="text-xs text-gray-600">{alert.alert_type.replace(/_/g, " ")}</p>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Watch candidates */}
      <Card className="bg-gray-900 border-gray-800">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm text-gray-400 flex items-center gap-2">
            <Eye className="h-4 w-4 text-indigo-400" />
            Watch Candidates
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {(!watchCandidates || watchCandidates.length === 0) && (
            <p className="text-sm text-gray-600">No watch candidates.</p>
          )}
          {watchCandidates?.map((wc) => (
            <div key={wc.etf} className="border border-indigo-500/20 bg-indigo-500/5 rounded-lg p-3">
              <div className="flex items-center justify-between mb-1">
                <span className="font-semibold text-indigo-400 text-sm">{wc.etf.replace("NSE:", "")}</span>
                <span className="text-xs font-semibold text-white bg-indigo-600/40 px-2 py-0.5 rounded-full">
                  {wc.score.toFixed(1)}
                </span>
              </div>
              <p className="text-xs text-gray-400 mb-1 leading-relaxed">{wc.trigger_condition}</p>
              <p className="text-xs text-gray-500 italic">{wc.note}</p>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
