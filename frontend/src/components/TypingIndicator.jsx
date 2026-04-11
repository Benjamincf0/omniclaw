import { motion } from "framer-motion"

export default function TypingIndicator() {
  return (
    <div className="flex items-end gap-2 px-4 py-1.5">
      <div className="w-1.5 h-1.5 rounded-full shrink-0 mb-3 bg-[#2a2a32]" />
      <div className="bg-[#1a1a1f] border border-[#2a2a32] rounded-2xl rounded-bl-sm px-4 py-3">
        <div className="flex gap-1 items-center h-4">
          {[0, 1, 2].map((i) => (
            <motion.span
              key={i}
              className="w-1.5 h-1.5 rounded-full bg-[#6b6b7a]"
              animate={{ opacity: [0.3, 1, 0.3], y: [0, -3, 0] }}
              transition={{ duration: 1, repeat: Infinity, delay: i * 0.2 }}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
