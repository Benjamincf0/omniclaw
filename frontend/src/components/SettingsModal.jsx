import { useState, useEffect } from "react"
import { X, Eye, EyeOff, Save, Loader2, CheckCircle, AlertCircle, RefreshCw } from "lucide-react"

// Settings API is on the MCP server (port 8000), not the orchestrator (8080)
const MCP_SERVER_URL = import.meta.env.VITE_MCP_SERVER_URL ?? "http://localhost:8000"
const ORCHESTRATOR_URL = import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8080"

export default function SettingsModal({ onClose }) {
  const [fields, setFields] = useState([])
  const [values, setValues] = useState({})
  const [revealed, setRevealed] = useState({})
  const [saving, setSaving] = useState(false)
  const [reloading, setReloading] = useState(false)
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState(null)

  useEffect(() => {
    fetch(`${MCP_SERVER_URL}/api/settings`)
      .then((r) => r.json())
      .then((data) => {
        setFields(data.fields)
        const vals = {}
        data.fields.forEach((f) => {
          vals[f.key] = f.secret ? "" : f.value
        })
        setValues(vals)
        setLoading(false)
      })
      .catch(() => {
        setMessage({ type: "error", text: "Failed to load settings" })
        setLoading(false)
      })
  }, [])

  const handleSave = async () => {
    setSaving(true)
    setMessage(null)
    try {
      // 1. Save settings to .env
      const res = await fetch(`${MCP_SERVER_URL}/api/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ settings: values }),
      })
      if (!res.ok) throw new Error("Failed to save")
      
      // 2. Hot reload orchestrator to pick up changes
      let reloadResult = null
      try {
        const reloadRes = await fetch(`${ORCHESTRATOR_URL}/reload`, { method: "POST" })
        if (reloadRes.ok) {
          reloadResult = await reloadRes.json()
        }
      } catch {
        // Reload failed, but save succeeded
      }
      
      // 3. Show success message
      const successMsg = reloadResult 
        ? `Saved & reloaded! Provider: ${reloadResult.new_provider}`
        : "Settings saved! Restart orchestrator to apply changes."
      setMessage({ type: "success", text: successMsg })
      
      // Close modal after a short delay to show success message
      setTimeout(() => {
        onClose()
      }, 1500)
    } catch {
      setMessage({ type: "error", text: "Failed to save settings" })
      setSaving(false)
    }
  }

  const handleReload = async () => {
    setReloading(true)
    setMessage(null)
    try {
      const res = await fetch(`${ORCHESTRATOR_URL}/reload`, { method: "POST" })
      if (!res.ok) throw new Error()
      const data = await res.json()
      setMessage({ 
        type: "success", 
        text: `Reloaded! Provider: ${data.old_provider} → ${data.new_provider}` 
      })
    } catch {
      setMessage({ type: "error", text: "Failed to reload orchestrator" })
    } finally {
      setReloading(false)
    }
  }

  const groups = {}
  fields.forEach((f) => {
    if (!groups[f.group]) groups[f.group] = []
    groups[f.group].push(f)
  })

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-[#16161a] border border-[#2a2a32] rounded-2xl w-full max-w-lg max-h-[85vh] flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#2a2a32] shrink-0">
          <h2 className="text-[#e8e8f0] font-semibold text-base">Settings</h2>
          <button
            onClick={onClose}
            className="text-[#6b6b7a] hover:text-[#e8e8f0] transition-colors cursor-pointer"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">
          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="animate-spin text-[#6b6b7a]" size={24} />
            </div>
          ) : (
            Object.entries(groups).map(([group, groupFields]) => (
              <div key={group}>
                <h3 className="text-xs font-semibold text-[#6b6b7a] uppercase tracking-wider mb-3">
                  {group}
                </h3>
                <div className="space-y-3">
                  {groupFields.map((field) => (
                    <div key={field.key}>
                      <label className="block text-sm text-[#a0a0b0] mb-1.5">
                        {field.label}
                      </label>

                      {field.type === "select" ? (
                        <select
                          value={values[field.key] ?? ""}
                          onChange={(e) =>
                            setValues((v) => ({ ...v, [field.key]: e.target.value }))
                          }
                          className="w-full bg-[#1a1a1f] border border-[#2a2a32] focus:border-[#6c63ff]/60 focus:outline-none text-[#e8e8f0] text-sm px-3 py-2.5 rounded-lg transition-colors appearance-none cursor-pointer"
                        >
                          <option value="">— not set —</option>
                          {field.options?.map((opt) => (
                            <option key={opt} value={opt}>
                              {opt}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <div className="relative">
                          <input
                            type={field.secret && !revealed[field.key] ? "password" : "text"}
                            value={values[field.key] ?? ""}
                            onChange={(e) =>
                              setValues((v) => ({ ...v, [field.key]: e.target.value }))
                            }
                            placeholder={
                              field.secret && field.is_set
                                ? `Configured (${field.value}) — leave blank to keep`
                                : ""
                            }
                            className="w-full bg-[#1a1a1f] border border-[#2a2a32] focus:border-[#6c63ff]/60 focus:outline-none text-[#e8e8f0] placeholder-[#4a4a55] text-sm px-3 py-2.5 rounded-lg pr-10 transition-colors"
                          />
                          {field.secret && (
                            <button
                              type="button"
                              onClick={() =>
                                setRevealed((r) => ({ ...r, [field.key]: !r[field.key] }))
                              }
                              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#6b6b7a] hover:text-[#e8e8f0] transition-colors cursor-pointer"
                            >
                              {revealed[field.key] ? <EyeOff size={15} /> : <Eye size={15} />}
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        {!loading && (
          <div className="px-6 py-4 border-t border-[#2a2a32] shrink-0 flex items-center gap-3">
            {message && (
              <div className={`flex items-center gap-1.5 text-xs ${message.type === "error" ? "text-red-400" : "text-emerald-400"}`}>
                {message.type === "error" ? <AlertCircle size={13} /> : <CheckCircle size={13} />}
                {message.text}
              </div>
            )}
            <div className="ml-auto flex items-center gap-2">
              <button
                onClick={handleReload}
                disabled={reloading}
                className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#2a2a32] hover:bg-[#3a3a42] disabled:opacity-50 text-[#a0a0b0] hover:text-[#e8e8f0] text-sm font-medium transition-all cursor-pointer"
                title="Reload orchestrator config"
              >
                <RefreshCw className={reloading ? "animate-spin" : ""} size={14} />
                Reload
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#6c63ff] hover:bg-[#7d75ff] disabled:opacity-50 text-white text-sm font-medium transition-all cursor-pointer"
              >
                {saving ? <Loader2 className="animate-spin" size={14} /> : <Save size={14} />}
                Save
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
