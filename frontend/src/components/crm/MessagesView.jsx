import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { MessageSquare, Send, Loader2, Sparkles, Clock, User, Search } from "lucide-react";

export default function MessagesView({ API, activeAccountId, cookieStatus }) {
  const [messageLog, setMessageLog] = useState([]);
  const [connections, setConnections] = useState([]);
  const [selectedRecipient, setSelectedRecipient] = useState(null);
  const [messageText, setMessageText] = useState("");
  const [msgPurpose, setMsgPurpose] = useState("introduce services");
  const [msgCompany, setMsgCompany] = useState("fundle");
  const [generatingMsg, setGeneratingMsg] = useState(false);
  const [sendingMsg, setSendingMsg] = useState(false);
  const [connSearch, setConnSearch] = useState("");
  const [loadingConns, setLoadingConns] = useState(false);

  const fetchLog = useCallback(async () => {
    if (!activeAccountId) return;
    try {
      const res = await axios.get(`${API}/li-search/messages/log`, {
        params: { start: 0, count: 50, account_id: activeAccountId }
      });
      setMessageLog(res.data.messages || []);
    } catch {}
  }, [API, activeAccountId]);

  const fetchConnections = useCallback(async () => {
    if (!activeAccountId || !cookieStatus?.has_cookie) return;
    setLoadingConns(true);
    try {
      const res = await axios.get(`${API}/li-search/connections`, {
        params: { start: 0, count: 40, keyword: connSearch, account_id: activeAccountId }
      });
      setConnections(res.data.connections || []);
    } catch {} finally { setLoadingConns(false); }
  }, [API, activeAccountId, connSearch, cookieStatus]);

  useEffect(() => { fetchLog(); }, [fetchLog]);
  useEffect(() => { fetchConnections(); }, [fetchConnections]);

  const handleGenerate = async () => {
    if (!selectedRecipient) return;
    setGeneratingMsg(true);
    try {
      const r = await axios.post(`${API}/li-search/message/generate`, {
        recipient_name: selectedRecipient.full_name || selectedRecipient.name,
        recipient_title: selectedRecipient.occupation || "",
        purpose: msgPurpose,
        company: msgCompany,
      });
      setMessageText(r.data.message || "");
    } catch {} finally { setGeneratingMsg(false); }
  };

  const handleSend = async () => {
    if (!selectedRecipient || !messageText) return;
    setSendingMsg(true);
    try {
      await axios.post(`${API}/li-search/message/send`, {
        recipient_urn: selectedRecipient.member_urn || selectedRecipient.urn_id || selectedRecipient.entity_urn,
        recipient_name: selectedRecipient.full_name || selectedRecipient.name,
        message: messageText,
        account_id: activeAccountId,
      });
      setMessageText(""); setSelectedRecipient(null);
      fetchLog();
    } catch {} finally { setSendingMsg(false); }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 max-w-7xl">
      {/* Compose Panel */}
      <div className="lg:col-span-2 space-y-4">
        <div className="rounded-md border p-5" style={{ background: "#18181b", borderColor: "#27272a" }}>
          <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2" style={{ fontFamily: "'Manrope', sans-serif" }}>
            <Send size={16} style={{ color: "#2563eb" }} /> Compose Message
          </h3>

          {/* Recipient Search */}
          <div className="mb-4">
            <label className="text-xs uppercase tracking-[0.15em] mb-2 block" style={{ color: "#a1a1aa" }}>Recipient</label>
            {selectedRecipient ? (
              <div className="flex items-center gap-2 px-3 py-2 rounded-md border" style={{ borderColor: "#27272a", background: "#09090b" }}>
                <User size={14} style={{ color: "#2563eb" }} />
                <span className="text-sm text-white">{selectedRecipient.full_name || selectedRecipient.name}</span>
                <span className="text-xs" style={{ color: "#a1a1aa" }}>{selectedRecipient.occupation}</span>
                <button onClick={() => setSelectedRecipient(null)} className="ml-auto text-xs" style={{ color: "#ef4444" }}>Remove</button>
              </div>
            ) : (
              <div className="space-y-2">
                <div className="relative">
                  <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "#a1a1aa" }} />
                  <input
                    data-testid="recipient-search"
                    value={connSearch}
                    onChange={(e) => setConnSearch(e.target.value)}
                    placeholder="Search connections..."
                    className="w-full pl-9 pr-3 py-2 rounded-md text-sm border"
                    style={{ background: "#09090b", borderColor: "#27272a", color: "#fff" }}
                  />
                </div>
                <div className="max-h-40 overflow-y-auto rounded-md border" style={{ borderColor: "#27272a" }}>
                  {loadingConns ? (
                    <div className="py-4 text-center"><Loader2 size={16} className="animate-spin mx-auto" style={{ color: "#a1a1aa" }} /></div>
                  ) : connections.map(c => (
                    <button
                      key={c.public_id}
                      onClick={() => setSelectedRecipient(c)}
                      className="w-full text-left px-3 py-2 flex items-center gap-2 text-sm transition-colors duration-100"
                      style={{ color: "#fff" }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = "#27272a"; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                    >
                      <User size={12} style={{ color: "#a1a1aa" }} />
                      <span className="font-medium">{c.full_name || c.name}</span>
                      <span className="text-xs truncate" style={{ color: "#a1a1aa" }}>{c.occupation}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* AI Generate Options */}
          <div className="flex gap-2 mb-3">
            <select value={msgCompany} onChange={(e) => setMsgCompany(e.target.value)} className="px-3 py-1.5 rounded text-sm border" style={{ background: "#09090b", borderColor: "#27272a", color: "#fff" }}>
              <option value="fundle">Fundle.ai</option>
              <option value="tagandpay">TagandPay</option>
              <option value="exceed">Exceed</option>
            </select>
            <input value={msgPurpose} onChange={(e) => setMsgPurpose(e.target.value)} placeholder="Purpose..." className="flex-1 px-3 py-1.5 rounded text-sm border" style={{ background: "#09090b", borderColor: "#27272a", color: "#fff" }} />
            <button
              data-testid="ai-generate-msg"
              onClick={handleGenerate}
              disabled={!selectedRecipient || generatingMsg}
              className="px-3 py-1.5 rounded text-sm flex items-center gap-1 disabled:opacity-40"
              style={{ background: "#27272a", color: "#fff" }}
            >
              {generatingMsg ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />} AI Generate
            </button>
          </div>

          {/* Message Textarea */}
          <textarea
            data-testid="message-textarea"
            value={messageText}
            onChange={(e) => setMessageText(e.target.value)}
            rows={5}
            className="w-full px-3 py-2 rounded-md text-sm border mb-3"
            style={{ background: "#09090b", borderColor: "#27272a", color: "#fff" }}
            placeholder="Write your message..."
          />

          <button
            data-testid="send-message-btn"
            onClick={handleSend}
            disabled={!selectedRecipient || !messageText || sendingMsg}
            className="px-5 py-2.5 rounded-md text-sm font-medium text-white flex items-center gap-2 disabled:opacity-40"
            style={{ background: "#2563eb" }}
          >
            {sendingMsg ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
            Send Message
          </button>
        </div>
      </div>

      {/* Message Log */}
      <div className="rounded-md border" style={{ background: "#18181b", borderColor: "#27272a" }}>
        <div className="px-5 py-4 border-b flex items-center gap-2" style={{ borderColor: "#27272a" }}>
          <Clock size={16} style={{ color: "#f59e0b" }} />
          <h3 className="text-sm font-semibold text-white" style={{ fontFamily: "'Manrope', sans-serif" }}>Message History</h3>
        </div>
        <div className="divide-y max-h-[600px] overflow-y-auto" style={{ borderColor: "#27272a" }}>
          {messageLog.length === 0 ? (
            <div className="px-5 py-8 text-center" style={{ color: "#a1a1aa" }}>
              <MessageSquare size={24} className="mx-auto mb-2 opacity-30" />
              <p className="text-sm">No messages yet</p>
            </div>
          ) : messageLog.map((msg, i) => (
            <div key={i} className="px-4 py-3" style={{ borderColor: "#27272a" }}>
              <div className="flex items-center justify-between mb-1">
                <p className="text-sm font-medium text-white">{msg.recipient_name}</p>
                <span className="text-xs" style={{ color: "#a1a1aa" }}>
                  {msg.sent_at ? new Date(msg.sent_at).toLocaleString() : ""}
                </span>
              </div>
              <p className="text-xs leading-relaxed" style={{ color: "#a1a1aa" }}>
                {(msg.message || "").substring(0, 120)}{msg.message?.length > 120 ? "..." : ""}
              </p>
              {msg.status && (
                <span className="text-xs mt-1 inline-block px-1.5 py-0.5 rounded" style={{
                  background: msg.status === "sent" ? "#10b98120" : msg.status === "queued" ? "#f59e0b20" : "#ef444420",
                  color: msg.status === "sent" ? "#10b981" : msg.status === "queued" ? "#f59e0b" : "#ef4444",
                }}>
                  {msg.status}
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
