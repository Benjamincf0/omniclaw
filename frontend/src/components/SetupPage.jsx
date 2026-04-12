import { useState, useRef, useEffect } from "react"
import { useAuth0 } from "@auth0/auth0-react"
import { motion } from "framer-motion"
import { useNavigate } from "react-router-dom"

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8000"

export default function SetupPage() {
  const { getAccessTokenSilently, logout } = useAuth0()
  const navigate = useNavigate()

  const [studentId, setStudentId] = useState("")
  const [password, setPassword] = useState("")
  // status: "idle" | "loading" | "polling" | "needs_otp" | "success" | "error"
  const [status, setStatus] = useState("idle")
  const [errorMsg, setErrorMsg] = useState("")
  const [sessionId, setSessionId] = useState("")
  const [otpCode, setOtpCode] = useState("")
  const [otpSubmitting, setOtpSubmitting] = useState(false)

  // Holds the setInterval ID for the status-poll loop.
  const pollRef = useRef(null)

  // Clear poll on unmount.
  useEffect(() => () => clearInterval(pollRef.current), [])

  function startPolling(sid) {
    clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/setup-status?session_id=${sid}`)
        if (!res.ok) {
          clearInterval(pollRef.current)
          setStatus("error")
          setErrorMsg(`Status check failed (${res.status})`)
          return
        }
        const data = await res.json()
        if (data.status === "needs_otp") {
          setStatus("needs_otp")
        } else if (data.status === "success") {
          clearInterval(pollRef.current)
          setStatus("success")
          setTimeout(() => navigate("/"), 1800)
        } else if (data.status === "error") {
          clearInterval(pollRef.current)
          setStatus("error")
          setErrorMsg(data.detail ?? "Omnivox login failed.")
        }
        // "running" → do nothing, poll again next tick
      } catch (err) {
        clearInterval(pollRef.current)
        setStatus("error")
        setErrorMsg(err.message ?? "Network error while checking status.")
      }
    }, 1500)
  }

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
      if (!res.ok) throw new Error(data.detail ?? `Server error ${res.status}`)

      setSessionId(data.session_id)
      setStatus("polling")
      startPolling(data.session_id)
    } catch (err) {
      setStatus("error")
      setErrorMsg(err.message ?? "Something went wrong.")
    }
  }

  const handleOtpSubmit = async (e) => {
    e.preventDefault()
    if (!otpCode.trim() || otpSubmitting) return

    setOtpSubmitting(true)
    try {
      const res = await fetch(`${BACKEND_URL}/setup-2fa`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, code: otpCode.trim() }),
      })
      if (!res.ok) {
        const data = await res.json()
        clearInterval(pollRef.current)
        setStatus("error")
        setErrorMsg(data.detail ?? "Failed to submit verification code.")
      }
      // On success the poll loop detects the final state; keep otpSubmitting true
      // so the button stays disabled while Playwright finishes.
    } catch (err) {
      clearInterval(pollRef.current)
      setStatus("error")
      setErrorMsg(err.message ?? "Network error.")
    }
  }

  // ── Success screen ────────────────────────────────────────────────────────

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

  // ── 2FA screen ────────────────────────────────────────────────────────────

  if (status === "needs_otp") {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-[#0f0f11] px-4">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="w-full max-w-sm flex flex-col gap-6"
        >
          <div className="flex flex-col items-center gap-3 text-center">
            <div className="w-12 h-12 rounded-2xl bg-[#6c63ff]/10 border border-[#6c63ff]/30 flex items-center justify-center">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                <rect x="5" y="11" width="14" height="10" rx="2" stroke="#6c63ff" strokeWidth="2" />
                <path d="M8 11V7a4 4 0 018 0v4" stroke="#6c63ff" strokeWidth="2" strokeLinecap="round" />
              </svg>
            </div>
            <div>
              <h1 className="text-[#e8e8f0] font-semibold text-xl tracking-tight">Verification code</h1>
              <p className="text-[#6b6b7a] text-sm mt-1 leading-relaxed max-w-xs">
                Omnivox sent you a verification code. Enter it below to finish connecting.
              </p>
            </div>
          </div>

          <form
            onSubmit={handleOtpSubmit}
            className="w-full bg-[#1a1a1f] border border-[#2a2a32] rounded-2xl p-6 flex flex-col gap-4"
          >
            <div className="flex flex-col gap-1.5">
              <label className="text-[#a0a0b0] text-xs font-medium uppercase tracking-wide">
                Verification code
              </label>
              <input
                type="text"
                inputMode="numeric"
                value={otpCode}
                onChange={(e) => setOtpCode(e.target.value)}
                placeholder="123456"
                required
                autoFocus
                autoComplete="one-time-code"
                disabled={otpSubmitting}
                className="h-11 bg-[#0f0f11] border border-[#2a2a32] focus:border-[#6c63ff]/60 focus:outline-none text-[#e8e8f0] placeholder-[#6b6b7a] text-sm px-4 rounded-xl transition-colors duration-150 disabled:opacity-50 tracking-widest text-center"
              />
            </div>

            <button
              type="submit"
              disabled={!otpCode.trim() || otpSubmitting}
              className="h-11 rounded-xl bg-[#6c63ff] hover:bg-[#7d75ff] disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium transition-all duration-150 cursor-pointer flex items-center justify-center gap-2"
            >
              {otpSubmitting ? (
                <>
                  <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  Verifying...
                </>
              ) : (
                "Submit code"
              )}
            </button>
          </form>
        </motion.div>
      </div>
    )
  }

  // ── Credentials form (idle | loading | polling | error) ──────────────────

  const isConnecting = status === "loading" || status === "polling"

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
              disabled={isConnecting}
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
              disabled={isConnecting}
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
            disabled={!studentId.trim() || !password || isConnecting}
            className="h-11 rounded-xl bg-[#6c63ff] hover:bg-[#7d75ff] disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium transition-all duration-150 cursor-pointer mt-1 flex items-center justify-center gap-2"
          >
            {isConnecting ? (
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
