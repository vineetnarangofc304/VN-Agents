import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import {
  MessageSquareText, Send, Loader2, CheckCircle, XCircle,
  Phone, User, Clock, ChevronDown, ChevronUp, Search
} from "lucide-react";

const API_BASE = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function WhatsAppView({ API, activeAccountId }) {
  const apiUrl = API || API_BASE;
  const [configured, setConfigured] = useState(false);
  const [loading, setLoading] = useState(true);
  const [messages, setMessages] = useState([]);
  const [stats, setStats] = useState({ total: 0, sent: 0, failed: 0 });
  const [showHistory, setShowHistory] = useState(false);

  // Send form
  const [phone, setPhone] = useState("");
  const [contactName, setContactName] = useState("");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [sendResult, setSendResult] = useState(null);

  // Contact search for quick-pick
  const [contactSearch, setContactSearch] = useState("");
  const [showContactPicker, setShowContactPicker] = useState(false);

  // CRM contacts for picker
  const [crmContacts, setCrmContacts] = useState([]);

  const fetchConfig = useCallback(async () => {
    try {
      const res = await axios.get(`${apiUrl}/whatsapp/config`);
      setConfigured(res.data.configured);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  }, [apiUrl]);

  const fetchStats = useCallback(async () => {
    try {
      const res = await axios.get(`${apiUrl}/whatsapp/stats`);
      setStats(res.data);
    } catch (err) { console.error(err); }
  }, [apiUrl]);

  const fetchMessages = useCallback(async () => {
    try {
      const res = await axios.get(`${apiUrl}/whatsapp/messages?limit=30`);
      setMessages(res.data.messages || []);
    } catch (err) { console.error(err); }
  }, [apiUrl]);

  const fetchContacts = useCallback(async () => {
    if (!activeAccountId) return;
    try {
      const res = await axios.get(`${apiUrl}/li-search/connections`, {
        params: { account_id: activeAccountId, limit: 500 }
      });
      setCrmContacts(res.data.connections || []);
    } catch (err) { console.error(err); }
  }, [apiUrl, activeAccountId]);

  useEffect(() => { fetchConfig(); fetchStats(); fetchContacts(); }, [fetchConfig, fetchStats, fetchContacts]);

  const handleSend = async () => {
    if (!phone.trim() || !message.trim()) return;
    setSending(true);
    setSendResult(null);
    try {
      const res = await axios.post(`${apiUrl}/whatsapp/send`, {
        phone: phone.trim(),
        message: message.trim(),
        contact_name: contactName,
      });
      setSendResult(res.data);
      if (res.data.success) {
        setMessage("");
        fetchStats();
        if (showHistory) fetchMessages();
      }
    } catch (err) {
      setSendResult({ success: false, detail: err.response?.data?.detail || "Failed to send" });
    }
    finally { setSending(false); }
  };

  const filteredContacts = crmContacts.filter(c => {
    if (!contactSearch) return false;
    if (!c.phone) return false; // Only show contacts with phone numbers
    const q = contactSearch.toLowerCase();
    return (
      (c.full_name || "").toLowerCase().includes(q) ||
      (c.phone || "").includes(q) ||
      (c.company || "").toLowerCase().includes(q)
    );
  }).slice(0, 8);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" style={{ color: "#a1a1aa" }}>
        <Loader2 size={20} className="animate-spin mr-2" /> Loading WhatsApp...
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MessageSquareText size={20} style={{ color: "#25D366" }} />
          <h2 className="text-xl font-bold text-white tracking-tight" style={{ fontFamily: "'Manrope', sans-serif" }}>
            WhatsApp
          </h2>
        </div>
        <div className="flex items-center gap-4 text-xs" style={{ color: "#a1a1aa" }}>
          <span>{stats.sent} sent</span>
          <span>{stats.failed} failed</span>
        </div>
      </div>

      {/* Status Banner */}
      {!configured && (
        <div className="rounded-md border px-4 py-3 text-sm" style={{ background: "#f59e0b10", borderColor: "#f59e0b30", color: "#f59e0b" }}>
          WhatsApp not configured. Add your Qikchat API key in Settings to start sending messages.
        </div>
      )}

      {/* Compose Panel */}
      <div className="rounded-md border" style={{ background: "#18181b", borderColor: "#27272a" }} data-testid="whatsapp-compose">
        <div className="px-5 py-3 border-b" style={{ borderColor: "#27272a" }}>
          <span className="text-sm font-medium text-white">Send Message</span>
        </div>

        <div className="p-5 space-y-4">
          {/* Contact Picker */}
          <div className="relative">
            <div className="flex gap-3">
              <div className="flex-1 relative">
                <Phone size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "#a1a1aa" }} />
                <input
                  data-testid="whatsapp-phone-input"
                  type="text"
                  placeholder="Phone number (e.g. +919876543210)"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="w-full pl-9 pr-3 py-2.5 rounded-md border text-sm text-white placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-blue-600"
                  style={{ background: "#09090b", borderColor: "#27272a" }}
                />
              </div>
              <div className="flex-1 relative">
                <User size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "#a1a1aa" }} />
                <input
                  data-testid="whatsapp-name-input"
                  type="text"
                  placeholder="Contact name (optional)"
                  value={contactName}
                  onChange={(e) => setContactName(e.target.value)}
                  className="w-full pl-9 pr-3 py-2.5 rounded-md border text-sm text-white placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-blue-600"
                  style={{ background: "#09090b", borderColor: "#27272a" }}
                />
              </div>
            </div>

            {/* CRM Contact Quick Pick */}
            <div className="mt-2 relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "#a1a1aa" }} />
              <input
                data-testid="whatsapp-contact-search"
                type="text"
                placeholder="Search CRM contacts by name, phone, or company..."
                value={contactSearch}
                onChange={(e) => { setContactSearch(e.target.value); setShowContactPicker(true); }}
                onFocus={() => setShowContactPicker(true)}
                onBlur={() => setTimeout(() => setShowContactPicker(false), 200)}
                className="w-full pl-9 pr-3 py-2 rounded-md border text-xs text-white placeholder:text-zinc-500 focus:outline-none focus:ring-1"
                style={{ background: "#09090b", borderColor: "#27272a" }}
              />
              {showContactPicker && filteredContacts.length > 0 && (
                <div className="absolute top-full left-0 right-0 mt-1 rounded-md border z-20 max-h-48 overflow-y-auto"
                  style={{ background: "#18181b", borderColor: "#27272a" }}>
                  {filteredContacts.map((c) => (
                    <button
                      key={c.public_id || c.phone}
                      data-testid={`contact-pick-${c.public_id || c.phone}`}
                      className="w-full px-3 py-2 text-left text-xs flex items-center gap-2 hover:bg-zinc-800"
                      onMouseDown={() => {
                        setPhone(c.phone || "");
                        setContactName(c.full_name || "");
                        setContactSearch("");
                        setShowContactPicker(false);
                      }}
                    >
                      <span className="text-white font-medium">{c.full_name}</span>
                      {c.phone && <span style={{ color: "#a1a1aa" }}>{c.phone}</span>}
                      {c.company && <span style={{ color: "#71717a" }}>@ {c.company}</span>}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Message */}
          <textarea
            data-testid="whatsapp-message-input"
            placeholder="Type your message..."
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            maxLength={4096}
            rows={4}
            className="w-full px-3 py-2.5 rounded-md border text-sm text-white placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-blue-600 resize-none"
            style={{ background: "#09090b", borderColor: "#27272a" }}
          />

          {/* Send Button */}
          <div className="flex items-center justify-between">
            <span className="text-xs" style={{ color: "#a1a1aa" }}>{message.length}/4096</span>
            <button
              data-testid="whatsapp-send-btn"
              onClick={handleSend}
              disabled={sending || !phone.trim() || !message.trim()}
              className="px-5 py-2.5 rounded-md text-sm font-semibold flex items-center gap-2 disabled:opacity-40 transition-colors"
              style={{ background: "#128C7E", color: "#ffffff" }}
            >
              {sending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
              Send WhatsApp
            </button>
          </div>

          {/* Result */}
          {sendResult && (
            <div className="rounded-md px-4 py-2 text-xs flex items-center gap-2" style={{
              background: sendResult.success ? "#10b98110" : "#ef444410",
              color: sendResult.success ? "#10b981" : "#ef4444",
            }}>
              {sendResult.success ? <CheckCircle size={14} /> : <XCircle size={14} />}
              {sendResult.detail}
              {sendResult.credits_used > 0 && <span className="ml-2 opacity-60">({sendResult.credits_used} credits)</span>}
            </div>
          )}
        </div>
      </div>

      {/* Message History */}
      <div className="rounded-md border" style={{ background: "#18181b", borderColor: "#27272a" }}>
        <button
          data-testid="whatsapp-toggle-history"
          onClick={() => { setShowHistory(!showHistory); if (!showHistory) fetchMessages(); }}
          className="w-full px-5 py-3 flex items-center justify-between text-sm font-medium text-white"
        >
          <span className="flex items-center gap-2">
            <Clock size={14} style={{ color: "#a1a1aa" }} />
            Message History ({stats.total})
          </span>
          {showHistory ? <ChevronUp size={14} style={{ color: "#a1a1aa" }} /> : <ChevronDown size={14} style={{ color: "#a1a1aa" }} />}
        </button>

        {showHistory && (
          <div className="border-t overflow-x-auto" style={{ borderColor: "#27272a" }}>
            {messages.length === 0 ? (
              <div className="px-5 py-8 text-center text-sm" style={{ color: "#a1a1aa" }}>
                No messages yet
              </div>
            ) : (
              <table className="w-full">
                <thead>
                  <tr className="border-b" style={{ borderColor: "#27272a" }}>
                    <th className="px-4 py-2 text-left text-xs" style={{ color: "#a1a1aa" }}>Contact</th>
                    <th className="px-4 py-2 text-left text-xs" style={{ color: "#a1a1aa" }}>Phone</th>
                    <th className="px-4 py-2 text-left text-xs" style={{ color: "#a1a1aa" }}>Message</th>
                    <th className="px-4 py-2 text-left text-xs" style={{ color: "#a1a1aa" }}>Status</th>
                    <th className="px-4 py-2 text-left text-xs" style={{ color: "#a1a1aa" }}>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {messages.map((m) => (
                    <tr key={m.id} className="border-t" style={{ borderColor: "#27272a" }} data-testid="whatsapp-message-row">
                      <td className="px-4 py-2 text-xs text-white">{m.contact_name || "-"}</td>
                      <td className="px-4 py-2 text-xs" style={{ color: "#a1a1aa" }}>{m.phone}</td>
                      <td className="px-4 py-2 text-xs truncate max-w-[250px]" style={{ color: "#a1a1aa" }}>{m.message}</td>
                      <td className="px-4 py-2">
                        <span className="text-xs px-2 py-0.5 rounded-full" style={{
                          background: m.status === "sent" ? "#10b98120" : "#ef444420",
                          color: m.status === "sent" ? "#10b981" : "#ef4444",
                        }}>{m.status}</span>
                      </td>
                      <td className="px-4 py-2 text-xs" style={{ color: "#71717a" }}>
                        {new Date(m.sent_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
