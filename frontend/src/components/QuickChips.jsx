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
          className="text-sm px-4 py-2 rounded-full transition-all duration-150 cursor-pointer"
          style={{
            backgroundColor: "var(--bg-card)",
            border: "1px solid var(--border)",
            color: "var(--navy-muted)",
            fontFamily: "'Source Serif 4', serif",
            fontSize: "0.8125rem",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = "var(--navy)"
            e.currentTarget.style.color = "#EDE8DC"
            e.currentTarget.style.borderColor = "var(--navy)"
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = "var(--bg-card)"
            e.currentTarget.style.color = "var(--navy-muted)"
            e.currentTarget.style.borderColor = "var(--border)"
          }}
        >
          {label}
        </button>
      ))}
    </div>
  )
}
