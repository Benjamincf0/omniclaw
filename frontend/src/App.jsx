import { useState, useRef, useEffect } from "react"
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

export default function App() {
  const [page, setPage] = useState("chat")
  const [consent, setConsent] = useState(false)
  const [showConsent, setShowConsent] = useState(false)
  const [messages, setMessages] = useState([])
  const [isTyping, setIsTyping] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
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
      // if not accepted, show the consent modal on first load
      if (!accepted) setShowConsent(true)
    } catch (e) {
      // ignore
    }
  }, [])

  const handleSend = async (text) => {
    if (!consent) {
      // guard: don't allow sending when consent not given
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
      const reply = await fetchReply(text, history)
      setMessages((prev) => [...prev, { role: "assistant", content: reply, timestamp: Date.now() }])
    } catch (err) {
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

      <div className="flex flex-1 items-stretch overflow-hidden bg-textured-parchment">

        {/* Left spacer — keeps chat card centered */}
        <div className="flex-1" />

        {/* Fixed-width content card */}
        <div className="flex flex-col h-full shrink-0" style={{ width: "640px" }}>

          {page === "chat" && (
            <>
              <Header />
              <div
                className="flex-1 overflow-y-auto py-4 bg-textured-warm"
              >
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

        {/* Right panel — always visible */}
        <div className="flex-1 flex justify-start">
          <GlancePanel />
        </div>

//     <div className="flex flex-col h-screen max-w-2xl mx-auto">
//       <Header onSettingsClick={() => setShowSettings(true)} />
//       {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}

//       {/* Message area */}
//       <div className="flex-1 overflow-y-auto py-4">
//         {!hasMessages && (
//           <div className="flex flex-col gap-6">
//             <WelcomeScreen />
//             <QuickChips onSelect={handleSend} />
//           </div>
//         )}

//         {messages.map((msg, i) => (
//           <Message key={i} role={msg.role} content={msg.content} />
//         ))}
        
//         {isTyping && <TypingIndicator />}

//         <div ref={bottomRef} />
      </div>

      {/* Consent modal - shown when user hasn't accepted or on-demand from sidebar */}
      {showConsent && <ConsentScreen onAccept={handleAcceptConsent} />}
    </div>
  )
}
