"use client"

import { useQuery } from "@tanstack/react-query"
import { TopBar } from "@/components/layout/TopBar"
import { Skeleton } from "@/components/ui/skeleton"
import { SectorRotationHeader } from "@/components/sector-rotation/SectorRotationHeader"
import { SectorScoreChart } from "@/components/sector-rotation/SectorScoreChart"
import { SectorScoreTable } from "@/components/sector-rotation/SectorScoreTable"
import { ScoreHistoryChart } from "@/components/sector-rotation/ScoreHistoryChart"
import { ExitAlerts } from "@/components/sector-rotation/ExitAlerts"
import { getSectorRotation } from "@/lib/api"

export default function SectorRotationPage() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["sectorRotation"],
    queryFn: getSectorRotation,
    staleTime: 5 * 60 * 1000,
  })

  return (
    <>
      <TopBar title="Sector Rotation" />
      <main className="flex-1 p-6 space-y-6 overflow-auto">
        {isLoading && (
          <div className="space-y-4">
            <Skeleton className="h-36 w-full bg-gray-800" />
            <Skeleton className="h-80 w-full bg-gray-800" />
            <Skeleton className="h-96 w-full bg-gray-800" />
          </div>
        )}

        {isError && (
          <div className="flex items-center justify-center h-64 text-red-400 text-sm">
            Failed to load sector rotation data: {(error as Error).message}
          </div>
        )}

        {data && (
          <>
            <SectorRotationHeader data={data} />

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <SectorScoreChart scores={data.current_month.scores} />
              <ScoreHistoryChart history={data.history} />
            </div>

            <SectorScoreTable scores={data.current_month.scores} />

            <ExitAlerts
              exitAlerts={data.exit_alerts}
              watchCandidates={data.watch_candidates}
            />
          </>
        )}
      </main>
    </>
  )
}
