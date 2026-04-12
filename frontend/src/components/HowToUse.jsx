import { motion } from "framer-motion"

const steps = [
  {
    number: "01",
    title: "Log in to Omnivox",
    description:
      "Make sure you are authenticated with your JAC Omnivox account before using Omniclaw. The assistant reads your live data directly from your account.",
  },
  {
    number: "02",
    title: "Ask in plain language",
    description:
      'Type your question naturally — no special commands needed. Try "What assignments are due this week?" or "Show me my schedule for tomorrow."',
  },
  {
    number: "03",
    title: "Use quick chips to get started",
    description:
      "On the chat screen you'll see shortcut buttons for common queries. Tap any of them to instantly ask a pre-set question without typing.",
  },
  {
    number: "04",
    title: "Review the response",
    description:
      "Omniclaw summarises information from Omnivox and presents it in a readable format. Always verify important deadlines directly in Omnivox.",
  },
]

const canAsk = [
  "What's my schedule today / this week?",
  "Do I have any unread messages?",
  "What assignments are due soon?",
  "What are the latest college announcements?",
  "When is my next class?",
]

const cannotAsk = [
  "Submit assignments on your behalf",
  "Send messages to teachers",
  "Change your grades or profile",
  "Access other students' data",
  "Perform actions outside Omnivox",
]

const item = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.25, ease: [0.25, 0.46, 0.45, 0.94] } },
}

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.07 } },
}

export default function HowToUse() {
  return (
    <div
      className="flex flex-col h-full"
      style={{ backgroundColor: "var(--bg-card)", borderLeft: "1px solid var(--border)", borderRight: "1px solid var(--border)" }}
    >
      {/* Page header */}
      <div
        className="flex items-center justify-between px-6 py-4 shrink-0"
        style={{ borderBottom: "1px solid var(--border)", backgroundColor: "var(--bg-card)" }}
      >
        <div>
          <h1
            className="text-base font-semibold leading-tight"
            style={{ fontFamily: "'DM Serif Display', serif", color: "var(--navy)", letterSpacing: "-0.01em" }}
          >
            How to Use
          </h1>
          <p className="text-[11px] leading-tight" style={{ color: "var(--text-muted)", letterSpacing: "0.04em" }}>
            A quick guide to Omniclaw
          </p>
        </div>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto" style={{ backgroundColor: "var(--bg-warm)" }}>
        <motion.div
          variants={container}
          initial="hidden"
          animate="show"
          className="max-w-xl mx-auto px-6 py-8 flex flex-col gap-10"
        >

          {/* Intro */}
          <motion.div variants={item}>
            <p
              className="text-sm leading-relaxed"
              style={{ color: "var(--text-secondary)", fontFamily: "'Source Serif 4', serif" }}
            >
              <strong style={{ color: "var(--navy)" }}>Omniclaw</strong> is your AI-powered academic assistant for
              John Abbott College. It connects directly to your Omnivox account and answers questions
              about your schedule, messages, assignments, and campus news — all in plain language.
            </p>
          </motion.div>

          {/* Steps */}
          <motion.div variants={item} className="flex flex-col gap-4">
            <SectionLabel>Getting Started</SectionLabel>
            {steps.map((step) => (
              <div
                key={step.number}
                className="flex gap-4 p-4 rounded-xl"
                style={{
                  backgroundColor: "var(--bg-card)",
                  border: "1px solid var(--border)",
                  boxShadow: "0 1px 4px rgba(28,43,74,0.05)",
                }}
              >
                <span
                  className="text-xs font-bold shrink-0 mt-0.5 w-7 h-7 rounded-md flex items-center justify-center"
                  style={{
                    backgroundColor: "var(--navy)",
                    color: "#C8B89A",
                    fontFamily: "'DM Serif Display', serif",
                    fontSize: "0.7rem",
                  }}
                >
                  {step.number}
                </span>
                <div>
                  <p
                    className="text-sm font-semibold mb-1"
                    style={{ color: "var(--navy)", fontFamily: "'DM Serif Display', serif" }}
                  >
                    {step.title}
                  </p>
                  <p
                    className="text-sm leading-relaxed"
                    style={{ color: "var(--text-secondary)", fontFamily: "'Source Serif 4', serif" }}
                  >
                    {step.description}
                  </p>
                </div>
              </div>
            ))}
          </motion.div>

          {/* Can / Cannot */}
          <motion.div variants={item} className="grid grid-cols-2 gap-4">
            {/* Can ask */}
            <div
              className="p-4 rounded-xl flex flex-col gap-3"
              style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}
            >
              <SectionLabel>What you can ask</SectionLabel>
              <ul className="flex flex-col gap-2">
                {canAsk.map((q) => (
                  <li key={q} className="flex items-start gap-2 text-sm" style={{ color: "var(--text-secondary)", fontFamily: "'Source Serif 4', serif" }}>
                    <span className="mt-1 shrink-0" style={{ color: "#5AAF72" }}>
                      <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                        <path d="M2 6L5 9L10 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </span>
                    {q}
                  </li>
                ))}
              </ul>
            </div>

            {/* Cannot */}
            <div
              className="p-4 rounded-xl flex flex-col gap-3"
              style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}
            >
              <SectionLabel>What it cannot do</SectionLabel>
              <ul className="flex flex-col gap-2">
                {cannotAsk.map((q) => (
                  <li key={q} className="flex items-start gap-2 text-sm" style={{ color: "var(--text-secondary)", fontFamily: "'Source Serif 4', serif" }}>
                    <span className="mt-1 shrink-0" style={{ color: "#C0624A" }}>
                      <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                        <path d="M3 3L9 9M9 3L3 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      </svg>
                    </span>
                    {q}
                  </li>
                ))}
              </ul>
            </div>
          </motion.div>

          {/* Tips */}
          <motion.div variants={item} className="flex flex-col gap-3">
            <SectionLabel>Tips for best results</SectionLabel>
            <div
              className="p-4 rounded-xl text-sm leading-relaxed"
              style={{
                backgroundColor: "rgba(80,125,214,0.06)",
                border: "1px solid rgba(80,125,214,0.18)",
                color: "var(--text-secondary)",
                fontFamily: "'Source Serif 4', serif",
              }}
            >
              <ul className="flex flex-col gap-2 list-disc list-inside">
                <li>Be specific — include course names or dates when relevant.</li>
                <li>If the answer seems outdated, try asking again; data is fetched live each time.</li>
                <li>Use the quick chips on the chat screen for the most common queries.</li>
                <li>Omniclaw reads <em>your</em> account only — it cannot see other students' data.</li>
              </ul>
            </div>
          </motion.div>

          {/* Footer note */}
          <motion.div variants={item}>
            <p
              className="text-xs text-center pb-2"
              style={{ color: "var(--text-muted)", fontFamily: "'Source Serif 4', serif" }}
            >
              Omniclaw is a student tool and is not officially affiliated with John Abbott College.
            </p>
          </motion.div>

        </motion.div>
      </div>
    </div>
  )
}

function SectionLabel({ children }) {
  return (
    <p
      className="text-[10px] font-medium"
      style={{ color: "var(--text-muted)", letterSpacing: "0.1em", fontFamily: "'Source Serif 4', serif" }}
    >
      {children.toUpperCase()}
    </p>
  )
}
