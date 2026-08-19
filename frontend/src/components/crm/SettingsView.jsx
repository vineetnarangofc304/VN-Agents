import { useState } from "react";
import axios from "axios";
import { Settings, Key, Loader2, CheckCircle, XCircle, Plug } from "lucide-react";

export default function SettingsView({ API, cookieStatus, setCookieStatus, fetchCookieStatus }) {
  const [liAt, setLiAt] = useState("");
  const [jsessionId, setJsessionId] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);

  const handleSaveCookie = async () => {
    if (!liAt.trim()) return;
    setSaving(true); setMsg(null);
    try {
      const res = await axios.post(`${API}/li-search/cookie`, {
        li_at: liAt.trim(), jsessionid: jsessionId.trim() || null
      });
      if (res.data.warning) {
        setMsg({ type: "warn", text: `Cookie saved. ${res.data.warning}` });
      } else {
        setMsg({ type: "success", text: `Connected as ${res.data.profile}` });
      }
      fetchCookieStatus();
      setLiAt(""); setJsessionId("");
    } catch (err) {
      setMsg({ type: "error", text: err.response?.data?.detail || "Failed to save cookie" });
    } finally { setSaving(false); }
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center gap-2 mb-2">
        <Settings size={18} style={{ color: "#2563eb" }} />
        <h2 className="text-lg font-semibold text-white tracking-tight" style={{ fontFamily: "'Manrope', sans-serif" }}>Settings</h2>
      </div>

      {/* LinkedIn Session */}
      <div className="rounded-md border p-5" style={{ background: "#18181b", borderColor: "#27272a" }}>
        <div className="flex items-center gap-2 mb-4">
          <Key size={16} style={{ color: "#2563eb" }} />
          <h3 className="text-sm font-semibold text-white" style={{ fontFamily: "'Manrope', sans-serif" }}>LinkedIn Session</h3>
          <div className="ml-auto flex items-center gap-1">
            {cookieStatus?.has_cookie ? (
              <span className="text-xs flex items-center gap-1" style={{ color: "#10b981" }}>
                <CheckCircle size={12} /> Connected: {cookieStatus.profile_name}
              </span>
            ) : (
              <span className="text-xs flex items-center gap-1" style={{ color: "#ef4444" }}>
                <XCircle size={12} /> Not connected
              </span>
            )}
          </div>
        </div>

        <p className="text-xs mb-4 leading-relaxed" style={{ color: "#a1a1aa" }}>
          Paste your LinkedIn <code className="px-1 py-0.5 rounded text-xs" style={{ background: "#27272a", color: "#2563eb" }}>li_at</code> cookie to enable search & messaging.
          Open LinkedIn &rarr; F12 &rarr; Application &rarr; Cookies &rarr; copy <code className="px-1 py-0.5 rounded text-xs" style={{ background: "#27272a", color: "#2563eb" }}>li_at</code> value.
        </p>

        <div className="space-y-3">
          <input
            data-testid="li-at-input"
            value={liAt}
            onChange={(e) => setLiAt(e.target.value)}
            placeholder="li_at cookie value"
            className="w-full px-3 py-2 rounded-md text-sm border"
            style={{ background: "#09090b", borderColor: "#27272a", color: "#fff" }}
          />
          <input
            data-testid="jsessionid-input"
            value={jsessionId}
            onChange={(e) => setJsessionId(e.target.value)}
            placeholder="JSESSIONID (optional)"
            className="w-full px-3 py-2 rounded-md text-sm border"
            style={{ background: "#09090b", borderColor: "#27272a", color: "#fff" }}
          />
          <button
            data-testid="save-cookie-btn"
            onClick={handleSaveCookie}
            disabled={saving || !liAt.trim()}
            className="px-5 py-2.5 rounded-md text-sm font-medium text-white flex items-center gap-2 disabled:opacity-40"
            style={{ background: "#2563eb" }}
          >
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Plug size={14} />}
            Connect LinkedIn
          </button>
        </div>

        {msg && (
          <div
            className="mt-3 text-xs px-3 py-2 rounded-md"
            style={{
              background: msg.type === "success" ? "#10b98120" : msg.type === "warn" ? "#f59e0b20" : "#ef444420",
              color: msg.type === "success" ? "#10b981" : msg.type === "warn" ? "#f59e0b" : "#ef4444",
            }}
          >
            {msg.text}
          </div>
        )}
      </div>

      {/* Extension */}
      <div className="rounded-md border p-5" style={{ background: "#18181b", borderColor: "#27272a" }}>
        <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2" style={{ fontFamily: "'Manrope', sans-serif" }}>
          <Plug size={16} style={{ color: "#10b981" }} /> Chrome Extension
        </h3>
        <p className="text-xs mb-3 leading-relaxed" style={{ color: "#a1a1aa" }}>
          Install the LinkedIn Lead Agent Chrome extension for auto-sync, enrichment, and message queue.
        </p>
        <a
          href={`${process.env.REACT_APP_BACKEND_URL}/api/linkedin-lead-agent-extension.zip`}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-md text-sm border transition-colors duration-150"
          style={{ borderColor: "#27272a", color: "#fff" }}
        >
          Download Extension
        </a>
      </div>
    </div>
  );
}
