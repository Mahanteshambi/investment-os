"use client"

import { useState } from "react"
import { RefreshCw } from "lucide-react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { triggerSync } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { KiteAuthModal } from "@/components/layout/KiteAuthModal"

interface TopBarProps {
  title: string
}

export function TopBar({ title }: TopBarProps) {
  const queryClient = useQueryClient()
  const [showAuthFlow, setShowAuthFlow] = useState(false)

  const { mutate: doSync, isPending } = useMutation({
    mutationFn: () => triggerSync(["all"]),
    onSuccess: (data: any) => {
      // If the backend returns an error about kite, show the auth flow
      const hasKiteError = data?.errors?.some((e: string) => e.toLowerCase().includes("kite"))
      if (hasKiteError) {
        setShowAuthFlow(true)
      } else {
        setShowAuthFlow(false)
        queryClient.invalidateQueries()
      }
    },
  })

  return (
    <div className="flex flex-col border-b border-gray-800 bg-gray-950">
      <header className="flex items-center justify-between h-14 px-6">
        <h1 className="text-white font-semibold text-base">{title}</h1>
        <Button
          size="sm"
          variant="outline"
          className="border-gray-700 text-gray-300 hover:text-white hover:border-gray-500 bg-transparent"
          onClick={() => doSync()}
          disabled={isPending}
        >
          <RefreshCw className={cn("h-3.5 w-3.5 mr-1.5", isPending && "animate-spin")} />
          {isPending ? "Syncing…" : "Sync Now"}
        </Button>
      </header>
      
      {showAuthFlow && (
        <div className="px-6 pb-6 w-full max-w-2xl mx-auto">
          <KiteAuthModal onSuccess={() => {
            setShowAuthFlow(false)
            doSync() // re-trigger sync automatically
          }} />
        </div>
      )}
    </div>
  )
}
