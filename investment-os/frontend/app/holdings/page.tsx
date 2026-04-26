import { TopBar } from "@/components/layout/TopBar"
import { HoldingsTable } from "@/components/holdings/HoldingsTable"

export default function HoldingsPage() {
  return (
    <>
      <TopBar title="Holdings" />
      <main className="flex-1 p-6">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <HoldingsTable />
        </div>
      </main>
    </>
  )
}
