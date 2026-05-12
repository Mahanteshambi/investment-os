"use client"

import { useEffect, useState } from "react"
import { TopBar } from "@/components/layout/TopBar"
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts"
import { Globe, Newspaper, TrendingUp, DollarSign, Droplets, RefreshCw } from "lucide-react"

type MacroData = {
  date: string
  DXY?: number
  Brent_Crude?: number
  US_10Y?: number
}

type NewsArticle = {
  id: string
  date: string
  title: string
  source: string
  description: string
}

export default function WorldViewPage() {
  const [macroData, setMacroData] = useState<MacroData[]>([])
  const [news, setNews] = useState<NewsArticle[]>([])
  const [kiteData, setKiteData] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)

  const fetchData = async () => {
    try {
      const [macroRes, newsRes, kiteRes] = await Promise.all([
        fetch("http://localhost:8000/api/world-view/macro"),
        fetch("http://localhost:8000/api/world-view/news"),
        fetch("http://localhost:8000/api/world-view/kite")
      ])
      const mData = await macroRes.json()
      const nData = await newsRes.json()
      const kData = await kiteRes.json()
      setMacroData(mData)
      setNews(nData)
      setKiteData(kData)
    } catch (error) {
      console.error("Failed to fetch world data", error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const handleSync = async () => {
    setSyncing(true)
    try {
      await fetch("http://localhost:8000/api/world-view/sync", { method: "POST" })
      // Since it's a background task, we just wait a bit and refetch
      setTimeout(fetchData, 5000)
    } finally {
      setTimeout(() => setSyncing(false), 2000)
    }
  }

  return (
    <>
      <TopBar title="World View" />
      <main className="flex-1 overflow-y-auto p-6 bg-gray-950">
        <div className="max-w-6xl mx-auto space-y-6">
          
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-semibold text-white flex items-center gap-2">
                <Globe className="w-6 h-6 text-indigo-400" />
                Macro Environment
              </h1>
              <p className="text-gray-400 text-sm mt-1">
                Global economic indicators that drive sector rotation and asset allocation.
              </p>
            </div>
            <button 
              onClick={handleSync}
              disabled={syncing}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${syncing ? 'animate-spin' : ''}`} />
              {syncing ? 'Syncing...' : 'Sync Data'}
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <MetricCard title="US Dollar Index (DXY)" value={macroData[macroData.length - 1]?.DXY?.toFixed(2) || "—"} icon={DollarSign} trend="Inverse to Emerging Markets" />
            <MetricCard title="Brent Crude Oil" value={`$${macroData[macroData.length - 1]?.Brent_Crude?.toFixed(2) || "—"}`} icon={Droplets} trend="Impacts India CAD" />
            <MetricCard title="US 10-Year Yield" value={`${macroData[macroData.length - 1]?.US_10Y?.toFixed(2) || "—"}%`} icon={TrendingUp} trend="Drives FII Flows" />
          </div>

          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <h2 className="text-lg font-medium text-white mb-4">30-Day Macro Trends</h2>
            {loading ? (
              <div className="h-72 flex items-center justify-center text-gray-500">Loading chart...</div>
            ) : (
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={macroData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} />
                    <XAxis 
                      dataKey="date" 
                      stroke="#9CA3AF" 
                      fontSize={12} 
                      tickFormatter={(val) => new Date(val).toLocaleDateString(undefined, {month: 'short', day: 'numeric'})}
                    />
                    <YAxis yAxisId="left" stroke="#9CA3AF" fontSize={12} domain={['auto', 'auto']} />
                    <YAxis yAxisId="right" orientation="right" stroke="#9CA3AF" fontSize={12} domain={['auto', 'auto']} />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#111827', borderColor: '#374151', color: '#F3F4F6' }}
                      labelStyle={{ color: '#9CA3AF', marginBottom: '4px' }}
                    />
                    <Legend />
                    <Line yAxisId="left" type="monotone" dataKey="DXY" stroke="#818CF8" strokeWidth={2} dot={false} name="DXY" />
                    <Line yAxisId="left" type="monotone" dataKey="Brent_Crude" stroke="#F87171" strokeWidth={2} dot={false} name="Brent ($)" />
                    <Line yAxisId="right" type="monotone" dataKey="US_10Y" stroke="#34D399" strokeWidth={2} dot={false} name="US 10Y Yield (%)" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <h2 className="text-lg font-medium text-white mb-4">Kite Historical Performance (Watchlist)</h2>
            {loading ? (
              <div className="h-72 flex items-center justify-center text-gray-500">Loading chart...</div>
            ) : kiteData.length === 0 ? (
              <div className="h-72 flex items-center justify-center text-gray-500">No Kite data found. Click Sync.</div>
            ) : (
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={kiteData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} />
                    <XAxis 
                      dataKey="date" 
                      stroke="#9CA3AF" 
                      fontSize={12} 
                      tickFormatter={(val) => new Date(val).toLocaleDateString(undefined, {month: 'short', day: 'numeric'})}
                    />
                    <YAxis stroke="#9CA3AF" fontSize={12} domain={['auto', 'auto']} />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#111827', borderColor: '#374151', color: '#F3F4F6' }}
                      labelStyle={{ color: '#9CA3AF', marginBottom: '4px' }}
                    />
                    <Legend />
                    <Line type="monotone" dataKey="NIFTYBEES" stroke="#FBBF24" strokeWidth={2} dot={false} name="NIFTYBEES" />
                    <Line type="monotone" dataKey="GOLDBEES" stroke="#60A5FA" strokeWidth={2} dot={false} name="GOLDBEES" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          <div>
            <h2 className="text-xl font-semibold text-white flex items-center gap-2 mb-4">
              <Newspaper className="w-5 h-5 text-indigo-400" />
              Latest Market Intelligence
            </h2>
            <div className="grid grid-cols-1 gap-4">
              {loading ? (
                <div className="text-gray-500">Loading news...</div>
              ) : news.length === 0 ? (
                <div className="text-gray-500 bg-gray-900 border border-gray-800 rounded-xl p-6 text-center">
                  No news fetched yet. Click "Sync Data" to pull latest headlines.
                </div>
              ) : (
                news.map((item) => (
                  <div key={item.id} className="bg-gray-900 border border-gray-800 rounded-xl p-4 hover:bg-gray-800/50 transition-colors">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <h3 className="text-gray-200 font-medium leading-snug">{item.title}</h3>
                        <p className="text-gray-400 text-sm mt-1.5 line-clamp-2">{item.description}</p>
                      </div>
                      <div className="text-right shrink-0">
                        <span className="inline-block px-2.5 py-1 bg-gray-800 text-gray-300 text-xs rounded-md border border-gray-700">
                          {item.source || "News"}
                        </span>
                        <p className="text-gray-500 text-xs mt-2">
                          {new Date(item.date).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

        </div>
      </main>
    </>
  )
}

function MetricCard({ title, value, icon: Icon, trend }: { title: string, value: string, icon: any, trend: string }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <div className="flex items-center gap-3 text-gray-400 mb-3">
        <Icon className="w-5 h-5" />
        <h3 className="text-sm font-medium">{title}</h3>
      </div>
      <p className="text-3xl font-semibold text-white">{value}</p>
      <p className="text-xs text-gray-500 mt-2">{trend}</p>
    </div>
  )
}
