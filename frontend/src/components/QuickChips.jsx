const chips = [
  "My schedule today",
  "Any new messages?",
  "What's due this week?",
  "Latest college news",
]

export default function QuickChips({ onSelect }) {
  return (
    <div className="flex flex-wrap gap-2 justify-center px-4 pb-2">
      {chips.map((label) => (
        <button
          key={label}
          onClick={() => onSelect(label)}
          className="text-sm bg-[#1a1a1f] border border-[#2a2a32] hover:border-[#6c63ff]/50 hover:bg-[#6c63ff]/5 text-[#a0a0b0] hover:text-[#e8e8f0] px-4 py-2 rounded-full transition-all duration-150 cursor-pointer"
        >
          {label}
        </button>
      ))}
    </div>
  )
}
