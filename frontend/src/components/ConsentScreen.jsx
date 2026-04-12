import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"

const dataPoints = [
  {
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
        <rect x="1" y="3" width="13" height="11" rx="1.5" stroke="currentColor" strokeWidth="1.2"/>
        <path d="M1 6.5H14" stroke="currentColor" strokeWidth="1.2"/>
        <path d="M5 1.5V4.5M10 1.5V4.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
      </svg>
    ),
    label: "Class schedule & timetable",
  },
  {
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
        <path d="M2 2H13V11H8.5L7 13.5L5.5 11H2V2Z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
      </svg>
    ),
    label: "Omnivox messages & notifications",
  },
  {
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
        <path d="M3 2H12V13L7.5 10.5L3 13V2Z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
      </svg>
    ),
    label: "Assignments & submission deadlines",
  },
  {
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
        <circle cx="7.5" cy="7.5" r="6" stroke="currentColor" strokeWidth="1.2"/>
        <path d="M7.5 4V7.5L10 9" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
      </svg>
    ),
    label: "College news & announcements",
  },
]

const consentItems = [
  {
    id: "sensitive",
    text: "I understand Omniclaw does not request, transmit, or store sensitive personal information (passwords, social insurance numbers, banking details). I will not enter such information into the chat.",
  },
  {
    id: "data",
    text: "I understand that Omniclaw will access my Omnivox account data (schedule, messages, assignments, and announcements) to answer my questions.",
  },
  {
    id: "readonly",
    text: "I understand that Omniclaw operates in read-only mode — it cannot submit assignments, send messages, or modify any account information on my behalf.",
  },
  {
    id: "unofficial",
    text: "I acknowledge that Omniclaw is a student-built tool and is not officially affiliated with or endorsed by John Abbott College.",
  },
]

export default function ConsentScreen({ onAccept }) {
  const [checked, setChecked] = useState({ sensitive: false, data: false, readonly: false, unofficial: false })
  const [declining, setDeclining] = useState(false)

  const allChecked = Object.values(checked).every(Boolean)

  const toggle = (id) => setChecked((prev) => ({ ...prev, [id]: !prev[id] }))

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.3 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-6"
      style={{ backgroundColor: "var(--bg-parchment)" }}
    >
      {/* Subtle background pattern */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage: `radial-gradient(circle at 20% 20%, rgba(80,125,214,0.06) 0%, transparent 50%),
                            radial-gradient(circle at 80% 80%, rgba(26,46,82,0.06) 0%, transparent 50%)`,
        }}
      />

      <motion.div
        initial={{ opacity: 0, y: 24, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.35, ease: [0.25, 0.46, 0.45, 0.94], delay: 0.1 }}
        className="relative w-full max-w-lg flex flex-col rounded-2xl overflow-hidden"
        style={{
          backgroundColor: "var(--bg-card)",
          border: "1px solid var(--border)",
          boxShadow: "0 8px 48px rgba(26,46,82,0.14), 0 2px 8px rgba(26,46,82,0.08)",
        }}
      >
        {/* Header band */}
        <div
          className="px-8 pt-8 pb-6"
          style={{ borderBottom: "1px solid var(--border)" }}
        >
          {/* Logo mark */}
          <div className="flex items-center gap-3 mb-6">
            <div
              className="w-9 h-9 rounded-lg flex items-center justify-center text-base font-bold"
              style={{
                backgroundColor: "var(--sidebar-bg)",
                color: "#ffffff",
                fontFamily: "'DM Serif Display', serif",
              }}
            >
              O
            </div>
            <div>
              <span
                className="text-sm font-semibold block leading-tight"
                style={{ fontFamily: "'DM Serif Display', serif", color: "var(--navy)" }}
              >
                Omniclaw
              </span>
              <span
                className="text-[10px] block"
                style={{ color: "var(--text-muted)", letterSpacing: "0.07em" }}
              >
                JAC ACADEMIC ASSISTANT
              </span>
            </div>
          </div>

          <h1
            className="text-xl mb-2 leading-snug"
            style={{ fontFamily: "'DM Serif Display', serif", color: "var(--navy)" }}
          >
            Before you get started
          </h1>
          <p
            className="text-sm leading-relaxed"
            style={{ color: "var(--text-secondary)", fontFamily: "'Source Serif 4', serif" }}
          >
            Omniclaw connects to your Omnivox account to answer your questions.
            Please review what data is accessed and confirm your consent below.
          </p>
        </div>

        {/* Data access list */}
        <div className="px-8 py-5" style={{ borderBottom: "1px solid var(--border)" }}>
          <p
            className="text-[10px] mb-3"
            style={{ color: "var(--text-muted)", letterSpacing: "0.1em" }}
          >
            DATA ACCESSED FROM YOUR OMNIVOX ACCOUNT
          </p>
          <div className="flex flex-col gap-2">
            {dataPoints.map((d) => (
              <div key={d.label} className="flex items-center gap-3">
                <span style={{ color: "var(--navy)", opacity: 0.7 }}>{d.icon}</span>
                <span
                  className="text-sm"
                  style={{ color: "var(--text-secondary)", fontFamily: "'Source Serif 4', serif" }}
                >
                  {d.label}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Consent checkboxes */}
        <div className="px-8 py-5 flex flex-col gap-4" style={{ borderBottom: "1px solid var(--border)" }}>
          <p
            className="text-[10px]"
            style={{ color: "var(--text-muted)", letterSpacing: "0.1em" }}
          >
            PLEASE READ AND CONFIRM
          </p>
          {consentItems.map((c) => (
            <label
              key={c.id}
              className="flex items-start gap-3 cursor-pointer group"
              onClick={() => toggle(c.id)}
            >
              {/* Custom checkbox */}
              <div
                className="w-4 h-4 rounded shrink-0 mt-0.5 flex items-center justify-center transition-all duration-150"
                style={{
                  backgroundColor: checked[c.id] ? "var(--sidebar-bg)" : "transparent",
                  border: `1.5px solid ${checked[c.id] ? "var(--sidebar-bg)" : "var(--border)"}`,
                }}
              >
                {checked[c.id] && (
                  <svg width="9" height="9" viewBox="0 0 9 9" fill="none">
                    <path d="M1.5 4.5L3.5 6.5L7.5 2.5" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                )}
              </div>
              <span
                className="text-xs leading-relaxed select-none"
                style={{
                  color: checked[c.id] ? "var(--text-primary)" : "var(--text-secondary)",
                  fontFamily: "'Source Serif 4', serif",
                  transition: "color 150ms",
                }}
              >
                {c.text}
              </span>
            </label>
          ))}
        </div>

        {/* Actions */}
        <div className="px-8 py-5 flex items-center justify-between gap-3">
          <AnimatePresence mode="wait">
            {declining ? (
              <motion.p
                key="decline-msg"
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0 }}
                className="text-xs"
                style={{ color: "var(--text-muted)", fontFamily: "'Source Serif 4', serif", fontStyle: "italic" }}
              >
                You need to accept to use Omniclaw.
              </motion.p>
            ) : (
              <motion.button
                key="decline-btn"
                initial={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                onClick={() => setDeclining(true)}
                className="text-sm transition-colors duration-150 cursor-pointer"
                style={{
                  color: "var(--text-muted)",
                  fontFamily: "'Source Serif 4', serif",
                  background: "none",
                  border: "none",
                  padding: 0,
                }}
              >
                Decline
              </motion.button>
            )}
          </AnimatePresence>

          <button
            onClick={() => allChecked && onAccept()}
            disabled={!allChecked}
            className="text-sm font-medium px-6 py-2.5 rounded-xl transition-all duration-200 cursor-pointer"
            style={{
              backgroundColor: allChecked ? "var(--sidebar-bg)" : "var(--border)",
              color: allChecked ? "#ffffff" : "var(--text-muted)",
              fontFamily: "'Source Serif 4', serif",
              border: "none",
              cursor: allChecked ? "pointer" : "not-allowed",
              opacity: allChecked ? 1 : 0.7,
              boxShadow: allChecked ? "0 2px 12px rgba(26,46,82,0.25)" : "none",
              transition: "all 200ms",
            }}
          >
            I agree — Continue
          </button>
        </div>
      </motion.div>
    </motion.div>
  )
}
