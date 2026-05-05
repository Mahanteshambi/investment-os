"use client"

import { useState, useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { ArrowUpDown, Download, Search } from "lucide-react"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Skeleton } from "@/components/ui/skeleton"
import { getHoldings } from "@/lib/api"
import { formatINR, formatPct } from "@/lib/utils"
import type { HoldingResponse } from "@/types"

const PAGE_SIZE = 10
const TABS = ["all", "equity", "mf", "etf", "gold", "cash", "debt"] as const
type Tab = (typeof TABS)[number]

const SOURCE_COLORS: Record<string, string> = {
  kite: "bg-blue-900/50 text-blue-400 border-blue-800",
  sheets: "bg-violet-900/50 text-violet-400 border-violet-800",
  manual: "bg-gray-800 text-gray-400 border-gray-700",
}

type SortKey = "asset_name" | "current_value" | "unrealized_pnl" | "unrealized_pnl_pct" | "avg_cost" | "current_price"

export function HoldingsTable() {
  const [activeTab, setActiveTab] = useState<Tab>("all")
  const [search, setSearch] = useState("")
  const [sortKey, setSortKey] = useState<SortKey>("current_value")
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc")
  const [page, setPage] = useState(0)

  const { data: holdings, isLoading } = useQuery({
    queryKey: ["holdings"],
    queryFn: () => getHoldings(),
    refetchInterval: 60_000,
  })

  const totalValue = useMemo(
    () => holdings?.reduce((sum, h) => sum + (h.current_value ?? 0), 0) ?? 0,
    [holdings]
  )

  const filtered = useMemo(() => {
    let list = holdings ?? []
    if (activeTab !== "all") list = list.filter((h) => h.asset_class === activeTab)
    if (search) {
      const q = search.toLowerCase()
      list = list.filter((h) => h.asset_name.toLowerCase().includes(q) || (h.ticker ?? "").toLowerCase().includes(q))
    }
    return [...list].sort((a, b) => {
      const av = (a[sortKey] as number | string | null) ?? 0
      const bv = (b[sortKey] as number | string | null) ?? 0
      const cmp = typeof av === "string" ? av.localeCompare(String(bv)) : Number(av) - Number(bv)
      return sortDir === "asc" ? cmp : -cmp
    })
  }, [holdings, activeTab, search, sortKey, sortDir])

  const pages = Math.ceil(filtered.length / PAGE_SIZE)
  const paged = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"))
    else { setSortKey(key); setSortDir("desc") }
    setPage(0)
  }

  function exportCSV() {
    const headers = ["Name", "Ticker", "Class", "Source", "Quantity", "Avg Cost", "Current Price", "Value", "P&L", "P&L %"]
    const rows = filtered.map((h) => [
      h.asset_name, h.ticker ?? "", h.asset_class, h.source,
      h.quantity ?? "", h.avg_cost ?? "", h.current_price ?? "",
      h.current_value ?? "", h.unrealized_pnl ?? "", h.unrealized_pnl_pct ?? "",
    ])
    const csv = [headers, ...rows].map((r) => r.join(",")).join("\n")
    const blob = new Blob([csv], { type: "text/csv" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url; a.download = "holdings.csv"; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <Tabs value={activeTab} onValueChange={(v) => { setActiveTab(v as Tab); setPage(0) }}>
          <TabsList className="bg-gray-800 border-gray-700">
            {TABS.map((t) => (
              <TabsTrigger key={t} value={t} className="capitalize text-xs data-[state=active]:bg-gray-700 data-[state=active]:text-white text-gray-500">
                {t}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-500" />
            <input
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(0) }}
              placeholder="Search…"
              className="pl-7 pr-3 py-1.5 text-xs bg-gray-800 border border-gray-700 rounded-md text-gray-300 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-indigo-600 w-40"
            />
          </div>
          <Button size="sm" variant="outline" onClick={exportCSV} className="border-gray-700 text-gray-400 bg-transparent hover:text-white text-xs">
            <Download className="h-3.5 w-3.5 mr-1" /> CSV
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full bg-gray-800" />
          ))}
        </div>
      ) : paged.length === 0 ? (
        <div className="text-center py-12 text-gray-600 text-sm">
          {(holdings?.length ?? 0) === 0
            ? "No holdings synced yet. Click Sync Now to pull your portfolio."
            : "No results match your filter."}
        </div>
      ) : (
        <>
          <div className="rounded-lg border border-gray-800 overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="border-gray-800 hover:bg-transparent">
                  <SortHead label="Asset" col="asset_name" current={sortKey} dir={sortDir} onSort={toggleSort} />
                  <TableHead className="text-gray-500 text-xs">Class</TableHead>
                  <SortHead label="Value" col="current_value" current={sortKey} dir={sortDir} onSort={toggleSort} right />
                  <TableHead className="text-gray-500 text-xs text-right">Alloc %</TableHead>
                  <SortHead label="Avg Cost" col="avg_cost" current={sortKey} dir={sortDir} onSort={toggleSort} right />
                  <SortHead label="Price" col="current_price" current={sortKey} dir={sortDir} onSort={toggleSort} right />
                  <SortHead label="P&L" col="unrealized_pnl" current={sortKey} dir={sortDir} onSort={toggleSort} right />
                </TableRow>
              </TableHeader>
              <TableBody>
                {paged.map((h) => (
                  <HoldingRow key={h.id} holding={h} totalValue={totalValue} />
                ))}
              </TableBody>
            </Table>
          </div>

          {pages > 1 && (
            <div className="flex items-center justify-between text-xs text-gray-500">
              <span>{filtered.length} holdings</span>
              <div className="flex gap-1">
                <button
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="px-2 py-1 rounded border border-gray-700 disabled:opacity-30 hover:border-gray-500"
                >
                  ‹
                </button>
                <span className="px-2 py-1">{page + 1}/{pages}</span>
                <button
                  onClick={() => setPage((p) => Math.min(pages - 1, p + 1))}
                  disabled={page >= pages - 1}
                  className="px-2 py-1 rounded border border-gray-700 disabled:opacity-30 hover:border-gray-500"
                >
                  ›
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

function HoldingRow({ holding: h, totalValue }: { holding: HoldingResponse; totalValue: number }) {
  const pnlPositive = (h.unrealized_pnl ?? 0) >= 0
  const allocPct = totalValue > 0 ? ((h.current_value ?? 0) / totalValue) * 100 : 0

  return (
    <TableRow className="border-gray-800 hover:bg-gray-800/30">
      <TableCell className="py-2.5">
        <div className="flex items-center gap-2">
          <Badge variant="outline" className={`text-[10px] px-1 py-0 ${SOURCE_COLORS[h.source] ?? ""}`}>
            {h.source}
          </Badge>
          <div>
            <p className="text-sm text-gray-200 font-medium">{h.asset_name}</p>
            {h.ticker && h.ticker !== h.asset_name && (
              <p className="text-[10px] text-gray-600">{h.ticker}</p>
            )}
          </div>
        </div>
      </TableCell>
      <TableCell className="py-2.5">
        <span className="text-xs text-gray-400 capitalize">{h.asset_class}</span>
      </TableCell>
      <TableCell className="py-2.5 text-right text-sm text-gray-200">
        {h.current_value != null ? formatINR(h.current_value) : "—"}
      </TableCell>
      <TableCell className="py-2.5 text-right text-xs text-gray-500">
        {allocPct.toFixed(1)}%
      </TableCell>
      <TableCell className="py-2.5 text-right text-xs text-gray-400">
        {h.avg_cost != null ? formatINR(h.avg_cost) : "—"}
      </TableCell>
      <TableCell className="py-2.5 text-right text-xs text-gray-400">
        {h.current_price != null ? formatINR(h.current_price) : "—"}
      </TableCell>
      <TableCell className="py-2.5 text-right">
        <div className={`text-xs font-medium ${pnlPositive ? "text-emerald-400" : "text-red-400"}`}>
          {h.unrealized_pnl != null ? formatINR(h.unrealized_pnl) : "—"}
        </div>
        {h.unrealized_pnl_pct != null && (
          <div className={`text-[10px] ${pnlPositive ? "text-emerald-600" : "text-red-600"}`}>
            {formatPct(h.unrealized_pnl_pct)}
          </div>
        )}
      </TableCell>
    </TableRow>
  )
}

function SortHead({
  label, col, current, dir, onSort, right,
}: {
  label: string
  col: SortKey
  current: SortKey
  dir: "asc" | "desc"
  onSort: (k: SortKey) => void
  right?: boolean
}) {
  const active = current === col
  return (
    <TableHead className={`text-xs cursor-pointer select-none ${right ? "text-right" : ""}`} onClick={() => onSort(col)}>
      <span className={`inline-flex items-center gap-0.5 ${active ? "text-indigo-400" : "text-gray-500"} ${right ? "flex-row-reverse" : ""}`}>
        {label}
        <ArrowUpDown className="h-3 w-3" />
        {active && <span className="text-[9px]">{dir === "asc" ? "↑" : "↓"}</span>}
      </span>
    </TableHead>
  )
}
