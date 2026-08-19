import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import {
  Users, Search, ChevronLeft, ChevronRight, Mail, Phone, MessageSquare,
  ExternalLink, Download, ArrowUpDown, CheckSquare, Square, Send, Loader2, Sparkles
} from "lucide-react";

const PAGE_SIZE = 40;

export default function ContactsView({ API, activeAccountId }) {
  const [contacts, setContacts] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [sortBy, setSortBy] = useState("full_name");
  const [sortDir, setSortDir] = useState("asc");
  const [selected, setSelected] = useState(new Set());
  const [selectedContact, setSelectedContact] = useState(null);

  // Bulk message state
  const [showBulkMsg, setShowBulkMsg] = useState(false);
  const [bulkMsgText, setBulkMsgText] = useState("");
  const [sendingBulk, setSendingBulk] = useState(false);
  const [generatingMsg, setGeneratingMsg] = useState(false);
  const [msgPurpose, setMsgPurpose] = useState("introduce services");
  const [msgCompany, setMsgCompany] = useState("fundle");

  const fetchContacts = useCallback(async (p = page) => {
    if (!activeAccountId) return;
    setLoading(true);
    try {
      const params = { start: p * PAGE_SIZE, count: PAGE_SIZE, sort_by: sortBy, sort_dir: sortDir === "asc" ? 1 : -1, account_id: activeAccountId };
      if (search) params.keyword = search;
      const res = await axios.get(`${API}/li-search/connections`, { params });
      setContacts(res.data.connections || []);
      setTotal(res.data.total || 0);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  }, [API, activeAccountId, page, search, sortBy, sortDir]);

  useEffect(() => { fetchContacts(page); }, [fetchContacts, page]);

  const toggleSelect = (id) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelected(next);
  };
  const toggleSelectAll = () => {
    if (selected.size === contacts.length) setSelected(new Set());
    else setSelected(new Set(contacts.map(c => c.public_id)));
  };

  const handleGenerateMsg = async () => {
    setGeneratingMsg(true);
    try {
      const firstContact = contacts.find(c => selected.has(c.public_id));
      const r = await axios.post(`${API}/li-search/message/generate`, {
        recipient_name: firstContact?.full_name || "there",
        recipient_title: firstContact?.occupation || "",
        purpose: msgPurpose,
        company: msgCompany,
      });
      setBulkMsgText(r.data.message || "");
    } catch {} finally { setGeneratingMsg(false); }
  };

  const handleBulkSend = async () => {
    if (!bulkMsgText || selected.size === 0) return;
    setSendingBulk(true);
    try {
      const recipients = contacts.filter(c => selected.has(c.public_id)).map(c => ({
        urn: c.member_urn || c.urn_id || c.entity_urn, name: c.full_name
      }));
      await axios.post(`${API}/li-search/message/bulk`, {
        recipients, message: bulkMsgText, account_id: activeAccountId
      });
      setSelected(new Set()); setShowBulkMsg(false); setBulkMsgText("");
      fetchContacts();
    } catch {} finally { setSendingBulk(false); }
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="space-y-4 max-w-7xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Users size={18} style={{ color: "#2563eb" }} />
          <h2 className="text-lg font-semibold text-white tracking-tight" style={{ fontFamily: "'Manrope', sans-serif" }}>
            Contacts
          </h2>
          <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "#27272a", color: "#a1a1aa" }}>{total}</span>
        </div>
        <div className="flex items-center gap-2">
          {selected.size > 0 && (
            <button
              data-testid="bulk-message-btn"
              onClick={() => setShowBulkMsg(true)}
              className="text-xs px-3 py-1.5 rounded-md flex items-center gap-1 text-white"
              style={{ background: "#2563eb" }}
            >
              <Send size={12} /> Message {selected.size} selected
            </button>
          )}
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "#a1a1aa" }} />
            <input
              data-testid="contacts-search"
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(0); }}
              placeholder="Search contacts..."
              className="pl-9 pr-3 py-2 rounded-md text-sm border w-64"
              style={{ background: "#18181b", borderColor: "#27272a", color: "#fff" }}
            />
          </div>
        </div>
      </div>

      {/* Bulk Message Panel */}
      {showBulkMsg && (
        <div className="rounded-md border p-4 space-y-3" style={{ background: "#18181b", borderColor: "#27272a" }}>
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Bulk Message ({selected.size} recipients)</h3>
            <button onClick={() => setShowBulkMsg(false)} className="text-xs" style={{ color: "#a1a1aa" }}>Close</button>
          </div>
          <div className="flex gap-2">
            <select value={msgCompany} onChange={(e) => setMsgCompany(e.target.value)} className="px-3 py-1.5 rounded text-sm border" style={{ background: "#09090b", borderColor: "#27272a", color: "#fff" }}>
              <option value="fundle">Fundle.ai</option>
              <option value="tagandpay">TagandPay</option>
              <option value="exceed">Exceed</option>
            </select>
            <input value={msgPurpose} onChange={(e) => setMsgPurpose(e.target.value)} placeholder="Purpose..." className="flex-1 px-3 py-1.5 rounded text-sm border" style={{ background: "#09090b", borderColor: "#27272a", color: "#fff" }} />
            <button onClick={handleGenerateMsg} disabled={generatingMsg} className="px-3 py-1.5 rounded text-sm flex items-center gap-1" style={{ background: "#27272a", color: "#fff" }}>
              {generatingMsg ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />} AI Generate
            </button>
          </div>
          <textarea
            value={bulkMsgText}
            onChange={(e) => setBulkMsgText(e.target.value)}
            rows={4}
            className="w-full px-3 py-2 rounded text-sm border"
            style={{ background: "#09090b", borderColor: "#27272a", color: "#fff" }}
            placeholder="Write your message..."
          />
          <button onClick={handleBulkSend} disabled={sendingBulk || !bulkMsgText} className="px-4 py-2 rounded-md text-sm font-medium text-white flex items-center gap-2" style={{ background: "#2563eb" }}>
            {sendingBulk ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
            Send to {selected.size} contacts
          </button>
        </div>
      )}

      {/* Contacts Table */}
      <div className="rounded-md border overflow-hidden" style={{ background: "#18181b", borderColor: "#27272a" }}>
        <table className="w-full">
          <thead>
            <tr className="border-b" style={{ borderColor: "#27272a" }}>
              <th className="px-4 py-3 text-left w-10">
                <button onClick={toggleSelectAll}>
                  {selected.size === contacts.length && contacts.length > 0 ? <CheckSquare size={16} style={{ color: "#2563eb" }} /> : <Square size={16} style={{ color: "#a1a1aa" }} />}
                </button>
              </th>
              <th className="px-4 py-3 text-left text-xs uppercase tracking-[0.15em] font-medium" style={{ color: "#a1a1aa" }}>
                <button onClick={() => { setSortBy("full_name"); setSortDir(d => d === "asc" ? "desc" : "asc"); }} className="flex items-center gap-1">
                  Name <ArrowUpDown size={12} />
                </button>
              </th>
              <th className="px-4 py-3 text-left text-xs uppercase tracking-[0.15em] font-medium" style={{ color: "#a1a1aa" }}>Title</th>
              <th className="px-4 py-3 text-left text-xs uppercase tracking-[0.15em] font-medium" style={{ color: "#a1a1aa" }}>Company</th>
              <th className="px-4 py-3 text-left text-xs uppercase tracking-[0.15em] font-medium" style={{ color: "#a1a1aa" }}>Contact</th>
              <th className="px-4 py-3 text-left text-xs uppercase tracking-[0.15em] font-medium" style={{ color: "#a1a1aa" }}>
                <button onClick={() => { setSortBy("messages_sent"); setSortDir(d => d === "asc" ? "desc" : "asc"); }} className="flex items-center gap-1">
                  Msgs <ArrowUpDown size={12} />
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} className="py-8 text-center" style={{ color: "#a1a1aa" }}>
                <Loader2 size={20} className="animate-spin mx-auto" />
              </td></tr>
            ) : contacts.length === 0 ? (
              <tr><td colSpan={6} className="py-8 text-center text-sm" style={{ color: "#a1a1aa" }}>No contacts found</td></tr>
            ) : contacts.map((c) => (
              <tr
                key={c.public_id}
                className="border-t transition-colors duration-100 cursor-pointer"
                style={{ borderColor: "#27272a" }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "#27272a40"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                onClick={() => setSelectedContact(c)}
              >
                <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                  <button onClick={() => toggleSelect(c.public_id)}>
                    {selected.has(c.public_id) ? <CheckSquare size={16} style={{ color: "#2563eb" }} /> : <Square size={16} style={{ color: "#a1a1aa" }} />}
                  </button>
                </td>
                <td className="px-4 py-3">
                  <p className="text-sm font-medium text-white">{c.full_name || c.name}</p>
                </td>
                <td className="px-4 py-3">
                  <p className="text-sm truncate max-w-[200px]" style={{ color: "#a1a1aa" }}>{c.occupation || c.headline || "—"}</p>
                </td>
                <td className="px-4 py-3">
                  <p className="text-sm" style={{ color: "#2563eb" }}>{c.company || "—"}</p>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    {c.email && <Mail size={14} style={{ color: "#10b981" }} title={c.email} />}
                    {c.phone && <Phone size={14} style={{ color: "#f59e0b" }} title={c.phone} />}
                    {c.profile_url && <a href={c.profile_url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}><ExternalLink size={14} style={{ color: "#a1a1aa" }} /></a>}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className="text-sm" style={{ color: c.messages_sent > 0 ? "#f59e0b" : "#a1a1aa" }}>
                    {c.messages_sent || 0}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <span className="text-xs" style={{ color: "#a1a1aa" }}>
          Showing {page * PAGE_SIZE + 1}-{Math.min((page + 1) * PAGE_SIZE, total)} of {total}
        </span>
        <div className="flex items-center gap-2">
          <button onClick={() => setPage(Math.max(0, page - 1))} disabled={page === 0} className="p-2 rounded border disabled:opacity-30" style={{ borderColor: "#27272a", color: "#a1a1aa" }}>
            <ChevronLeft size={14} />
          </button>
          <span className="text-xs" style={{ color: "#a1a1aa" }}>Page {page + 1} of {totalPages || 1}</span>
          <button onClick={() => setPage(Math.min(totalPages - 1, page + 1))} disabled={page >= totalPages - 1} className="p-2 rounded border disabled:opacity-30" style={{ borderColor: "#27272a", color: "#a1a1aa" }}>
            <ChevronRight size={14} />
          </button>
        </div>
      </div>

      {/* Contact Detail Drawer */}
      {selectedContact && (
        <div className="fixed inset-0 z-50 flex justify-end" onClick={() => setSelectedContact(null)}>
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
          <div
            className="relative w-full max-w-md border-l overflow-y-auto"
            style={{ background: "#18181b", borderColor: "#27272a" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-6 border-b" style={{ borderColor: "#27272a" }}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-white" style={{ fontFamily: "'Manrope', sans-serif" }}>
                  {selectedContact.full_name || selectedContact.name}
                </h3>
                <button onClick={() => setSelectedContact(null)} className="text-sm" style={{ color: "#a1a1aa" }}>Close</button>
              </div>
              <p className="text-sm" style={{ color: "#a1a1aa" }}>{selectedContact.occupation || selectedContact.headline}</p>
              {selectedContact.company && <p className="text-sm mt-1" style={{ color: "#2563eb" }}>{selectedContact.company}</p>}
            </div>
            <div className="p-6 space-y-4">
              {selectedContact.email && (
                <div className="flex items-center gap-2">
                  <Mail size={14} style={{ color: "#10b981" }} />
                  <span className="text-sm text-white">{selectedContact.email}</span>
                </div>
              )}
              {selectedContact.phone && (
                <div className="flex items-center gap-2">
                  <Phone size={14} style={{ color: "#f59e0b" }} />
                  <span className="text-sm text-white">{selectedContact.phone}</span>
                </div>
              )}
              <div className="flex items-center gap-2">
                <MessageSquare size={14} style={{ color: "#a1a1aa" }} />
                <span className="text-sm text-white">{selectedContact.messages_sent || 0} messages sent</span>
              </div>
              {selectedContact.profile_url && (
                <a href={selectedContact.profile_url} target="_blank" rel="noreferrer" className="flex items-center gap-2 text-sm" style={{ color: "#2563eb" }}>
                  <ExternalLink size={14} /> View LinkedIn Profile
                </a>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
