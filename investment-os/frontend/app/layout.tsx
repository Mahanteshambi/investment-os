import type { Metadata } from "next"
import { Geist } from "next/font/google"
import "./globals.css"
import { Providers } from "./providers"
import { Sidebar } from "@/components/layout/Sidebar"

const geist = Geist({ variable: "--font-geist-sans", subsets: ["latin"] })

export const metadata: Metadata = {
  title: "Investment OS",
  description: "Personal investment portfolio dashboard",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geist.variable} h-full antialiased dark`} suppressHydrationWarning>
      <body className="min-h-full flex bg-gray-950 text-gray-100" suppressHydrationWarning>
        <Providers>
          <Sidebar />
          <div className="flex-1 flex flex-col min-h-screen overflow-auto">
            {children}
          </div>
        </Providers>
      </body>
    </html>
  )
}
