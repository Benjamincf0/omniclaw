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

    
        

    </header>
  )
}
