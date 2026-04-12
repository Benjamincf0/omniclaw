import { useState, useRef, useEffect } from "react"
import Sidebar from "./components/Sidebar"
import Header from "./components/Header"
import Message from "./components/Message"
import TypingIndicator from "./components/TypingIndicator"
import ChatInput from "./components/ChatInput"
import QuickChips from "./components/QuickChips"
import WelcomeScreen from "./components/WelcomeScreen"
import HowToUse from "./components/HowToUse"

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
  const [messages, setMessages] = useState([])
  const [isTyping, setIsTyping] = useState(false)
  const bottomRef = useRef(null)

  const hasMessages = messages.length > 0

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, isTyping])

  const handleSend = async (text) => {
    const userMessage = { role: "user", content: text }
    const updatedMessages = [...messages, userMessage]
    setMessages(updatedMessages)
    setIsTyping(true)

    const history = messages.map((m) => ({
      role: m.role === "assistant" ? "model" : "user",
      parts: [{ text: m.content }],
    }))

    try {
      const reply = await fetchReply(text, history)
      setMessages((prev) => [...prev, { role: "assistant", content: reply }])
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Something went wrong. Is the server running?" },
      ])
    } finally {
      setIsTyping(false)
    }
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden" style={{ backgroundColor: "var(--bg-parchment)" }}>

      <Sidebar activePage={page} onNavigate={setPage} />

      <div className="flex flex-1 items-stretch justify-center overflow-hidden" style={{ backgroundColor: "var(--bg-parchment)" }}>

        {/* Fixed-width content card */}
        <div className="flex flex-col h-full" style={{ width: "680px" }}>

          {page === "chat" && (
            <>
              <Header />
              <div
                className="flex-1 overflow-y-auto py-4"
                style={{ backgroundColor: "var(--bg-warm)" }}
              >
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
            </>
          )}

          {page === "howto" && <HowToUse />}

        </div>

        {/* Right gutter — reserved for future panels */}
        <div className="hidden xl:block" style={{ width: "260px" }} />
      </div>
    </div>
  )
}
