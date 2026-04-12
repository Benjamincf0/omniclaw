export default function Header() {
  return (
    <header className="shrink-0">
      {/* Top announcement bar */}
      <div
        className="w-full text-center text-xs py-2 px-4 font-medium tracking-wide"
        style={{
          backgroundColor: "var(--navy)",
          color: "#C8B89A",
          letterSpacing: "0.04em",
        }}
      >
        ✦ Omniclaw is connected to your Omnivox account
      </div>

      {/* Main nav */}
      <div
        className="flex items-center justify-between px-6 py-4"
        style={{
          backgroundColor: "var(--bg-card)",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <div className="flex items-center gap-3">
          {/* Crest mark */}
          <div
            className="w-8 h-8 rounded-sm flex items-center justify-center text-xs font-bold shrink-0"
            style={{
              backgroundColor: "var(--navy)",
              color: "#C8B89A",
              fontFamily: "'DM Serif Display', serif",
              letterSpacing: "0.02em",
            }}
          >
            O
          </div>

          <div>
            <span
              className="font-semibold text-base leading-tight block"
              style={{
                fontFamily: "'DM Serif Display', serif",
                color: "var(--navy)",
                letterSpacing: "-0.01em",
              }}
            >
              Omniclaw
            </span>
            <span
              className="text-[10px] leading-tight block"
              style={{ color: "var(--text-muted)", letterSpacing: "0.08em" }}
            >
              JAC ACADEMIC ASSISTANT
            </span>
          </div>
        </div>

        <div
          className="flex items-center gap-2 text-xs font-medium px-3 py-1.5 rounded-full"
          style={{
            backgroundColor: "var(--bg-parchment)",
            border: "1px solid var(--border)",
            color: "var(--navy-muted)",
          }}
        >
          <span
            className="w-1.5 h-1.5 rounded-full animate-pulse"
            style={{ backgroundColor: "#5AAF72" }}
          />
          Connected
        </div>
      </div>
    </header>
  )
}
