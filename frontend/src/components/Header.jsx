import { useState, useRef, useEffect } from "react"
import { useAuth0 } from "@auth0/auth0-react"
import { useNavigate } from "react-router-dom"
import { Settings } from "lucide-react"

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8000"

export default function Header({ onSettingsClick }) {
  const { isAuthenticated, user, logout, getAccessTokenSilently } = useAuth0()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef(null)

  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  const handleLogout = () => {
    setMenuOpen(false)
    logout({ logoutParams: { returnTo: window.location.origin + "/auth" } })
  }

  const handleReconnect = () => {
    setMenuOpen(false)
    navigate("/setup")
  }

  const handleDisconnect = async () => {
    setMenuOpen(false)
    try {
      const token = await getAccessTokenSilently()
      await fetch(`${BACKEND_URL}/unlink-omnivox`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      })
    } catch {
      // Ignore errors — navigate away regardless so the user isn't stuck.
    }
    navigate("/")
  }

  return (
    <header
      className="flex items-center justify-between px-6 py-4 shrink-0"
      style={{
        backgroundColor: "var(--bg-card)",
        borderBottom: "1px solid var(--border)",
      }}
    >
      <div>
        <h1
          className="text-base font-semibold leading-tight"
          style={{
            fontFamily: "'DM Serif Display', serif",
            color: "var(--navy)",
            letterSpacing: "-0.01em",
          }}
        >
          Chat
        </h1>
        <p
          className="text-[11px] leading-tight"
          style={{ color: "var(--text-muted)", letterSpacing: "0.04em" }}
        >
          Ask me anything about Omnivox
        </p>
      </div>

      {/* Right: live indicator + settings + user menu */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5 text-xs text-[#6b6b7a]">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          Live
        </div>

        {onSettingsClick && (
          <button
            onClick={onSettingsClick}
            className="text-[#6b6b7a] hover:text-[#e8e8f0] transition-colors cursor-pointer"
            aria-label="Settings"
          >
            <Settings size={16} />
          </button>
        )}

        {isAuthenticated && user && (
          <div className="relative" ref={menuRef}>
            <button
              onClick={() => setMenuOpen((o) => !o)}
              className="flex items-center gap-2 cursor-pointer group"
              aria-label="User menu"
            >
              {user.picture ? (
                <img
                  src={user.picture}
                  alt={user.name ?? "User"}
                  className="w-7 h-7 rounded-full border border-[#2a2a32] group-hover:border-[#6c63ff]/50 transition-colors"
                />
              ) : (
                <div className="w-7 h-7 rounded-full bg-[#6c63ff]/20 border border-[#6c63ff]/30 flex items-center justify-center text-[#6c63ff] text-xs font-semibold group-hover:bg-[#6c63ff]/30 transition-colors">
                  {(user.name ?? user.email ?? "?")[0].toUpperCase()}
                </div>
              )}
            </button>

            {menuOpen && (
              <div className="absolute right-0 top-full mt-2 w-52 bg-[#1a1a1f] border border-[#2a2a32] rounded-xl shadow-xl z-50 overflow-hidden">
                {/* User info */}
                <div className="px-4 py-3 border-b border-[#2a2a32]">
                  <p className="text-[#e8e8f0] text-sm font-medium truncate">
                    {user.name ?? "Student"}
                  </p>
                  <p className="text-[#6b6b7a] text-xs truncate mt-0.5">
                    {user.email ?? ""}
                  </p>
                </div>

                {/* Actions */}
                <div className="py-1">
                  <button
                    onClick={handleReconnect}
                    className="w-full text-left px-4 py-2.5 text-sm text-[#a0a0b0] hover:text-[#e8e8f0] hover:bg-[#6c63ff]/5 transition-colors cursor-pointer"
                  >
                    Reconnect Omnivox
                  </button>
                  <button
                    onClick={handleDisconnect}
                    className="w-full text-left px-4 py-2.5 text-sm text-[#a0a0b0] hover:text-red-400 hover:bg-red-500/5 transition-colors cursor-pointer"
                  >
                    Disconnect Omnivox
                  </button>
                  <button
                    onClick={handleLogout}
                    className="w-full text-left px-4 py-2.5 text-sm text-[#a0a0b0] hover:text-red-400 hover:bg-red-500/5 transition-colors cursor-pointer"
                  >
                    Sign out
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  )
}
