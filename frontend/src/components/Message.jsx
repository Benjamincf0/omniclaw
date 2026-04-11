import { motion } from "framer-motion"
import ReactMarkdown from "react-markdown"

export default function Message({ role, content }) {
  const isUser = role === "user"

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={`flex items-end gap-2 px-4 py-1.5 ${isUser ? "flex-row-reverse" : ""}`}
    >
      {/* Avatar dot */}
      <div
        className={`w-1.5 h-1.5 rounded-full shrink-0 mb-3 ${
          isUser ? "bg-[#6c63ff]" : "bg-[#2a2a32]"
        }`}
      />

      {/* Bubble */}
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? "bg-[#6c63ff] text-white rounded-br-sm"
            : "bg-[#1a1a1f] border border-[#2a2a32] text-[#e8e8f0] rounded-bl-sm"
        }`}
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
