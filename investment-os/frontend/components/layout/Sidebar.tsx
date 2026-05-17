"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { BarChart2, BriefcaseBusiness, FlaskConical, TrendingUp, Shield, RotateCcw, Globe, ArrowLeftRight } from "lucide-react"
import { cn } from "@/lib/utils"
import { useQuery } from "@tanstack/react-query"
import { getSyncStatus } from "@/lib/api"

const navItems = [
  { href: "/", label: "Dashboard", icon: BarChart2 },
  { href: "/world-view", label: "World View", icon: Globe },
  { href: "/holdings", label: "Holdings", icon: BriefcaseBusiness },
  { href: "/intelligence", label: "MF Intelligence", icon: Shield },
  { href: "/sector-rotation", label: "Sector Rotation", icon: RotateCcw },
  { href: "/transactions", label: "Transactions", icon: ArrowLeftRight },
  { href: "/analysis", label: "Analysis", icon: FlaskConical },
]

export function Sidebar() {
  const pathname = usePathname()
  const { data: syncStatus } = useQuery({
    queryKey: ["syncStatus"],
    queryFn: getSyncStatus,
    refetchInterval: 30_000,
  })

  const kiteOk = syncStatus?.find((s) => s.source === "kite")?.status === "success"
  const sheetsOk = syncStatus?.find((s) => s.source === "sheets")?.status === "success"

  return (
    <aside className="flex flex-col w-56 min-h-screen bg-gray-950 border-r border-gray-800 px-4 py-6">
      <div className="flex items-center gap-2 mb-8">
        <TrendingUp className="h-6 w-6 text-indigo-400" />
        <span className="text-white font-semibold text-lg tracking-tight">Investment OS</span>
      </div>

      <nav className="flex-1 space-y-1">
        {navItems.map(({ href, label, icon: Icon, disabled }) => (
          <div key={href}>
            {disabled ? (
              <div className="flex items-center gap-3 px-3 py-2 rounded-md text-gray-600 cursor-not-allowed select-none">
                <Icon className="h-4 w-4" />
                <span className="text-sm">{label}</span>
                <span className="ml-auto text-xs bg-gray-800 text-gray-500 px-1.5 py-0.5 rounded">Soon</span>
              </div>
            ) : (
              <Link
                href={href}
                className={cn(
                  "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
                  pathname === href
                    ? "bg-indigo-900/50 text-indigo-300 font-medium"
                    : "text-gray-400 hover:text-gray-200 hover:bg-gray-800"
                )}
              >
                <Icon className="h-4 w-4" />
                {label}
              </Link>
            )}
          </div>
        ))}
      </nav>

      <div className="mt-auto pt-4 border-t border-gray-800 space-y-2">
        <p className="text-xs text-gray-600 uppercase tracking-wider mb-2">Connections</p>
        <StatusDot label="Kite" ok={kiteOk} />
        <StatusDot label="Google Sheets" ok={sheetsOk} />
      </div>
    </aside>
  )
}

function StatusDot({ label, ok }: { label: string; ok?: boolean }) {
  return (
    <div className="flex items-center gap-2 text-xs text-gray-500">
      <span className={cn("h-2 w-2 rounded-full", ok ? "bg-emerald-400" : "bg-gray-600")} />
      {label}
    </div>
  )
}
