import { motion } from "framer-motion"
import ReactMarkdown from "react-markdown"

export default function Message({ role, content }) {
  const isUser = role === "user"

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: [0.25, 0.46, 0.45, 0.94] }}
      className={`flex items-end gap-2.5 px-4 py-1.5 ${isUser ? "flex-row-reverse" : ""}`}
    >
      {/* Avatar */}
      {!isUser && (
        <div
          className="w-6 h-6 rounded-full shrink-0 mb-1 flex items-center justify-center text-[9px] font-bold"
          style={{
            backgroundColor: "var(--navy)",
            color: "#C8B89A",
            fontFamily: "'DM Serif Display', serif",
            flexShrink: 0,
          }}
        >
          O
        </div>
      )}

      {/* Bubble */}
      <div
        className={`max-w-[76%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          isUser ? "rounded-br-sm" : "rounded-bl-sm"
        }`}
        style={
          isUser
            ? {
                backgroundColor: "var(--navy)",
                color: "#EDE8DC",
                fontFamily: "'Source Serif 4', serif",
              }
            : {
                backgroundColor: "var(--bg-card)",
                border: "1px solid var(--border)",
                color: "var(--text-primary)",
                fontFamily: "'Source Serif 4', serif",
                boxShadow: "0 1px 4px rgba(28,43,74,0.06)",
              }
        }
      >
        {isUser ? (
          content
        ) : (
          <div className="prose">
            <ReactMarkdown>{content}</ReactMarkdown>
          </div>
        )}
      </div>
    </motion.div>
  )
}
