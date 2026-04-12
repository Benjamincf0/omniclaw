import { useState } from "react"

export default function ChatInput({ onSend, disabled }) {
  const [value, setValue] = useState("")
  const [focused, setFocused] = useState(false)

  const handleSubmit = (e) => {
    e.preventDefault()
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue("")
  }

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      handleSubmit(e)
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex items-center gap-3 px-4 py-4"
      style={{
        borderTop: "1px solid var(--border)",
        backgroundColor: "var(--bg-card)",
      }}
    >
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        placeholder="Ask anything about your Omnivox…"
        rows={1}
        disabled={disabled}
        className="flex-1 text-sm resize-none transition-all duration-150 disabled:opacity-50"
        style={{
          backgroundColor: "var(--bg-parchment)",
          border: `1px solid ${focused ? "var(--navy)" : "var(--border)"}`,
          borderRadius: "12px",
          padding: "10px 16px",
          color: "var(--text-primary)",
          fontFamily: "'Source Serif 4', serif",
          lineHeight: "1.5",
          outline: "none",
          boxShadow: focused ? "0 0 0 3px rgba(28,43,74,0.08)" : "none",
        }}
      />
      <button
        type="submit"
        disabled={!value.trim() || disabled}
        className="shrink-0 text-sm font-medium transition-all duration-150 cursor-pointer"
        style={{
          height: "40px",
          padding: "0 18px",
          borderRadius: "10px",
          backgroundColor: value.trim() && !disabled ? "var(--navy)" : "var(--border)",
          color: value.trim() && !disabled ? "#EDE8DC" : "var(--text-muted)",
          border: "none",
          fontFamily: "'Source Serif 4', serif",
          cursor: !value.trim() || disabled ? "not-allowed" : "pointer",
          opacity: !value.trim() || disabled ? 0.5 : 1,
        }}
      >
        Send
      </button>
    </form>
  )
}
