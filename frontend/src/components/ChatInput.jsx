import { useState } from "react"

export default function ChatInput({ onSend, disabled }) {
  const [value, setValue] = useState("")

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
      className="flex items-center gap-3 px-4 py-4 border-t border-[#2a2a32]"
    >
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask anything about your Omnivox..."
        rows={1}
        disabled={disabled}
        className="flex-1 bg-[#1a1a1f] border border-[#2a2a32] focus:border-[#6c63ff]/60 focus:outline-none text-[#e8e8f0] placeholder-[#6b6b7a] text-sm px-4 py-3 rounded-xl resize-none transition-colors duration-150 disabled:opacity-50"
        style={{ lineHeight: "1.5" }}
      />
      <button
        type="submit"
        disabled={!value.trim() || disabled}
        className="h-10 px-4 rounded-xl bg-[#6c63ff] hover:bg-[#7d75ff] disabled:opacity-30 disabled:cursor-not-allowed text-white text-sm font-medium transition-all duration-150 shrink-0 cursor-pointer"
      >
        Send
      </button>
    </form>
  )
}
