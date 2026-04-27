import { Suspense } from "react"
import { TopBar } from "@/components/layout/TopBar"
import { SummaryBar } from "@/components/dashboard/SummaryBar"
import { AllocationBar } from "@/components/dashboard/AllocationBar"
import { AllocationDrift } from "@/components/dashboard/AllocationDrift"
import { TopMovers } from "@/components/dashboard/TopMovers"
import { HoldingsTable } from "@/components/holdings/HoldingsTable"
import { Skeleton } from "@/components/ui/skeleton"

export default function DashboardPage() {
  return (
    <>
      <TopBar title="Dashboard" />
      <main className="flex-1 p-6 space-y-6 overflow-auto">
        <Suspense fallback={<Skeleton className="h-24 w-full bg-gray-800" />}>
          <SummaryBar />
        </Suspense>

        <div className="w-full">
          <Suspense fallback={<Skeleton className="h-80 w-full bg-gray-800" />}>
            <AllocationBar />
          </Suspense>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="col-span-1">
            <Suspense fallback={<Skeleton className="h-80 w-full bg-gray-800" />}>
              <AllocationDrift />
            </Suspense>
          </div>
          <div className="col-span-1">
            <Suspense fallback={<Skeleton className="h-80 w-full bg-gray-800" />}>
              <TopMovers />
            </Suspense>
          </div>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <h2 className="text-sm font-medium text-gray-400 mb-4">Holdings</h2>
          <Suspense fallback={<Skeleton className="h-48 w-full bg-gray-800" />}>
            <HoldingsTable />
          </Suspense>
        </div>
      </main>
    </>
  )
}
