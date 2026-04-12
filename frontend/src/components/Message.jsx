import { motion } from "framer-motion"
import ReactMarkdown from "react-markdown"

export default function Message({ role, content, timestamp }) {
  const isUser = role === "user"
  
  // Format timestamp if provided
  const timeStr = timestamp 
    ? new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : null

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
          className="w-7 h-7 rounded-full shrink-0 mb-1 flex items-center justify-center text-[10px] font-bold"
          style={{
            backgroundColor: "var(--navy)",
            color: "#C8B89A",
            fontFamily: "'DM Serif Display', serif",
            flexShrink: 0,
            boxShadow: "0 0 0 2px rgba(80,125,214,0.15), 0 2px 4px rgba(28,43,74,0.1)",
          }}
        >
          O
        </div>
      )}

      {/* Bubble + timestamp wrapper */}
      <div className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}>
        <div
          className={`max-w-[76%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
            isUser ? "rounded-br-sm" : "rounded-bl-sm"
          }`}
          style={
            isUser
              ? {
                  backgroundColor: "#5a82d4", /* Slightly lighter than header navy */
                  color: "#F5F0E6",
                  fontFamily: "'Source Serif 4', serif",
                  boxShadow: "0 2px 6px rgba(80,125,214,0.25)",
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
        
        {/* Timestamp */}
        {timeStr && (
          <span 
            className="text-[10px] mt-1 px-1"
            style={{ color: "var(--text-muted)", fontFamily: "'Source Serif 4', serif" }}
          >
            {timeStr}
          </span>
        )}
      </div>
    </motion.div>
  )
}
