import { useAuth0 } from "@auth0/auth0-react"
import { motion } from "framer-motion"

export default function AuthPage() {
  const { loginWithRedirect, isLoading } = useAuth0()

  return (
    <div className="flex flex-col items-center justify-center h-screen bg-[#0f0f11] px-4">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="w-full max-w-sm flex flex-col items-center gap-8"
      >
        {/* Logo */}
        <div className="flex flex-col items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-[#6c63ff]/10 border border-[#6c63ff]/30 flex items-center justify-center">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <path d="M13 2L4.5 13.5H12L11 22L19.5 10.5H12L13 2Z" fill="#6c63ff" />
            </svg>
          </div>
          <div className="text-center">
            <h1 className="text-[#e8e8f0] font-semibold text-xl tracking-tight">Omniclaw</h1>
            <p className="text-[#6b6b7a] text-sm mt-1">Your JAC Omnivox assistant</p>
          </div>
        </div>

        {/* Card */}
        <div className="w-full bg-[#1a1a1f] border border-[#2a2a32] rounded-2xl p-6 flex flex-col gap-5">
          <div className="text-center">
            <h2 className="text-[#e8e8f0] font-semibold text-base">Get started</h2>
            <p className="text-[#6b6b7a] text-sm mt-1 leading-relaxed">
              Sign in or create a free account to connect your Omnivox.
            </p>
          </div>

          <button
            onClick={() => loginWithRedirect({ authorizationParams: { screen_hint: "signup" } })}
            disabled={isLoading}
            className="w-full h-11 rounded-xl bg-[#6c63ff] hover:bg-[#7d75ff] disabled:opacity-40 text-white text-sm font-medium transition-all duration-150 cursor-pointer"
          >
            Create account
          </button>

          <div className="flex items-center gap-3">
            <div className="flex-1 h-px bg-[#2a2a32]" />
            <span className="text-[#6b6b7a] text-xs">or</span>
            <div className="flex-1 h-px bg-[#2a2a32]" />
          </div>

          <button
            onClick={() => loginWithRedirect()}
            disabled={isLoading}
            className="w-full h-11 rounded-xl bg-transparent border border-[#2a2a32] hover:border-[#6c63ff]/50 hover:bg-[#6c63ff]/5 text-[#e8e8f0] text-sm font-medium transition-all duration-150 cursor-pointer"
          >
            Sign in
          </button>
        </div>

        <p className="text-[#6b6b7a] text-xs text-center leading-relaxed max-w-xs">
          By continuing you agree that Omniclaw may access your Omnivox data on your behalf.
        </p>
      </motion.div>
    </div>
  )
}
