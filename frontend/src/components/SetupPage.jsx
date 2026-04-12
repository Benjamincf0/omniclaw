import { useState } from "react"
import { useAuth0 } from "@auth0/auth0-react"
import { motion } from "framer-motion"
import { useNavigate } from "react-router-dom"

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8000"

export default function SetupPage() {
  const { getAccessTokenSilently, user, logout } = useAuth0()
  const navigate = useNavigate()

  const [studentId, setStudentId] = useState("")
  const [password, setPassword] = useState("")
  const [status, setStatus] = useState("idle") // idle | loading | success | error
  const [errorMsg, setErrorMsg] = useState("")

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!studentId.trim() || !password) return

    setStatus("loading")
    setErrorMsg("")

    try {
      const token = await getAccessTokenSilently()

      const res = await fetch(`${BACKEND_URL}/setup-omnivox`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ email: studentId.trim(), password }),
      })

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.detail ?? `Server error ${res.status}`)
      }

      setStatus("success")
      // Redirect to the chat after a short delay so the user sees the success state.
      setTimeout(() => navigate("/"), 1800)
    } catch (err) {
      setStatus("error")
      setErrorMsg(err.message ?? "Something went wrong.")
    }
  }

  if (status === "success") {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-[#0f0f11] px-4">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="flex flex-col items-center gap-4 text-center"
        >
          <div className="w-14 h-14 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <path d="M5 13l4 4L19 7" stroke="#34d399" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <h2 className="text-[#e8e8f0] font-semibold text-lg">Omnivox connected!</h2>
          <p className="text-[#6b6b7a] text-sm">Taking you to the chat...</p>
        </motion.div>
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center justify-center h-screen bg-[#0f0f11] px-4">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="w-full max-w-sm flex flex-col gap-6"
      >
        {/* Header */}
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="w-12 h-12 rounded-2xl bg-[#6c63ff]/10 border border-[#6c63ff]/30 flex items-center justify-center">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <path d="M13 2L4.5 13.5H12L11 22L19.5 10.5H12L13 2Z" fill="#6c63ff" />
            </svg>
          </div>
          <div>
            <h1 className="text-[#e8e8f0] font-semibold text-xl tracking-tight">Connect Omnivox</h1>
            <p className="text-[#6b6b7a] text-sm mt-1 leading-relaxed max-w-xs">
              Enter your JAC Omnivox credentials. We log in once to capture your session — your password is never stored.
            </p>
          </div>
        </div>

        {/* Form card */}
        <form
          onSubmit={handleSubmit}
          className="w-full bg-[#1a1a1f] border border-[#2a2a32] rounded-2xl p-6 flex flex-col gap-4"
        >
          {/* Student ID */}
          <div className="flex flex-col gap-1.5">
            <label className="text-[#a0a0b0] text-xs font-medium uppercase tracking-wide">
              Omnivox student ID
            </label>
            <input
              type="text"
              inputMode="numeric"
              pattern="\d{7}"
              value={studentId}
              onChange={(e) => setStudentId(e.target.value)}
              placeholder="1234567"
              required
              autoComplete="username"
              disabled={status === "loading"}
              className="h-11 bg-[#0f0f11] border border-[#2a2a32] focus:border-[#6c63ff]/60 focus:outline-none text-[#e8e8f0] placeholder-[#6b6b7a] text-sm px-4 rounded-xl transition-colors duration-150 disabled:opacity-50"
            />
          </div>

          {/* Password */}
          <div className="flex flex-col gap-1.5">
            <label className="text-[#a0a0b0] text-xs font-medium uppercase tracking-wide">
              Omnivox password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              autoComplete="current-password"
              disabled={status === "loading"}
              className="h-11 bg-[#0f0f11] border border-[#2a2a32] focus:border-[#6c63ff]/60 focus:outline-none text-[#e8e8f0] placeholder-[#6b6b7a] text-sm px-4 rounded-xl transition-colors duration-150 disabled:opacity-50"
            />
          </div>

          {/* Error */}
          {status === "error" && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-3 text-sm text-red-400"
            >
              {errorMsg}
            </motion.div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={!studentId.trim() || !password || status === "loading"}
            className="h-11 rounded-xl bg-[#6c63ff] hover:bg-[#7d75ff] disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium transition-all duration-150 cursor-pointer mt-1 flex items-center justify-center gap-2"
          >
            {status === "loading" ? (
              <>
                <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                Connecting...
              </>
            ) : (
              "Connect Omnivox"
            )}
          </button>
        </form>

        {/* Note */}
        <div className="bg-[#1a1a1f] border border-[#2a2a32] rounded-xl px-4 py-3 flex gap-3">
          <span className="text-[#6b6b7a] text-xs leading-relaxed">
            <span className="text-[#a0a0b0] font-medium">Why do we need this?</span>{" "}
            Omnivox doesn't have a public API. We use your credentials once to capture a session cookie, then discard the password. The cookie is stored securely on our server.
          </span>
        </div>

        {/* Sign out link */}
        <button
          onClick={() => logout({ logoutParams: { returnTo: window.location.origin } })}
          className="text-[#6b6b7a] text-xs hover:text-[#a0a0b0] transition-colors text-center cursor-pointer"
        >
          Sign out
        </button>
      </motion.div>
    </div>
  )
}
