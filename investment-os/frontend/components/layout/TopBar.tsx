"use client"

import { RefreshCw } from "lucide-react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { triggerSync } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

interface TopBarProps {
  title: string
}

export function TopBar({ title }: TopBarProps) {
  const queryClient = useQueryClient()
  const { mutate: doSync, isPending } = useMutation({
    mutationFn: () => triggerSync(["all"]),
    onSuccess: () => {
      queryClient.invalidateQueries()
    },
  })

  return (
    <header className="flex items-center justify-between h-14 px-6 border-b border-gray-800 bg-gray-950">
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
  )
}
