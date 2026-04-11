export default function Header() {
  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-[#2a2a32]">
      <div className="flex items-center gap-2.5">
        <span className="font-semibold text-[#e8e8f0] tracking-tight text-lg">
          Omniclaw
        </span>
        <span className="text-xs text-[#6b6b7a] font-medium bg-[#1a1a1f] border border-[#2a2a32] px-2 py-0.5 rounded-full">
          JAC
        </span>
      </div>

      <div className="flex items-center gap-2 text-xs text-[#6b6b7a]">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
        Live
      </div>
    </header>
  )
}
