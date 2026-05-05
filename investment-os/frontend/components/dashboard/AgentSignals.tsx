"use client"

import { useEffect, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { getAgentSignals } from "@/lib/api"
import { relativeTime } from "@/lib/utils"
import type { AgentSignal } from "@/types"

const SIGNAL_STYLES: Record<string, { label: string; className: string }> = {
  bullish: { label: "BULLISH", className: "bg-emerald-900/60 text-emerald-400 border-emerald-800" },
  bearish: { label: "BEARISH", className: "bg-red-900/60 text-red-400 border-red-800" },
  neutral: { label: "NEUTRAL", className: "bg-gray-800 text-gray-400 border-gray-700" },
  action_needed: { label: "ACTION NEEDED", className: "bg-orange-900/60 text-orange-400 border-orange-800" },
}

export function AgentSignals() {
  const [mounted, setMounted] = useState(false)
  const { data: signals, isLoading } = useQuery({
    queryKey: ["agentSignals"],
    queryFn: getAgentSignals,
    refetchInterval: 120_000,
  })

  useEffect(() => {
    setMounted(true)
  }, [])

  return (
    <Card className="bg-gray-900 border-gray-800 h-full">
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <CardTitle className="text-sm text-gray-400">Agent Signals</CardTitle>
          <Badge variant="outline" className="text-xs border-gray-700 text-gray-600">Phase 2</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading ? (
          Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full bg-gray-800" />
          ))
        ) : !signals || signals.length === 0 ? (
          <p className="text-gray-600 text-sm py-4 text-center">
            No signals yet. Agents coming in Phase 2.
          </p>
        ) : (
          signals.map((s) => <SignalCard key={s.agent_name} signal={s} mounted={mounted} />)
        )}
      </CardContent>
    </Card>
  )
}

function SignalCard({ signal, mounted }: { signal: AgentSignal; mounted: boolean }) {
  const style = SIGNAL_STYLES[signal.signal_value] ?? SIGNAL_STYLES.neutral
  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-3 space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-gray-300">{signal.agent_name}</span>
        <Badge variant="outline" className={`text-[10px] px-1.5 py-0 ${style.className}`}>
          {style.label}
        </Badge>
      </div>
      <p className="text-xs text-gray-500 leading-relaxed">{signal.summary}</p>
      <p className="text-[10px] text-gray-700">{mounted ? relativeTime(signal.created_at) : "—"}</p>
    </div>
  )
}
