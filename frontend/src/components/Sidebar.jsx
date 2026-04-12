const navItems = [
  {
    id: "chat",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path d="M2 5.5L8 2L14 5.5V14H10V10H6V14H2V5.5Z" stroke="currentColor" strokeWidth="1.25" strokeLinejoin="round"/>
      </svg>
    ),
    label: "Home",
  },
  {
    id: "schedule",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <rect x="2" y="2" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.25"/>
        <rect x="9" y="2" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.25"/>
        <rect x="2" y="9" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.25"/>
        <rect x="9" y="9" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.25"/>
      </svg>
    ),
    label: "Schedule",
    soon: true,
  },
  {
    id: "messages",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path d="M2 3H14V11H9L6 14V11H2V3Z" stroke="currentColor" strokeWidth="1.25" strokeLinejoin="round"/>
      </svg>
    ),
    label: "Messages",
    soon: true,
  },
  {
    id: "grades",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path d="M8 2L9.8 5.8L14 6.3L11 9.2L11.7 13.4L8 11.4L4.3 13.4L5 9.2L2 6.3L6.2 5.8L8 2Z" stroke="currentColor" strokeWidth="1.25" strokeLinejoin="round"/>
      </svg>
    ),
    label: "Grades",
    soon: true,
  },
  {
    id: "profile",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <circle cx="8" cy="5" r="3" stroke="currentColor" strokeWidth="1.25"/>
        <path d="M2 14C2 11.2 4.7 9 8 9C11.3 9 14 11.2 14 14" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round"/>
      </svg>
    ),
    label: "Profile",
    soon: true,
  },
]

const bottomItems = [
  {
    id: "howto",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.25"/>
        <path d="M6.5 6C6.5 5.17 7.17 4.5 8 4.5C8.83 4.5 9.5 5.17 9.5 6C9.5 6.83 8 7.5 8 8.5" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round"/>
        <circle cx="8" cy="11" r="0.75" fill="currentColor"/>
      </svg>
    ),
    label: "How to Use",
  },
]

export default function Sidebar({ activePage, onNavigate }) {
  return (
    <aside
      className="flex flex-col h-full shrink-0"
      style={{
        width: "220px",
        backgroundColor: "var(--navy)",
        borderRight: "1px solid rgba(255,255,255,0.07)",
      }}
    >
      {/* Logo area */}
      <div
        className="flex items-center gap-3 px-5 py-5"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.07)" }}
      >
        <div
          className="w-8 h-8 rounded-sm flex items-center justify-center text-sm font-bold shrink-0"
          style={{
            backgroundColor: "rgba(200,184,154,0.15)",
            color: "#C8B89A",
            fontFamily: "'DM Serif Display', serif",
            border: "1px solid rgba(200,184,154,0.2)",
          }}
        >
          O
        </div>
        <div>
          <span
            className="text-sm font-semibold block leading-tight"
            style={{ fontFamily: "'DM Serif Display', serif", color: "#EDE8DC" }}
          >
            Omniclaw
          </span>
          <span
            className="text-[10px] block leading-tight"
            style={{ color: "rgba(200,184,154,0.6)", letterSpacing: "0.06em" }}
          >
            JAC
          </span>
        </div>
      </div>

      {/* Main nav */}
      <nav className="flex flex-col gap-1 px-3 py-4 flex-1">
        <p
          className="text-[10px] px-2 mb-2"
          style={{ color: "rgba(200,184,154,0.4)", letterSpacing: "0.1em" }}
        >
          NAVIGATION
        </p>
        {navItems.map((item) => (
          <NavButton
            key={item.id}
            item={item}
            active={activePage === item.id}
            onClick={() => !item.soon && onNavigate(item.id)}
          />
        ))}
      </nav>

      {/* Bottom nav (Help, Settings, etc.) */}
      <div
        className="flex flex-col gap-1 px-3 py-3"
        style={{ borderTop: "1px solid rgba(255,255,255,0.07)" }}
      >
        {bottomItems.map((item) => (
          <NavButton
            key={item.id}
            item={item}
            active={activePage === item.id}
            onClick={() => onNavigate(item.id)}
          />
        ))}

        {/* Connected pill */}
        <div className="flex items-center gap-2 px-3 pt-3">
          <span
            className="w-1.5 h-1.5 rounded-full animate-pulse"
            style={{ backgroundColor: "#5AAF72" }}
          />
          <span
            className="text-[11px]"
            style={{ color: "rgba(200,184,154,0.5)", fontFamily: "'Source Serif 4', serif" }}
          >
            Connected to Omnivox
          </span>
        </div>
      </div>
    </aside>
  )
}

function NavButton({ item, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm w-full text-left transition-all duration-150 cursor-pointer"
      style={
        active
          ? {
              backgroundColor: "rgba(200,184,154,0.12)",
              color: "#EDE8DC",
              border: "1px solid rgba(200,184,154,0.15)",
            }
          : {
              backgroundColor: "transparent",
              color: item.soon ? "rgba(200,184,154,0.35)" : "rgba(200,184,154,0.55)",
              border: "1px solid transparent",
              cursor: item.soon ? "default" : "pointer",
            }
      }
    >
      <span style={{ opacity: active ? 1 : item.soon ? 0.35 : 0.6 }}>{item.icon}</span>
      <span style={{ fontFamily: "'Source Serif 4', serif", fontSize: "0.8125rem" }}>
        {item.label}
      </span>
      {item.soon && (
        <span
          className="ml-auto text-[9px] px-1.5 py-0.5 rounded"
          style={{
            backgroundColor: "rgba(200,184,154,0.08)",
            color: "rgba(200,184,154,0.35)",
            letterSpacing: "0.06em",
          }}
        >
          SOON
        </span>
      )}
    </button>
  )
}
