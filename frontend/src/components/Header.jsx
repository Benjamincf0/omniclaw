export default function Header() {
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

      <div
        className="flex items-center gap-2 text-xs font-medium px-3 py-1.5 rounded-full"
        style={{
          backgroundColor: "var(--bg-parchment)",
          border: "1px solid var(--border)",
          color: "var(--navy-muted)",
          fontFamily: "'Source Serif 4', serif",
        }}
      >
        <span
          className="w-1.5 h-1.5 rounded-full animate-pulse"
          style={{ backgroundColor: "#5AAF72" }}
        />
        Live
      </div>
    </header>
  )
}
