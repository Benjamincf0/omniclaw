import { Settings } from "lucide-react"

export default function Header({ onSettingsClick }) {
  return (
    <header
      className="flex items-center justify-between px-6 py-4 shrink-0"
      style={{
        backgroundColor: "var(--bg-card)",
        borderBottom: "1px solid var(--border)",
      }}
    >
      <div>
        <h1
          className="text-base font-semibold leading-tight"
          style={{
            fontFamily: "'DM Serif Display', serif",
            color: "var(--navy)",
            letterSpacing: "-0.01em",
          }}
        >
          Chat
        </h1>
        <p
          className="text-[11px] leading-tight"
          style={{ color: "var(--text-muted)", letterSpacing: "0.04em" }}
        >
          Ask me anything about Omnivox
        </p>
      </div>    
       

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 text-xs text-[#6b6b7a]">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          Live
        </div>
        <button
          onClick={onSettingsClick}
          className="text-[#6b6b7a] hover:text-[#e8e8f0] transition-colors cursor-pointer"
          title="Settings"
        >
          <Settings size={16} />
        </button>
      </div>
    </header>
  )
}
