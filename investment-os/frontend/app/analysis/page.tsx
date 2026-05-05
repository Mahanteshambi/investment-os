import { TopBar } from "@/components/layout/TopBar"

export default function AnalysisPage() {
  return (
    <>
      <TopBar title="Analysis" />
      <main className="flex-1 p-6 flex items-center justify-center">
        <div className="text-center space-y-3">
          <p className="text-4xl">🤖</p>
          <h2 className="text-lg font-semibold text-gray-300">Agent Analysis — Phase 2</h2>
          <p className="text-sm text-gray-500 max-w-sm">
            Google ADK agents will power this page. Portfolio health, sector rotation, and rebalancing
            recommendations will appear here once agents are wired in.
          </p>
        </div>
      </main>
    </>
  )
}
