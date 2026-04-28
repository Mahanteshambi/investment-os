import { Suspense } from "react"
import { TopBar } from "@/components/layout/TopBar"
import { Skeleton } from "@/components/ui/skeleton"
import { IntelligenceDashboard } from "./IntelligenceDashboard"

export default function IntelligencePage() {
  return (
    <>
      <TopBar title="MF Intelligence & Monitoring" />
      <main className="flex-1 p-6 space-y-6 overflow-auto">
        <Suspense fallback={<Skeleton className="h-96 w-full bg-gray-900 rounded-xl" />}>
          <IntelligenceDashboard />
        </Suspense>
      </main>
    </>
  )
}
