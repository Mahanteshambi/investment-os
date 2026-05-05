"use client"

import { useState } from "react"
import { ExternalLink } from "lucide-react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { getKiteLoginUrl, submitKiteToken } from "@/lib/api"
import { Button } from "@/components/ui/button"

export function KiteAuthModal({ onSuccess }: { onSuccess: () => void }) {
  const [tokenInput, setTokenInput] = useState("")

  const { data } = useQuery({
    queryKey: ["kiteLoginUrl"],
    queryFn: getKiteLoginUrl,
  })

  const { mutate: doSubmit, isPending, error } = useMutation({
    mutationFn: (token: string) => submitKiteToken(token),
    onSuccess: () => {
      onSuccess()
    },
  })

  return (
    <div className="bg-gray-900 border border-red-900/50 rounded-xl p-4 mt-4">
      <h3 className="text-red-400 font-medium mb-2">Kite Authentication Required</h3>
      <p className="text-gray-400 text-sm mb-4">
        Your Kite session token has expired. Because Zerodha requires 2FA, we cannot automate this step in the background. Please log in manually to generate a new token.
      </p>
      
      <div className="space-y-4">
        <div>
          <p className="text-gray-300 text-sm mb-2 font-medium">1. Login to Zerodha</p>
          <Button
            variant="outline"
            className="w-full justify-between border-gray-700 bg-gray-800 hover:bg-gray-700 hover:text-white"
            onClick={() => {
              if (data?.login_url) window.open(data.login_url, "_blank")
            }}
            disabled={!data?.login_url}
          >
            Open Kite Login
            <ExternalLink className="h-4 w-4" />
          </Button>
          <p className="text-xs text-gray-500 mt-2">
            After logging in, you will be redirected to a URL that looks like <code className="text-gray-400 font-mono">http://127.0.0.1/?request_token=XXXXX</code>. Copy the <code className="text-gray-400 font-mono">XXXXX</code> part.
          </p>
        </div>

        <div>
          <p className="text-gray-300 text-sm mb-2 font-medium">2. Paste Request Token</p>
          <div className="flex gap-2">
            <input
              type="text"
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
              placeholder="Paste request_token here"
              className="flex h-10 w-full rounded-md border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder:text-gray-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
            <Button
              onClick={() => doSubmit(tokenInput)}
              disabled={isPending || !tokenInput}
              className="bg-indigo-600 hover:bg-indigo-700"
            >
              {isPending ? "Saving..." : "Save Token"}
            </Button>
          </div>
          {error && (
            <p className="text-red-400 text-xs mt-2">Failed to verify token. Make sure it's fresh.</p>
          )}
        </div>
      </div>
    </div>
  )
}
