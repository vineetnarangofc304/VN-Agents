import { useState, useEffect, useCallback } from "react";
import { useAuth } from "./AuthContext";
import {
  LayoutDashboard, Megaphone, Users, Settings, LogOut, UserPlus,
  Upload, Send, Loader2, CheckCircle, XCircle, ChevronDown, ChevronUp,
  RefreshCw, Search, MessageSquare, Shield
} from "lucide-react";

const VIEWS = { dashboard: "Dashboard", campaigns: "Campaigns", connections: "Connections", settings: "Settings", admin: "Admin" };

export default function CRMDashboard() {
  const { user, logout, ax } = useAuth();
  const [view, setView] = useState("campaigns");

  const navItems = [
    { id: "campaigns", label: "Campaigns", icon: Megaphone },
    { id: "connections", label: "Connections", icon: Users },
    { id: "settings", label: "Settings", icon: Settings },
  ];
  if (user?.role === "super_admin") {
    navItems.push({ id: "admin", label: "Admin", icon: Shield });
  }

  return (
    <div className="min-h-screen flex" style={{ background: "#09090b" }}>
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 border-r flex flex-col" style={{ background: "#0a0a0a", borderColor: "#1a1a1a" }}>
        <div className="px-4 py-5 border-b" style={{ borderColor: "#1a1a1a" }}>
          <h1 className="text-lg font-bold text-white" style={{ fontFamily: "'Manrope', sans-serif" }}>LinkedIn CRM</h1>
          <p className="text-xs mt-0.5" style={{ color: "#71717a" }}>{user?.name}</p>
        </div>
        <nav className="flex-1 px-2 py-3 space-y-1">
          {navItems.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              data-testid={`nav-${id}`}
              onClick={() => setView(id)}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors ${
                view === id ? "text-white font-medium" : "hover:text-white"
              }`}
              style={{
                background: view === id ? "#1a1a2e" : "transparent",
                color: view === id ? "#fff" : "#a1a1aa",
              }}
            >
              <Icon size={16} />
              {label}
            </button>
          ))}
        </nav>
        <div className="px-2 py-3 border-t" style={{ borderColor: "#1a1a1a" }}>
          <button onClick={logout} className="w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors hover:text-white" style={{ color: "#a1a1aa" }} data-testid="logout-btn">
            <LogOut size={16} /> Sign Out
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-auto p-6">
        {view === "campaigns" && <CampaignsView ax={ax} user={user} />}
        {view === "connections" && <ConnectionsView ax={ax} user={user} />}
        {view === "settings" && <SettingsView ax={ax} user={user} />}
        {view === "admin" && user?.role === "super_admin" && <AdminView ax={ax} />}
      </main>
    </div>
  );
}


// ============ Campaigns ============
function CampaignsView({ ax, user }) {
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

  const fetchCampaigns = useCallback(async () => {
    try {
      const { data } = await ax.get("/api/crm/campaigns");
      setCampaigns(data.campaigns || []);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [ax]);

  useEffect(() => { fetchCampaigns(); }, [fetchCampaigns]);

  if (loading) return <div className="flex items-center justify-center h-64 text-zinc-500"><Loader2 size={20} className="animate-spin mr-2" /> Loading...</div>;

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-white" style={{ fontFamily: "'Manrope', sans-serif" }}>Campaigns</h2>
        <button onClick={() => setShowCreate(true)} className="px-4 py-2 rounded-md text-sm font-medium text-white flex items-center gap-2" style={{ background: "#2563eb" }} data-testid="create-campaign-btn">
          <Megaphone size={14} /> New Campaign
        </button>
      </div>

      {showCreate && <CreateCampaign ax={ax} onDone={() => { setShowCreate(false); fetchCampaigns(); }} />}

      {campaigns.length === 0 && !showCreate && (
        <div className="text-center py-16" style={{ color: "#71717a" }}>
          <Megaphone size={40} className="mx-auto mb-3 opacity-30" />
          <p>No campaigns yet. Create one to get started.</p>
        </div>
      )}

      {campaigns.map(c => <CampaignCard key={c.campaign_id} campaign={c} ax={ax} onRefresh={fetchCampaigns} />)}
    </div>
  );
}

function CreateCampaign({ ax, onDone }) {
  const [name, setName] = useState("");
  const [directMsg, setDirectMsg] = useState("Hi {name},\n\nI noticed your role at {company} and wanted to connect.\n\nWe've built ChannelLoyalty.ai — a platform that helps brands digitize dealer/distributor loyalty programs with QR rewards, automated schemes, and WhatsApp engagement.\n\nWould love to show you a quick demo.\n\nRegards,\nVineet Narang\nChannelLoyalty.ai");
  const [inviteNote, setInviteNote] = useState("Hi {name}, noticed your role at {company}. We built ChannelLoyalty.ai for dealer loyalty automation — QR rewards, scheme digitization. Would love to connect!");
  const [dailyLimit, setDailyLimit] = useState(25);
  const [saving, setSaving] = useState(false);

  const handleCreate = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      await ax.post("/api/crm/campaigns", { name, direct_message: directMsg, invite_note: inviteNote, daily_limit: dailyLimit });
      onDone();
    } catch (e) { alert(e.response?.data?.detail || "Failed"); }
    finally { setSaving(false); }
  };

  return (
    <div className="rounded-lg border p-5 space-y-4" style={{ background: "#18181b", borderColor: "#27272a" }}>
      <h3 className="text-sm font-semibold text-white">Create Campaign</h3>
      <input placeholder="Campaign name" value={name} onChange={e => setName(e.target.value)} className="w-full px-3 py-2 rounded-md border text-sm text-white placeholder:text-zinc-500" style={{ background: "#09090b", borderColor: "#27272a" }} data-testid="campaign-name-input" />
      <div>
        <label className="text-xs font-medium mb-1 block" style={{ color: "#a1a1aa" }}>Direct Message (for 1st connections)</label>
        <textarea value={directMsg} onChange={e => setDirectMsg(e.target.value)} rows={5} className="w-full px-3 py-2 rounded-md border text-sm text-white placeholder:text-zinc-500 resize-none" style={{ background: "#09090b", borderColor: "#27272a" }} data-testid="direct-msg-input" />
      </div>
      <div>
        <label className="text-xs font-medium mb-1 block" style={{ color: "#a1a1aa" }}>Connection Request Note (max 300 chars, for non-connections)</label>
        <textarea value={inviteNote} onChange={e => setInviteNote(e.target.value)} rows={3} maxLength={300} className="w-full px-3 py-2 rounded-md border text-sm text-white placeholder:text-zinc-500 resize-none" style={{ background: "#09090b", borderColor: "#27272a" }} data-testid="invite-note-input" />
        <span className="text-xs" style={{ color: "#71717a" }}>{inviteNote.length}/300</span>
      </div>
      <div className="flex items-center gap-3">
        <label className="text-xs" style={{ color: "#a1a1aa" }}>Daily limit:</label>
        <input type="number" value={dailyLimit} onChange={e => setDailyLimit(+e.target.value)} min={1} max={50} className="w-20 px-2 py-1 rounded border text-sm text-white" style={{ background: "#09090b", borderColor: "#27272a" }} />
      </div>
      <div className="flex gap-2">
        <button onClick={handleCreate} disabled={saving || !name.trim()} className="px-4 py-2 rounded-md text-sm font-medium text-white disabled:opacity-40" style={{ background: "#2563eb" }} data-testid="save-campaign-btn">
          {saving ? <Loader2 size={14} className="animate-spin" /> : "Create Campaign"}
        </button>
        <button onClick={onDone} className="px-4 py-2 rounded-md text-sm border" style={{ borderColor: "#27272a", color: "#a1a1aa" }}>Cancel</button>
      </div>
    </div>
  );
}

function CampaignCard({ campaign: c, ax, onRefresh }) {
  const [expanded, setExpanded] = useState(false);
  const [prospects, setProspects] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [sending, setSending] = useState(false);

  const fetchProspects = async () => {
    const { data } = await ax.get(`/api/crm/campaigns/${c.campaign_id}`);
    setProspects(data.prospects || []);
  };

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    const form = new FormData();
    form.append("file", file);
    try {
      const { data } = await ax.post(`/api/crm/campaigns/${c.campaign_id}/upload`, form);
      alert(`Imported ${data.imported} prospects`);
      onRefresh();
      if (expanded) fetchProspects();
    } catch (err) { alert(err.response?.data?.detail || "Upload failed"); }
    finally { setUploading(false); }
  };

  const handleSend = async (count = 10) => {
    setSending(true);
    try {
      const { data } = await ax.post(`/api/crm/campaigns/${c.campaign_id}/send?count=${count}`);
      alert(data.detail);
      setTimeout(onRefresh, 3000);
    } catch (err) { alert(err.response?.data?.detail || "Send failed"); }
    finally { setSending(false); }
  };

  const handleRetry = async () => {
    const { data } = await ax.post(`/api/crm/campaigns/${c.campaign_id}/retry`);
    alert(`Reset ${data.reset} failed prospects`);
    onRefresh();
  };

  const pct = c.total > 0 ? Math.round((c.sent / c.total) * 100) : 0;

  return (
    <div className="rounded-lg border" style={{ background: "#18181b", borderColor: "#27272a" }}>
      <div className="px-5 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-white">{c.name}</h3>
            <p className="text-xs mt-0.5" style={{ color: "#71717a" }}>Created {new Date(c.created_at).toLocaleDateString()} | Limit: {c.daily_limit}/day</p>
          </div>
          <div className="flex items-center gap-2">
            <label className="px-3 py-1.5 rounded-md text-xs font-medium cursor-pointer flex items-center gap-1.5 border" style={{ borderColor: "#27272a", color: "#a1a1aa" }}>
              <Upload size={12} /> Upload List
              <input type="file" accept=".xlsx,.csv" onChange={handleUpload} className="hidden" data-testid={`upload-${c.campaign_id}`} />
              {uploading && <Loader2 size={12} className="animate-spin" />}
            </label>
            <button onClick={() => handleSend(10)} disabled={sending || c.pending === 0} className="px-3 py-1.5 rounded-md text-xs font-medium text-white flex items-center gap-1.5 disabled:opacity-40" style={{ background: "#2563eb" }} data-testid={`send-${c.campaign_id}`}>
              {sending ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />} Send Batch (10)
            </button>
          </div>
        </div>

        {/* Stats */}
        <div className="flex items-center gap-6 mt-3 text-xs" style={{ color: "#a1a1aa" }}>
          <span>{c.total} total</span>
          <span style={{ color: "#3b82f6" }}>{c.pending} pending</span>
          <span style={{ color: "#10b981" }}>{c.sent} sent</span>
          <span style={{ color: "#ef4444" }}>{c.failed} failed</span>
        </div>

        {/* Progress bar */}
        <div className="mt-2 h-1.5 rounded-full overflow-hidden" style={{ background: "#27272a" }}>
          <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: "#2563eb" }} />
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3 mt-3">
          <button onClick={() => { setExpanded(!expanded); if (!expanded) fetchProspects(); }} className="text-xs flex items-center gap-1" style={{ color: "#a1a1aa" }}>
            {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />} {expanded ? "Hide" : "Show"} Prospects
          </button>
          {c.failed > 0 && (
            <button onClick={handleRetry} className="text-xs flex items-center gap-1" style={{ color: "#f59e0b" }}>
              <RefreshCw size={12} /> Retry Failed ({c.failed})
            </button>
          )}
        </div>
      </div>

      {/* Prospects table */}
      {expanded && (
        <div className="border-t overflow-x-auto" style={{ borderColor: "#27272a" }}>
          <table className="w-full">
            <thead>
              <tr style={{ background: "#111" }}>
                <th className="px-3 py-2 text-left text-xs" style={{ color: "#71717a" }}>#</th>
                <th className="px-3 py-2 text-left text-xs" style={{ color: "#71717a" }}>Name</th>
                <th className="px-3 py-2 text-left text-xs" style={{ color: "#71717a" }}>Company</th>
                <th className="px-3 py-2 text-left text-xs" style={{ color: "#71717a" }}>Title</th>
                <th className="px-3 py-2 text-left text-xs" style={{ color: "#71717a" }}>Status</th>
                <th className="px-3 py-2 text-left text-xs" style={{ color: "#71717a" }}>Type</th>
              </tr>
            </thead>
            <tbody>
              {prospects.map((p, i) => (
                <tr key={p.public_id} className="border-t" style={{ borderColor: "#1a1a1a" }}>
                  <td className="px-3 py-2 text-xs" style={{ color: "#71717a" }}>{p.rank || i + 1}</td>
                  <td className="px-3 py-2 text-xs text-white">
                    <a href={p.linkedin_url} target="_blank" rel="noreferrer" className="hover:underline">{p.name || p.public_id}</a>
                  </td>
                  <td className="px-3 py-2 text-xs" style={{ color: "#a1a1aa" }}>{p.company}</td>
                  <td className="px-3 py-2 text-xs truncate max-w-[200px]" style={{ color: "#a1a1aa" }}>{p.title}</td>
                  <td className="px-3 py-2">
                    <span className="text-xs px-2 py-0.5 rounded-full" style={{
                      background: p.status === "sent" ? "#10b98120" : p.status === "failed" ? "#ef444420" : p.status === "sending" ? "#3b82f620" : "#71717a20",
                      color: p.status === "sent" ? "#10b981" : p.status === "failed" ? "#ef4444" : p.status === "sending" ? "#3b82f6" : "#71717a",
                    }}>{p.status}</span>
                  </td>
                  <td className="px-3 py-2 text-xs" style={{ color: "#71717a" }}>{p.send_type || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}


// ============ Connections ============
function ConnectionsView({ ax, user }) {
  const [connections, setConnections] = useState([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState(new Set());
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [sendResult, setSendResult] = useState(null);

  const fetchConnections = useCallback(async (start = 0) => {
    setLoading(true);
    try {
      const { data } = await ax.get(`/api/crm/connections?count=50&start=${start}`);
      setConnections(data.connections || []);
      setTotal(data.total || 0);
    } catch (e) { alert(e.response?.data?.detail || "Failed to fetch connections"); }
    finally { setLoading(false); }
  }, [ax]);

  const handleSend = async () => {
    if (selected.size === 0 || !message.trim()) return;
    setSending(true);
    setSendResult(null);
    const recipients = connections.filter(c => selected.has(c.publicIdentifier)).map(c => ({
      publicId: c.publicIdentifier, name: c.name, urn: c.urn,
    }));
    try {
      const { data } = await ax.post("/api/crm/connections/message", { recipients, message: message.trim() });
      setSendResult(data);
      setSelected(new Set());
    } catch (e) { alert(e.response?.data?.detail || "Failed"); }
    finally { setSending(false); }
  };

  const toggleSelect = (pid) => {
    const next = new Set(selected);
    next.has(pid) ? next.delete(pid) : next.add(pid);
    setSelected(next);
  };

  const toggleAll = () => {
    if (selected.size === connections.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(connections.map(c => c.publicIdentifier)));
    }
  };

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-white" style={{ fontFamily: "'Manrope', sans-serif" }}>Connections</h2>
        <button onClick={() => fetchConnections(0)} disabled={loading} className="px-4 py-2 rounded-md text-sm font-medium flex items-center gap-2 border" style={{ borderColor: "#27272a", color: "#a1a1aa" }} data-testid="pull-connections-btn">
          {loading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />} Pull from LinkedIn
        </button>
      </div>

      {connections.length > 0 && (
        <>
          {/* Message composer */}
          <div className="rounded-lg border p-4 space-y-3" style={{ background: "#18181b", borderColor: "#27272a" }}>
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium" style={{ color: "#a1a1aa" }}>{selected.size} selected</span>
            </div>
            <textarea value={message} onChange={e => setMessage(e.target.value)} rows={3} placeholder="Type your message... use {name} for personalization" className="w-full px-3 py-2 rounded-md border text-sm text-white placeholder:text-zinc-500 resize-none" style={{ background: "#09090b", borderColor: "#27272a" }} data-testid="conn-message-input" />
            <button onClick={handleSend} disabled={sending || selected.size === 0 || !message.trim()} className="px-4 py-2 rounded-md text-sm font-medium text-white flex items-center gap-2 disabled:opacity-40" style={{ background: "#2563eb" }} data-testid="conn-send-btn">
              {sending ? <Loader2 size={14} className="animate-spin" /> : <MessageSquare size={14} />} Send to {selected.size} connections
            </button>
            {sendResult && (
              <div className="text-xs" style={{ color: "#10b981" }}>Sent: {sendResult.sent} / {sendResult.total}</div>
            )}
          </div>

          {/* Connections table */}
          <div className="rounded-lg border overflow-x-auto" style={{ background: "#18181b", borderColor: "#27272a" }}>
            <table className="w-full">
              <thead>
                <tr style={{ background: "#111" }}>
                  <th className="px-3 py-2 text-left">
                    <input type="checkbox" checked={selected.size === connections.length && connections.length > 0} onChange={toggleAll} />
                  </th>
                  <th className="px-3 py-2 text-left text-xs" style={{ color: "#71717a" }}>Name</th>
                  <th className="px-3 py-2 text-left text-xs" style={{ color: "#71717a" }}>Headline</th>
                </tr>
              </thead>
              <tbody>
                {connections.map(c => (
                  <tr key={c.publicIdentifier} className="border-t cursor-pointer hover:bg-zinc-800/30" style={{ borderColor: "#1a1a1a" }} onClick={() => toggleSelect(c.publicIdentifier)}>
                    <td className="px-3 py-2">
                      <input type="checkbox" checked={selected.has(c.publicIdentifier)} onChange={() => toggleSelect(c.publicIdentifier)} />
                    </td>
                    <td className="px-3 py-2 text-xs text-white">
                      <a href={c.linkedinUrl} target="_blank" rel="noreferrer" className="hover:underline" onClick={e => e.stopPropagation()}>{c.name}</a>
                    </td>
                    <td className="px-3 py-2 text-xs truncate max-w-[300px]" style={{ color: "#a1a1aa" }}>{c.headline}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {connections.length === 0 && !loading && (
        <div className="text-center py-16" style={{ color: "#71717a" }}>
          <Users size={40} className="mx-auto mb-3 opacity-30" />
          <p>Click "Pull from LinkedIn" to load your connections</p>
        </div>
      )}
    </div>
  );
}


// ============ Settings ============
function SettingsView({ ax, user }) {
  const [liAt, setLiAt] = useState("");
  const [jsessionid, setJsessionid] = useState("");
  const [settings, setSettings] = useState(null);
  const [saving, setSaving] = useState(false);
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");

  useEffect(() => {
    ax.get("/api/crm/settings").then(({ data }) => setSettings(data));
  }, [ax]);

  const saveCookie = async () => {
    setSaving(true);
    try {
      await ax.post("/api/crm/settings/cookie", { li_at: liAt, jsessionid });
      setSettings(s => ({ ...s, has_cookie: true }));
      setLiAt(""); setJsessionid("");
      alert("LinkedIn cookies saved!");
    } catch (e) { alert(e.response?.data?.detail || "Failed"); }
    finally { setSaving(false); }
  };

  const changePassword = async () => {
    try {
      await ax.post("/api/crm-auth/change-password", { current_password: currentPw, new_password: newPw });
      setCurrentPw(""); setNewPw("");
      alert("Password changed!");
    } catch (e) { alert(e.response?.data?.detail || "Failed"); }
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <h2 className="text-xl font-bold text-white" style={{ fontFamily: "'Manrope', sans-serif" }}>Settings</h2>

      {/* LinkedIn Cookies */}
      <div className="rounded-lg border p-5 space-y-4" style={{ background: "#18181b", borderColor: "#27272a" }}>
        <h3 className="text-sm font-semibold text-white">LinkedIn Cookies</h3>
        {settings?.has_cookie && (
          <div className="text-xs px-3 py-2 rounded" style={{ background: "#10b98110", color: "#10b981" }}>
            Cookies configured: {settings.li_at_preview}
          </div>
        )}
        <p className="text-xs" style={{ color: "#71717a" }}>
          Open LinkedIn in Chrome → F12 → Application → Cookies → linkedin.com → copy <strong>li_at</strong> and <strong>JSESSIONID</strong>
        </p>
        <input placeholder="li_at cookie value" value={liAt} onChange={e => setLiAt(e.target.value)} className="w-full px-3 py-2 rounded-md border text-sm text-white placeholder:text-zinc-500" style={{ background: "#09090b", borderColor: "#27272a" }} data-testid="settings-liat" />
        <input placeholder="JSESSIONID value" value={jsessionid} onChange={e => setJsessionid(e.target.value)} className="w-full px-3 py-2 rounded-md border text-sm text-white placeholder:text-zinc-500" style={{ background: "#09090b", borderColor: "#27272a" }} data-testid="settings-jsessionid" />
        <button onClick={saveCookie} disabled={saving || !liAt || !jsessionid} className="px-4 py-2 rounded-md text-sm font-medium text-white disabled:opacity-40" style={{ background: "#2563eb" }} data-testid="save-cookie-btn">
          {saving ? "Saving..." : "Save Cookies"}
        </button>
      </div>

      {/* Change Password */}
      <div className="rounded-lg border p-5 space-y-4" style={{ background: "#18181b", borderColor: "#27272a" }}>
        <h3 className="text-sm font-semibold text-white">Change Password</h3>
        <input type="password" placeholder="Current password" value={currentPw} onChange={e => setCurrentPw(e.target.value)} className="w-full px-3 py-2 rounded-md border text-sm text-white placeholder:text-zinc-500" style={{ background: "#09090b", borderColor: "#27272a" }} data-testid="current-password-input" />
        <input type="password" placeholder="New password" value={newPw} onChange={e => setNewPw(e.target.value)} className="w-full px-3 py-2 rounded-md border text-sm text-white placeholder:text-zinc-500" style={{ background: "#09090b", borderColor: "#27272a" }} data-testid="new-password-input" />
        <button onClick={changePassword} disabled={!currentPw || !newPw} className="px-4 py-2 rounded-md text-sm font-medium text-white disabled:opacity-40" style={{ background: "#2563eb" }} data-testid="change-password-btn">
          Change Password
        </button>
      </div>
    </div>
  );
}


// ============ Admin (Super Admin Only) ============
function AdminView({ ax }) {
  const [users, setUsers] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", role: "user", li_at: "", jsessionid: "", password: "CRM@2026!" });

  const fetchUsers = useCallback(async () => {
    const { data } = await ax.get("/api/crm-auth/users");
    setUsers(data.users || []);
  }, [ax]);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const handleAdd = async () => {
    try {
      await ax.post("/api/crm-auth/users", form);
      setShowAdd(false);
      setForm({ name: "", email: "", role: "user", li_at: "", jsessionid: "", password: "CRM@2026!" });
      fetchUsers();
    } catch (e) { alert(e.response?.data?.detail || "Failed"); }
  };

  const handleUpdateCookie = async (userId, liAt, jsessionId) => {
    try {
      await ax.put(`/api/crm-auth/users/${userId}`, { li_at: liAt, jsessionid: jsessionId });
      fetchUsers();
      alert("Updated");
    } catch (e) { alert(e.response?.data?.detail || "Failed"); }
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-white" style={{ fontFamily: "'Manrope', sans-serif" }}>Admin — User Management</h2>
        <button onClick={() => setShowAdd(!showAdd)} className="px-4 py-2 rounded-md text-sm font-medium text-white flex items-center gap-2" style={{ background: "#2563eb" }} data-testid="add-user-btn">
          <UserPlus size={14} /> Add User
        </button>
      </div>

      {showAdd && (
        <div className="rounded-lg border p-5 space-y-3" style={{ background: "#18181b", borderColor: "#27272a" }}>
          <div className="grid grid-cols-2 gap-3">
            <input placeholder="Name" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} className="px-3 py-2 rounded-md border text-sm text-white placeholder:text-zinc-500" style={{ background: "#09090b", borderColor: "#27272a" }} />
            <input placeholder="Email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} className="px-3 py-2 rounded-md border text-sm text-white placeholder:text-zinc-500" style={{ background: "#09090b", borderColor: "#27272a" }} />
            <input placeholder="li_at cookie" value={form.li_at} onChange={e => setForm({ ...form, li_at: e.target.value })} className="px-3 py-2 rounded-md border text-sm text-white placeholder:text-zinc-500" style={{ background: "#09090b", borderColor: "#27272a" }} />
            <input placeholder="JSESSIONID" value={form.jsessionid} onChange={e => setForm({ ...form, jsessionid: e.target.value })} className="px-3 py-2 rounded-md border text-sm text-white placeholder:text-zinc-500" style={{ background: "#09090b", borderColor: "#27272a" }} />
            <select value={form.role} onChange={e => setForm({ ...form, role: e.target.value })} className="px-3 py-2 rounded-md border text-sm text-white" style={{ background: "#09090b", borderColor: "#27272a" }}>
              <option value="user">User</option>
              <option value="super_admin">Super Admin</option>
            </select>
            <input placeholder="Password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} className="px-3 py-2 rounded-md border text-sm text-white placeholder:text-zinc-500" style={{ background: "#09090b", borderColor: "#27272a" }} />
          </div>
          <button onClick={handleAdd} className="px-4 py-2 rounded-md text-sm font-medium text-white" style={{ background: "#2563eb" }}>Create User</button>
        </div>
      )}

      <div className="rounded-lg border overflow-x-auto" style={{ background: "#18181b", borderColor: "#27272a" }}>
        <table className="w-full">
          <thead>
            <tr style={{ background: "#111" }}>
              <th className="px-4 py-2 text-left text-xs" style={{ color: "#71717a" }}>Name</th>
              <th className="px-4 py-2 text-left text-xs" style={{ color: "#71717a" }}>Email</th>
              <th className="px-4 py-2 text-left text-xs" style={{ color: "#71717a" }}>Role</th>
              <th className="px-4 py-2 text-left text-xs" style={{ color: "#71717a" }}>Cookie</th>
            </tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id} className="border-t" style={{ borderColor: "#1a1a1a" }}>
                <td className="px-4 py-2 text-sm text-white">{u.name}</td>
                <td className="px-4 py-2 text-xs" style={{ color: "#a1a1aa" }}>{u.email}</td>
                <td className="px-4 py-2">
                  <span className="text-xs px-2 py-0.5 rounded-full" style={{
                    background: u.role === "super_admin" ? "#8b5cf620" : "#3b82f620",
                    color: u.role === "super_admin" ? "#8b5cf6" : "#3b82f6",
                  }}>{u.role}</span>
                </td>
                <td className="px-4 py-2">
                  {u.li_at ? (
                    <span className="text-xs" style={{ color: "#10b981" }}>Configured</span>
                  ) : (
                    <span className="text-xs" style={{ color: "#ef4444" }}>Not set</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
