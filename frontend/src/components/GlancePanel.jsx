import { useState, useEffect } from "react"
import { motion } from "framer-motion"

const item = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.22, ease: [0.25, 0.46, 0.45, 0.94] } },
}
const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08, delayChildren: 0.1 } },
}

function useLiveClock() {
  const [now, setNow] = useState(new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  return now
}

const stats = [
  {
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
        <rect x="1" y="3" width="13" height="11" rx="1.5" stroke="currentColor" strokeWidth="1.2"/>
        <path d="M1 6.5H14" stroke="currentColor" strokeWidth="1.2"/>
        <path d="M5 1.5V4.5M10 1.5V4.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
      </svg>
    ),
    label: "Next class",
    value: "Math 201",
    sub: "Today, 10:30 AM · H-210",
    color: "var(--navy)",
  },
  {
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
        <path d="M2 2H13V11H8.5L7 13.5L5.5 11H2V2Z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
        <path d="M5 5.5H10M5 7.5H8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
      </svg>
    ),
    label: "Unread messages",
    value: "3 new",
    sub: "From teachers & admin",
    color: "#507dd6",
  },
  {
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
        <path d="M3 3H12V12H3V3Z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
        <path d="M3 6H12M6 3V12" stroke="currentColor" strokeWidth="1.2"/>
        <circle cx="8.5" cy="9" r="1" fill="currentColor"/>
      </svg>
    ),
    label: "Due soon",
    value: "2 assignments",
    sub: "Within the next 3 days",
    color: "#B07830",
  },
]

const tips = [
  "Ask \"What's due this week?\" to see all upcoming assignments.",
  "Try \"Any messages from my teachers?\" for a quick inbox summary.",
  "Ask \"When is my next class?\" to get your schedule at a glance.",
]

export default function GlancePanel() {
  const now = useLiveClock()
  const tip = tips[now.getMinutes() % tips.length]

  const dayName = now.toLocaleDateString("en-CA", { weekday: "long" })
  const dateStr = now.toLocaleDateString("en-CA", { month: "long", day: "numeric", year: "numeric" })
  const timeStr = now.toLocaleTimeString("en-CA", { hour: "2-digit", minute: "2-digit" })

  return (
    <aside
      className="h-full overflow-y-auto flex flex-col"
      style={{
        width: "260px",
        borderLeft: "1px solid var(--border)",
        backgroundColor: "var(--bg-card)",
      }}
    >
      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="flex flex-col gap-5 px-5 py-6"
      >
        {/* Date + clock */}
        <motion.div variants={item}>
          <p
            className="text-[10px] mb-3"
            style={{ color: "var(--text-muted)", letterSpacing: "0.1em" }}
          >
            TODAY AT A GLANCE
          </p>
          <div
            className="rounded-xl px-4 py-3 flex items-center justify-between"
            style={{
              background: "linear-gradient(135deg, var(--sidebar-bg) 0%, #2A4A8A 100%)",
            }}
          >
            <div>
              <p className="text-xs font-medium" style={{ color: "rgba(255,255,255,0.6)" }}>
                {dayName}
              </p>
              <p className="text-[11px]" style={{ color: "rgba(255,255,255,0.4)" }}>
                {dateStr}
              </p>
            </div>
            <p
              className="text-xl font-bold tracking-tight"
              style={{ color: "#ffffff", fontFamily: "'DM Serif Display', serif" }}
            >
              {timeStr}
            </p>
          </div>
        </motion.div>

        {/* Stats */}
        <motion.div variants={item} className="flex flex-col gap-3">
          <p
            className="text-[10px]"
            style={{ color: "var(--text-muted)", letterSpacing: "0.1em" }}
          >
            OVERVIEW
          </p>
          {stats.map((s) => (
            <div
              key={s.label}
              className="flex items-start gap-3 p-3.5 rounded-xl"
              style={{
                backgroundColor: "var(--bg-warm)",
                border: "1px solid var(--border)",
              }}
            >
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
                style={{ backgroundColor: `${s.color}18`, color: s.color }}
              >
                {s.icon}
              </div>
              <div>
                <p
                  className="text-sm font-medium leading-tight"
                  style={{ color: "var(--text-primary)", fontFamily: "'Source Serif 4', serif" }}
                >
                  {s.value}
                </p>
                <p
                  className="text-[11px] leading-tight mt-0.5"
                  style={{ color: "var(--text-muted)", fontFamily: "'Source Serif 4', serif" }}
                >
                  {s.sub}
                </p>
              </div>
            </div>
          ))}
        </motion.div>

        {/* Tip */}
        <motion.div variants={item}>
          <p
            className="text-[10px] mb-2"
            style={{ color: "var(--text-muted)", letterSpacing: "0.1em" }}
          >
            TIP
          </p>
          <div
            className="p-3 rounded-xl text-xs leading-relaxed"
            style={{
              backgroundColor: "rgba(80,125,214,0.06)",
              border: "1px solid rgba(80,125,214,0.18)",
              color: "var(--text-secondary)",
              fontFamily: "'Source Serif 4', serif",
              fontStyle: "italic",
            }}
          >
            "{tip}"
          </div>
        </motion.div>

        {/* Disclaimer */}
        <motion.div variants={item}>
          <p
            className="text-[10px] leading-relaxed text-center"
            style={{ color: "var(--text-muted)", fontFamily: "'Source Serif 4', serif" }}
          >
            Overview data is a preview.<br />Live data loads when you chat.
          </p>
        </motion.div>
      </motion.div>
    </aside>
  )
}
