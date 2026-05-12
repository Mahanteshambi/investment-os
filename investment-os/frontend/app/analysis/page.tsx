"use client"

import { useState, useRef, useEffect } from "react"
import { TopBar } from "@/components/layout/TopBar"
import { Send, Bot, User, Sparkles, Activity, RefreshCw, BarChart2 } from "lucide-react"
import { cn } from "@/lib/utils"

interface Message {
  id: string
  role: "user" | "agent"
  content: string
  isStreaming?: boolean
}

export default function AnalysisChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      role: "agent",
      content: "Hello Mahantesh! I am your CIO Agent. Your Kite and Google Sheets connections are active. What would you like to analyze today?"
    }
  ])
  const [input, setInput] = useState("")
  const [isTyping, setIsTyping] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, isTyping])

  const handleSend = async (text: string) => {
    if (!text.trim()) return

    // Add user message
    const newUserMsg: Message = { id: Date.now().toString(), role: "user", content: text }
    setMessages(prev => [...prev, newUserMsg])
    setInput("")
    setIsTyping(true)

    // Real Backend API Call
    try {
      const response = await fetch("http://localhost:8000/api/chat/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message: text }),
      });

      if (!response.ok) {
        throw new Error("Network response was not ok");
      }

      const data = await response.json();
      const newAgentMsg: Message = { id: (Date.now() + 1).toString(), role: "agent", content: data.response };
      setMessages(prev => [...prev, newAgentMsg]);
    } catch (error) {
      console.error("Error calling agent:", error);
      const errorMsg: Message = { id: (Date.now() + 1).toString(), role: "agent", content: "Sorry, I couldn't reach the backend server. Is it running?" };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsTyping(false);
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend(input)
    }
  }

  const quickActions = [
    { label: "Run Daily Analysis", icon: Activity, text: "Run the daily analysis pipeline." },
    { label: "What did 'Sync Now' do?", icon: RefreshCw, text: "Explain what happened when I clicked Sync Now." },
    { label: "Check NIFTYBEES", icon: BarChart2, text: "What is the status of NIFTYBEES?" }
  ]

  return (
    <>
      <TopBar title="CIO Agent Chat" />
      <main className="flex-1 overflow-hidden flex flex-col bg-gray-950">
        
        {/* Chat Area */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6 max-w-4xl mx-auto w-full">
          {messages.map((msg) => (
            <div key={msg.id} className={cn("flex gap-4", msg.role === "user" ? "justify-end" : "justify-start")}>
              
              {/* Agent Avatar */}
              {msg.role === "agent" && (
                <div className="w-8 h-8 rounded-full bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center shrink-0 mt-1">
                  <Sparkles className="w-4 h-4 text-indigo-400" />
                </div>
              )}

              {/* Message Bubble */}
              <div className={cn(
                "px-5 py-4 rounded-2xl max-w-[85%] sm:max-w-[75%] whitespace-pre-wrap leading-relaxed shadow-sm text-sm",
                msg.role === "user" 
                  ? "bg-indigo-600 text-white rounded-tr-sm" 
                  : "bg-gray-900 border border-gray-800 text-gray-200 rounded-tl-sm"
              )}>
                {msg.content}
              </div>

              {/* User Avatar */}
              {msg.role === "user" && (
                <div className="w-8 h-8 rounded-full bg-gray-800 border border-gray-700 flex items-center justify-center shrink-0 mt-1">
                  <User className="w-4 h-4 text-gray-400" />
                </div>
              )}
            </div>
          ))}

          {/* Typing Indicator */}
          {isTyping && (
            <div className="flex gap-4 justify-start">
              <div className="w-8 h-8 rounded-full bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center shrink-0 mt-1">
                <Sparkles className="w-4 h-4 text-indigo-400 animate-pulse" />
              </div>
              <div className="px-5 py-4 rounded-2xl bg-gray-900 border border-gray-800 text-gray-200 rounded-tl-sm flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-full bg-gray-600 animate-bounce" />
                <div className="w-2 h-2 rounded-full bg-gray-600 animate-bounce" style={{ animationDelay: '0.15s' }} />
                <div className="w-2 h-2 rounded-full bg-gray-600 animate-bounce" style={{ animationDelay: '0.3s' }} />
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="bg-gray-950 border-t border-gray-800 p-4 shrink-0">
          <div className="max-w-4xl mx-auto">
            
            {/* Quick Actions */}
            <div className="flex flex-wrap gap-2 mb-3">
              {quickActions.map((action, i) => (
                <button
                  key={i}
                  onClick={() => handleSend(action.text)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gray-900 hover:bg-gray-800 border border-gray-800 text-xs font-medium text-gray-300 transition-colors"
                >
                  <action.icon className="w-3.5 h-3.5" />
                  {action.label}
                </button>
              ))}
            </div>

            {/* Input Field */}
            <div className="relative flex items-center">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask me to analyze the market, check a stock, or review your budget..."
                className="w-full bg-gray-900 border border-gray-800 text-gray-100 rounded-xl pl-4 pr-12 py-4 focus:outline-none focus:ring-1 focus:ring-indigo-500 resize-none overflow-hidden"
                rows={1}
                style={{ minHeight: "56px" }}
              />
              <button
                onClick={() => handleSend(input)}
                disabled={!input.trim() || isTyping}
                className="absolute right-2 p-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-800 disabled:text-gray-500 text-white rounded-lg transition-colors"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
            <p className="text-center text-xs text-gray-600 mt-3">
              Press Enter to send, Shift + Enter for new line.
            </p>
          </div>
        </div>

      </main>
    </>
  )
}
