export default function WelcomeScreen() {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-10 px-6 text-center">
      {/* Decorative emblem */}
      <div className="relative mb-1">
        <div
          className="w-16 h-16 rounded-full flex items-center justify-center"
          style={{
            backgroundColor: "var(--navy)",
            boxShadow: "0 4px 24px rgba(28,43,74,0.18)",
          }}
        >
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <path
              d="M14 4C14 4 6 8 6 14C6 18.4 9.6 22 14 22C18.4 22 22 18.4 22 14C22 8 14 4 14 4Z"
              fill="none"
              stroke="#C8B89A"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
            <path
              d="M14 9V14L17 16"
              stroke="#C8B89A"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <circle cx="14" cy="14" r="1.5" fill="#C8B89A" />
          </svg>
        </div>
        {/* Subtle halo */}
        <div
          className="absolute inset-0 rounded-full"
          style={{
            background: "radial-gradient(circle, rgba(28,43,74,0.08) 0%, transparent 70%)",
            transform: "scale(2)",
          }}
        />
      </div>

      <div>
        <h2
          className="text-2xl mb-1"
          style={{
            fontFamily: "'DM Serif Display', serif",
            color: "var(--navy)",
            letterSpacing: "-0.02em",
          }}
        >
          Hello, I'm Omniclaw
        </h2>
        <p
          className="text-sm max-w-xs leading-relaxed mx-auto"
          style={{ color: "var(--text-secondary)" }}
        >
          Your academic assistant for John Abbott College. Ask me about assignments,
          messages, your schedule, or campus news.
        </p>
      </div>

      {/* <div
        className="text-[11px] px-4 py-2 rounded-full mt-1"
        style={{
          backgroundColor: "var(--bg-card)",
          border: "1px solid var(--border)",
          color: "var(--text-muted)",
          letterSpacing: "0.06em",
        }}
      >
        POWERED BY OMNICLAW
      </div> */}
    </div>
  )
}
