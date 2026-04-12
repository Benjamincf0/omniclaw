import { useState, useRef, useEffect } from "react"
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { useAuth0 } from "@auth0/auth0-react"

import Header from "./components/Header"
import Message from "./components/Message"
import TypingIndicator from "./components/TypingIndicator"
import ChatInput from "./components/ChatInput"
import QuickChips from "./components/QuickChips"
import WelcomeScreen from "./components/WelcomeScreen"
import AuthPage from "./components/AuthPage"
import SetupPage from "./components/SetupPage"

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8080"

async function fetchReply(message, history) {
  const res = await fetch(`${BACKEND_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail ?? `Server error ${res.status}`)
  return data.reply
}

// ── Loading spinner (shared) ──────────────────────────────────────────────────

function LoadingDots() {
  return (
    <div className="flex items-center justify-center h-screen bg-[#0f0f11]">
      <div className="flex gap-1.5 items-center">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="w-1.5 h-1.5 rounded-full bg-[#6b6b7a] animate-bounce"
            style={{ animationDelay: `${i * 0.15}s` }}
          />
        ))}
      </div>
    </div>
  )
}

// ── Chat page ─────────────────────────────────────────────────────────────────

function ChatPage() {
  const [messages, setMessages] = useState([])
  const [isTyping, setIsTyping] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const bottomRef = useRef(null)
  const hasMessages = messages.length > 0

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, isTyping])

  const handleSend = async (text) => {
    const userMessage = { role: "user", content: text }
    setMessages((prev) => [...prev, userMessage])
    setIsTyping(true)

    // Build history in Gemini format (exclude the current message)
    const history = messages.map((m) => ({
      role: m.role === "assistant" ? "model" : "user",
      parts: [{ text: m.content }],
    }))

    try {
      const reply = await fetchReply(text, history)
      setMessages((prev) => [...prev, { role: "assistant", content: reply }])
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Something went wrong. Is the server running?" },
      ])
    } finally {
      setIsTyping(false)
    }
  }

  return (
    <div className="flex flex-col h-screen max-w-2xl mx-auto">
      <Header />
      <div className="flex-1 overflow-y-auto py-4">
        {!hasMessages && (
          <div className="flex flex-col gap-6">
            <WelcomeScreen />
            <QuickChips onSelect={handleSend} />
          </div>
        )}
        {messages.map((msg, i) => (
          <Message key={i} role={msg.role} content={msg.content} />
        ))}
        {isTyping && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>
      <ChatInput onSend={handleSend} disabled={isTyping} />
    </div>
  )
}

// ── Auth guard: checks Omnivox link status, redirects to /setup if needed ─────

function RequireOmnivox({ children }) {
  const { getAccessTokenSilently } = useAuth0()
  const [checking, setChecking] = useState(true)
  const [linked, setLinked] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function check() {
      try {
        const token = await getAccessTokenSilently()
        const res = await fetch(`${BACKEND_URL}/account-status`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        const data = await res.json()
        if (!cancelled) setLinked(data.linked === true)
      } catch {
        if (!cancelled) setLinked(false)
      } finally {
        if (!cancelled) setChecking(false)
      }
    }
    check()
    return () => { cancelled = true }
  }, [getAccessTokenSilently])

  if (checking) return <LoadingDots />
  if (!linked) return <Navigate to="/setup" replace />
  return children
}

// ── Root ──────────────────────────────────────────────────────────────────────

export default function App() {
  const { isLoading, isAuthenticated } = useAuth0()

  if (isLoading) return <LoadingDots />

  return (
    <BrowserRouter>
      <Routes>
        {/* Public: login / create account */}
        <Route
          path="/auth"
          element={isAuthenticated ? <Navigate to="/" replace /> : <AuthPage />}
        />

        {/* Protected: Omnivox credential setup (also reachable via /link-omnivox
            so MCP clients can direct users here by opening the frontend URL) */}
        <Route
          path="/setup"
          element={isAuthenticated ? <SetupPage /> : <Navigate to="/auth" replace />}
        />
        <Route
          path="/link-omnivox"
          element={isAuthenticated ? <SetupPage /> : <Navigate to="/auth" replace />}
        />

        {/* Protected: main chat — also checks Omnivox link */}
        <Route
          path="/"
          element={
            isAuthenticated
              ? <RequireOmnivox><ChatPage /></RequireOmnivox>
              : <Navigate to="/auth" replace />
          }
        />

        {/* Catch-all */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
