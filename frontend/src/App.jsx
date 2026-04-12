import { useState, useRef, useEffect } from "react"
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { useAuth0 } from "@auth0/auth0-react"

import Sidebar from "./components/Sidebar"
import Header from "./components/Header"
import Message from "./components/Message"
import TypingIndicator from "./components/TypingIndicator"
import ChatInput from "./components/ChatInput"
import QuickChips from "./components/QuickChips"
import WelcomeScreen from "./components/WelcomeScreen"
import HowToUse from "./components/HowToUse"
import GlancePanel from "./components/GlancePanel"
import ConsentScreen from "./components/ConsentScreen"
import SettingsModal from "./components/SettingsModal"
import AuthPage from "./components/AuthPage"
import SetupPage from "./components/SetupPage"

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8000"

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
  const { getAccessTokenSilently } = useAuth0()
  const [page, setPage] = useState("chat")
  const [consent, setConsent] = useState(false)
  const [showConsent, setShowConsent] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [messages, setMessages] = useState([])
  const [isTyping, setIsTyping] = useState(false)
  const bottomRef = useRef(null)
  const hasMessages = messages.length > 0

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, isTyping])

  // load consent from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem("omniclaw:consent")
      const accepted = saved === "true"
      setConsent(accepted)
      if (!accepted) setShowConsent(true)
    } catch (e) {
      // ignore
    }
  }, [])

  const handleSend = async (text) => {
    if (!consent) {
      setShowConsent(true)
      return
    }
    const userMessage = { role: "user", content: text, timestamp: Date.now() }
    const updatedMessages = [...messages, userMessage]
    setMessages(updatedMessages)
    setIsTyping(true)

    const history = messages.map((m) => ({
      role: m.role === "assistant" ? "model" : "user",
      parts: [{ text: m.content }],
    }))

    try {
      const token = await getAccessTokenSilently()
      const res = await fetch(`${BACKEND_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ message: text, history }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail ?? `Server error ${res.status}`)
      setMessages((prev) => [...prev, { role: "assistant", content: data.reply, timestamp: Date.now() }])
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Something went wrong. Is the server running?", timestamp: Date.now() },
      ])
    } finally {
      setIsTyping(false)
    }
  }

  const handleAcceptConsent = () => {
    try {
      localStorage.setItem("omniclaw:consent", "true")
    } catch (e) {
      // ignore
    }
    setConsent(true)
    setShowConsent(false)
  }

  const openConsent = () => setShowConsent(true)

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-textured-parchment">
      <Sidebar activePage={page} onNavigate={setPage} consent={consent} onOpenConsent={openConsent} />

      {/* Main content */}
      <div className="flex flex-col flex-1 min-w-0 h-full overflow-hidden">
        {page === "chat" && (
          <>
            <Header onSettingsClick={() => setShowSettings(true)} />
            <div className="flex-1 overflow-y-auto py-4 bg-textured-warm">
              {!hasMessages && (
                <div className="flex flex-col gap-6">
                  <WelcomeScreen />
                  <QuickChips onSelect={handleSend} />
                </div>
              )}
              {messages.map((msg, i) => (
                <Message key={i} role={msg.role} content={msg.content} timestamp={msg.timestamp} />
              ))}
              {isTyping && <TypingIndicator />}
              <div ref={bottomRef} />
            </div>
            <ChatInput onSend={handleSend} disabled={isTyping || !consent} />
          </>
        )}

        {page === "howto" && <HowToUse />}
      </div>

      {/* Right panel */}
      <GlancePanel />

      {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}
      {showConsent && <ConsentScreen onAccept={handleAcceptConsent} />}
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

        {/* Protected: Omnivox credential setup */}
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
