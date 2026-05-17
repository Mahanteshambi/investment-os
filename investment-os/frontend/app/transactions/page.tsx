"use client"

import { useState, useRef } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from "recharts"
import {
  getTransactions, getTransactionSummary, getDeploymentSeries, bulkImportTransactions
} from "@/lib/api"
import type { Transaction, DeploymentPoint, TransactionIn } from "@/types"

// ── Bucket colours ───────────────────────────────────────────────────────────
const BUCKET_COLORS: Record<string, string> = {
  "Large Cap":    "#6366f1",
  "Mid/Small":    "#8b5cf6",
  "Sector":       "#f59e0b",
  "Gold":         "#eab308",
  "International":"#06b6d4",
  "Debt":         "#22c55e",
  "Other":        "#94a3b8",
  "MF":           "#ec4899",
}

const BUCKETS = Object.keys(BUCKET_COLORS)

// ── Helpers ──────────────────────────────────────────────────────────────────
function fmt(n: number | null | undefined, decimals = 0) {
  if (n == null) return "—"
  return new Intl.NumberFormat("en-IN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n)
}

function fmtINR(n: number | null | undefined) {
  if (n == null) return "—"
  if (Math.abs(n) >= 1_00_000) return `₹${(n / 1_00_000).toFixed(2)}L`
  return `₹${fmt(n)}`
}

// ── Deployment chart data transformation ─────────────────────────────────────
function buildChartData(series: DeploymentPoint[]): Record<string, number | string>[] {
  // Group by date, pivot buckets into columns
  const byDate: Record<string, Record<string, number>> = {}
  for (const pt of series) {
    if (!byDate[pt.date]) byDate[pt.date] = {}
    byDate[pt.date][pt.bucket] = (byDate[pt.date][pt.bucket] || 0) + pt.cumulative
  }
  return Object.entries(byDate)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, buckets]) => ({ date, ...buckets }))
}

// ── CSV parser (Zerodha Console P&L format) ──────────────────────────────────
function parseZerodhaCsv(text: string): TransactionIn[] {
  const lines = text.split("\n").map(l => l.trim()).filter(Boolean)
  if (lines.length < 2) return []
  const header = lines[0].split(",").map(h => h.trim().toLowerCase().replace(/\s+/g, "_"))
  const results: TransactionIn[] = []

  for (const line of lines.slice(1)) {
    const cols = line.split(",").map(c => c.trim().replace(/^"|"$/g, ""))
    const row: Record<string, string> = {}
    header.forEach((h, i) => { row[h] = cols[i] || "" })

    const ticker = row["symbol"] || row["tradingsymbol"] || row["scrip"] || ""
    const txnType = (row["trade_type"] || row["type"] || "buy").toLowerCase()
    const qty = parseFloat(row["quantity"] || row["qty"] || "0")
    const price = parseFloat(row["price"] || row["avg_price"] || "0")
    const rawDate = row["trade_date"] || row["date"] || ""

    // Parse date — supports DD-MM-YYYY and YYYY-MM-DD
    let txnDate = rawDate
    if (/^\d{2}-\d{2}-\d{4}/.test(rawDate)) {
      const [d, m, y] = rawDate.split("-")
      txnDate = `${y}-${m}-${d}`
    }

    if (!ticker || !txnDate || qty === 0) continue

    results.push({
      transaction_date: txnDate,
      asset_name: ticker,
      ticker,
      asset_class: "etf",
      transaction_type: txnType.includes("sell") ? "sell" : "buy",
      quantity: qty,
      price,
      amount: qty * price,
      fees: parseFloat(row["charges"] || row["brokerage"] || "0"),
      source: "zerodha_csv",
      exchange: row["exchange"] || "NSE",
    })
  }
  return results
}

// ── Summary cards ─────────────────────────────────────────────────────────────
function SummaryCards() {
  const { data } = useQuery({ queryKey: ["txnSummary"], queryFn: getTransactionSummary })
  if (!data) return null
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      {[
        { label: "Total Deployed", value: fmtINR(data.total_deployed), sub: `${data.total_buys} buys` },
        { label: "Total Redeemed", value: fmtINR(data.total_redeemed), sub: `${data.total_sells} sells` },
        { label: "Net Deployed", value: fmtINR(data.net_deployed), sub: "buy − sell" },
        { label: "Active Since", value: data.first_trade ?? "—", sub: `last: ${data.last_trade ?? "—"}` },
      ].map(c => (
        <div key={c.label} className="bg-gray-900 rounded-xl p-4 border border-gray-800">
          <p className="text-xs text-gray-400 mb-1">{c.label}</p>
          <p className="text-xl font-semibold text-white">{c.value}</p>
          <p className="text-xs text-gray-500 mt-0.5">{c.sub}</p>
        </div>
      ))}
    </div>
  )
}

// ── Deployment area chart ─────────────────────────────────────────────────────
function DeploymentChart() {
  const { data: series = [] } = useQuery({
    queryKey: ["deploymentSeries"],
    queryFn: getDeploymentSeries,
  })

  if (!series.length) {
    return (
      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 mb-6 flex items-center justify-center h-48 text-gray-500 text-sm">
        No deployment data yet — import trades or sync Kite.
      </div>
    )
  }

  const chartData = buildChartData(series)
  const activeBuckets = BUCKETS.filter(b => series.some(s => s.bucket === b))

  return (
    <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 mb-6">
      <h2 className="text-sm font-medium text-gray-300 mb-4">Cumulative Deployment by Bucket</h2>
      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={chartData} margin={{ top: 4, right: 16, bottom: 0, left: 0 }}>
          <defs>
            {activeBuckets.map(b => (
              <linearGradient key={b} id={`grad-${b}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={BUCKET_COLORS[b]} stopOpacity={0.3} />
                <stop offset="95%" stopColor={BUCKET_COLORS[b]} stopOpacity={0} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#6b7280" }} tickLine={false} />
          <YAxis
            tick={{ fontSize: 11, fill: "#6b7280" }}
            tickFormatter={v => `₹${(v / 1000).toFixed(0)}K`}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            contentStyle={{ background: "#111827", border: "1px solid #374151", borderRadius: 8 }}
            labelStyle={{ color: "#9ca3af", fontSize: 12 }}
            formatter={(v: number, name: string) => [fmtINR(v), name]}
          />
          <Legend wrapperStyle={{ fontSize: 12, color: "#9ca3af" }} />
          {activeBuckets.map(b => (
            <Area
              key={b}
              type="monotone"
              dataKey={b}
              stackId="1"
              stroke={BUCKET_COLORS[b]}
              fill={`url(#grad-${b})`}
              strokeWidth={1.5}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── Transaction table ─────────────────────────────────────────────────────────
function TransactionTable({ filters }: {
  filters: { ticker: string; type: string; bucket: string }
}) {
  const { data: txns = [], isLoading } = useQuery({
    queryKey: ["transactions", filters],
    queryFn: () => getTransactions({
      ticker: filters.ticker || undefined,
      transaction_type: filters.type || undefined,
      bucket: filters.bucket || undefined,
    }),
  })

  if (isLoading) return <div className="text-gray-500 text-sm py-8 text-center">Loading…</div>
  if (!txns.length) return <div className="text-gray-500 text-sm py-8 text-center">No transactions match filters.</div>

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-800">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-800 bg-gray-900">
            {["Date", "Symbol", "Type", "Qty", "Price", "Amount", "Bucket", "Source"].map(h => (
              <th key={h} className="px-4 py-3 text-left text-xs font-medium text-gray-400">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {txns.map(t => (
            <tr key={t.id} className="border-b border-gray-800/50 hover:bg-gray-900/60 transition-colors">
              <td className="px-4 py-3 text-gray-300 whitespace-nowrap">{t.transaction_date}</td>
              <td className="px-4 py-3 font-medium text-white">{t.ticker || t.asset_name}</td>
              <td className="px-4 py-3">
                <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                  t.transaction_type === "buy"
                    ? "bg-emerald-900/50 text-emerald-400"
                    : "bg-red-900/50 text-red-400"
                }`}>
                  {t.transaction_type.toUpperCase()}
                </span>
              </td>
              <td className="px-4 py-3 text-gray-300 text-right">{fmt(t.quantity, 0)}</td>
              <td className="px-4 py-3 text-gray-300 text-right">₹{fmt(t.price, 2)}</td>
              <td className="px-4 py-3 text-gray-300 text-right font-medium">{fmtINR(t.amount)}</td>
              <td className="px-4 py-3">
                {t.bucket && (
                  <span
                    className="text-xs px-2 py-0.5 rounded-full font-medium"
                    style={{
                      background: (BUCKET_COLORS[t.bucket] || "#94a3b8") + "22",
                      color: BUCKET_COLORS[t.bucket] || "#94a3b8",
                    }}
                  >
                    {t.bucket}
                  </span>
                )}
              </td>
              <td className="px-4 py-3 text-gray-500 text-xs">{t.source}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── CSV import button ─────────────────────────────────────────────────────────
function CsvImport() {
  const qc = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [status, setStatus] = useState<string | null>(null)

  const { mutate, isPending } = useMutation({
    mutationFn: bulkImportTransactions,
    onSuccess: (res) => {
      setStatus(`✅ ${res.inserted} inserted, ${res.skipped} skipped${res.errors.length ? ` — ${res.errors.length} errors` : ""}`)
      qc.invalidateQueries({ queryKey: ["transactions"] })
      qc.invalidateQueries({ queryKey: ["txnSummary"] })
      qc.invalidateQueries({ queryKey: ["deploymentSeries"] })
    },
    onError: (e: Error) => setStatus(`❌ ${e.message}`),
  })

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      const text = ev.target?.result as string
      const parsed = parseZerodhaCsv(text)
      if (!parsed.length) { setStatus("No valid rows found in CSV."); return }
      mutate(parsed)
    }
    reader.readAsText(file)
  }

  return (
    <div className="flex items-center gap-3">
      <input ref={fileRef} type="file" accept=".csv" className="hidden" onChange={handleFile} />
      <button
        onClick={() => fileRef.current?.click()}
        disabled={isPending}
        className="text-xs px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-colors disabled:opacity-50"
      >
        {isPending ? "Importing…" : "Import Zerodha CSV"}
      </button>
      {status && <span className="text-xs text-gray-400">{status}</span>}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function TransactionsPage() {
  const [filters, setFilters] = useState({ ticker: "", type: "", bucket: "" })

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Transactions</h1>
          <p className="text-sm text-gray-400 mt-0.5">Buy &amp; sell history with temporal deployment view</p>
        </div>
        <CsvImport />
      </div>

      <SummaryCards />
      <DeploymentChart />

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <input
          placeholder="Filter by symbol…"
          value={filters.ticker}
          onChange={e => setFilters(f => ({ ...f, ticker: e.target.value }))}
          className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 w-40"
        />
        <select
          value={filters.type}
          onChange={e => setFilters(f => ({ ...f, type: e.target.value }))}
          className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-indigo-500"
        >
          <option value="">All types</option>
          <option value="buy">Buy</option>
          <option value="sell">Sell</option>
        </select>
        <select
          value={filters.bucket}
          onChange={e => setFilters(f => ({ ...f, bucket: e.target.value }))}
          className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-indigo-500"
        >
          <option value="">All buckets</option>
          {BUCKETS.map(b => <option key={b} value={b}>{b}</option>)}
        </select>
      </div>

      <TransactionTable filters={filters} />
    </div>
  )
}
