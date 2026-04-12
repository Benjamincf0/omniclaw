import { motion } from "framer-motion"

export default function TypingIndicator() {
  return (
    <div className="flex items-end gap-2.5 px-4 py-1.5">
      <div
        className="w-6 h-6 rounded-full shrink-0 mb-1 flex items-center justify-center text-[9px] font-bold"
        style={{
          backgroundColor: "var(--navy)",
          color: "#C8B89A",
          fontFamily: "'DM Serif Display', serif",
        }}
      >
        O
      </div>
      <div
        className="rounded-2xl rounded-bl-sm px-4 py-3"
        style={{
          backgroundColor: "var(--bg-card)",
          border: "1px solid var(--border)",
          boxShadow: "0 1px 4px rgba(28,43,74,0.06)",
        }}
      >
        <div className="flex gap-1 items-center h-4">
          {[0, 1, 2].map((i) => (
            <motion.span
              key={i}
              className="w-1.5 h-1.5 rounded-full"
              style={{ backgroundColor: "var(--navy-muted)" }}
              animate={{ opacity: [0.3, 1, 0.3], y: [0, -3, 0] }}
              transition={{ duration: 1, repeat: Infinity, delay: i * 0.2 }}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
