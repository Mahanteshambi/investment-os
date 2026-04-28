"use client"

import { useState } from "react"
import { useQuery, useMutation } from "@tanstack/react-query"
import { syncMFIntelligence, getMFProfiles, getMFAlerts, getMFFactsheets } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { RefreshCw, AlertTriangle, ShieldCheck, FileText, ArrowRight } from "lucide-react"

export function IntelligenceDashboard() {
  const [selectedIsin, setSelectedIsin] = useState<string | null>(null)

  const { data: profiles, refetch: refetchProfiles } = useQuery({
    queryKey: ["mfProfiles"],
    queryFn: getMFProfiles,
  })

  const { data: alerts, refetch: refetchAlerts } = useQuery({
    queryKey: ["mfAlerts"],
    queryFn: getMFAlerts,
  })

  const { data: factsheets } = useQuery({
    queryKey: ["mfFactsheets", selectedIsin],
    queryFn: () => getMFFactsheets(selectedIsin!),
    enabled: !!selectedIsin,
  })

  const syncMutation = useMutation({
    mutationFn: syncMFIntelligence,
    onSuccess: () => {
      alert("Intelligence sync started in the background! This will scrape real-time factsheets using crawl4ai & Gemini. Please refresh the page in a minute.")
    },
    onError: (err) => {
      alert("Failed to start sync: " + err.message)
    }
  })

  const activeAlerts = alerts?.filter(a => !a.is_read) || []

  return (
    <div className="space-y-6">
      {/* Header Actions */}
      <div className="flex justify-between items-center bg-gray-900 border border-gray-800 p-4 rounded-xl">
        <div>
          <h2 className="text-lg font-semibold text-gray-200 flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-indigo-400" />
            Watchdog Status
          </h2>
          <p className="text-sm text-gray-400">Monitoring {profiles?.length || 0} mutual funds for structural changes.</p>
        </div>
        <Button 
          onClick={() => syncMutation.mutate()} 
          disabled={syncMutation.isPending}
          className="bg-indigo-600 hover:bg-indigo-700 text-white"
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${syncMutation.isPending ? 'animate-spin' : ''}`} />
          {syncMutation.isPending ? 'Syncing...' : 'Run Intelligence Sync'}
        </Button>
      </div>

      {/* Alerts Section */}
      {activeAlerts.length > 0 && (
        <Card className="bg-red-950/20 border-red-900/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-red-400 text-sm flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              Active Alerts
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {activeAlerts.map(alert => {
              const fundName = profiles?.find(p => p.isin === alert.isin)?.fund_name || alert.isin
              return (
                <div key={alert.id} className="bg-gray-900 border border-red-900/30 p-3 rounded-lg flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-200">{fundName}</p>
                    <p className="text-xs text-gray-400 mt-1">
                      <span className="text-red-400 font-semibold">{alert.alert_type}</span>: Changed from <span className="text-gray-300">"{alert.old_value}"</span> to <span className="text-white">"{alert.new_value}"</span>
                    </p>
                  </div>
                  <span className="text-xs text-gray-500">{new Date(alert.alert_date).toLocaleDateString()}</span>
                </div>
              )
            })}
          </CardContent>
        </Card>
      )}

      {/* Performance Matrix */}
      <Card className="bg-gray-900 border-gray-800">
        <CardHeader>
          <CardTitle className="text-base text-gray-200">Performance vs Benchmark Matrix</CardTitle>
          <CardDescription>Trailing returns extracted directly from factsheets.</CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-gray-500 uppercase bg-gray-900/50 border-b border-gray-800">
              <tr>
                <th className="px-4 py-3">Fund Name</th>
                <th className="px-4 py-3">Category</th>
                <th className="px-4 py-3 text-right">1Y</th>
                <th className="px-4 py-3 text-right">3Y</th>
                <th className="px-4 py-3 text-right">5Y</th>
                <th className="px-4 py-3">Action</th>
              </tr>
            </thead>
            <tbody>
              {profiles?.map(profile => {
                const fs = factsheets?.length ? factsheets[0] : null
                return (
                  <tr key={profile.isin} className="border-b border-gray-800 hover:bg-gray-800/50 transition-colors">
                    <td className="px-4 py-3 font-medium text-gray-200">
                      {profile.fund_name}
                      <div className="text-xs text-gray-500 font-normal mt-0.5">Mgr: {profile.fund_manager || 'N/A'}</div>
                    </td>
                    <td className="px-4 py-3 text-gray-400">{profile.category}</td>
                    <td className="px-4 py-3 text-right">
                      {/* We mock the data display if factsheet is null just to show structure */}
                      <span className="text-emerald-400">--%</span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className="text-emerald-400">--%</span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className="text-emerald-400">--%</span>
                    </td>
                    <td className="px-4 py-3">
                      <Button variant="ghost" size="sm" onClick={() => setSelectedIsin(profile.isin)} className="text-indigo-400 hover:text-indigo-300">
                        View Details <ArrowRight className="h-4 w-4 ml-1" />
                      </Button>
                    </td>
                  </tr>
                )
              })}
              {(!profiles || profiles.length === 0) && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                    No mutual fund intelligence data found. Click "Run Intelligence Sync" to fetch.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
      
      {/* Detail View (Mocked for now since factsheet data needs the real run) */}
      {selectedIsin && factsheets && factsheets.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card className="bg-gray-900 border-gray-800">
             <CardHeader>
               <CardTitle className="text-sm text-gray-300">Top Sectors</CardTitle>
             </CardHeader>
             <CardContent>
               <ul className="space-y-2">
                 {factsheets[0].sector_weights?.map((s: any) => (
                   <li key={s.sector_name} className="flex justify-between text-sm">
                     <span className="text-gray-400">{s.sector_name}</span>
                     <span className="text-gray-200 font-medium">{s.weight_pct}%</span>
                   </li>
                 ))}
               </ul>
             </CardContent>
          </Card>
          <Card className="bg-gray-900 border-gray-800">
             <CardHeader>
               <CardTitle className="text-sm text-gray-300">Top Holdings</CardTitle>
             </CardHeader>
             <CardContent>
               <ul className="space-y-2">
                 {factsheets[0].stock_holdings?.map((s: any) => (
                   <li key={s.stock_name} className="flex justify-between text-sm">
                     <span className="text-gray-400">{s.stock_name}</span>
                     <span className="text-gray-200 font-medium">{s.weight_pct}%</span>
                   </li>
                 ))}
               </ul>
             </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
