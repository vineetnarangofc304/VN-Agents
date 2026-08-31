import { useState, useEffect, useCallback, useRef } from "react";
import { useAuth } from "./AuthContext";
import {
  LayoutDashboard, Megaphone, Users, Settings, LogOut, Upload,
  Send, Loader2, CheckCircle, XCircle, ChevronDown, ChevronUp,
  RefreshCw, Search, Shield, Download, Play, Pause, Trash2,
  Plus, FileSpreadsheet, Eye, Clock, TrendingUp, Zap,
  Chrome, ArrowRight, BarChart3, Calendar, UserPlus, MessageSquare
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

export default function CRMDashboard() {
  const { user, logout, ax } = useAuth();
  const [view, setView] = useState("dashboard");

  const navItems = [
    { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
    { id: "campaigns", label: "Campaigns", icon: Megaphone },
    { id: "prospects", label: "Prospects", icon: Users },
    { id: "extension", label: "Extension", icon: Chrome },
    { id: "settings", label: "Settings", icon: Settings },
  ];
  if (user?.role === "super_admin") {
    navItems.push({ id: "admin", label: "Admin", icon: Shield });
  }

  return (
    <div className="min-h-screen flex bg-slate-50">
      {/* Sidebar */}
      <aside className="w-60 flex-shrink-0 bg-white border-r border-slate-200 flex flex-col">
        <div className="px-5 py-5 border-b border-slate-100">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center flex-shrink-0">
              <svg width="16" height="16" viewBox="0 0 32 32" fill="none">
                <path d="M8 24V12h4v12H8zm2-14a2.5 2.5 0 110-5 2.5 2.5 0 010 5zm6 14V17.5c0-1.5.5-3 2.5-3s2.5 1.5 2.5 3V24h4v-7c0-3.5-2-5.5-4.5-5.5-2 0-3.5 1-4 2.5h-.5V12h-4v12h4z" fill="white"/>
              </svg>
            </div>
            <div>
              <h1 className="text-sm font-bold text-slate-900 leading-tight">LinkedLeads.ai</h1>
              <p className="text-[10px] text-slate-400">LinkedIn Automation CRM</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 px-3 py-3 space-y-0.5">
          {navItems.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              data-testid={`nav-${id}`}
              onClick={() => setView(id)}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all ${
                view === id
                  ? "bg-blue-50 text-blue-700 font-semibold"
                  : "text-slate-500 hover:bg-slate-50 hover:text-slate-700"
              }`}
            >
              <Icon size={16} />
              {label}
            </button>
          ))}
        </nav>

        {/* User + Logout */}
        <div className="p-3 border-t border-slate-100">
          <div className="flex items-center gap-2.5 px-3 py-2 mb-1">
            <div className="w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center text-xs font-bold flex-shrink-0">
              {(user?.name || "U")[0]}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-slate-900 truncate">{user?.name}</div>
              <div className="text-[10px] text-slate-400 truncate">{user?.email}</div>
            </div>
          </div>
          <button
            onClick={logout}
            data-testid="logout-btn"
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-slate-400 hover:text-red-600 hover:bg-red-50 transition-all"
          >
            <LogOut size={14} /> Sign Out
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        {view === "dashboard" && <DashboardView ax={ax} user={user} onNavigate={setView} />}
        {view === "campaigns" && <CampaignsView ax={ax} user={user} />}
        {view === "prospects" && <ProspectsView ax={ax} user={user} />}
        {view === "extension" && <ExtensionView />}
        {view === "settings" && <SettingsView ax={ax} user={user} />}
        {view === "admin" && user?.role === "super_admin" && <AdminView ax={ax} />}
      </main>
    </div>
  );
}


// ============ Dashboard Overview ============
function DashboardView({ ax, user, onNavigate }) {
  const [stats, setStats] = useState(null);
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      ax.get("/api/ext/stats").then(r => r.data).catch(() => null),
      ax.get("/api/ext/campaigns").then(r => r.data).catch(() => ({ campaigns: [] })),
    ]).then(([s, c]) => {
      setStats(s);
      setCampaigns(c?.campaigns || []);
      setLoading(false);
    });
  }, [ax]);

  if (loading) return <LoadingScreen />;

  const today = stats?.today || {};
  const statCards = [
    { label: "Connects Today", value: today.connects || 0, icon: UserPlus, color: "text-blue-600", bg: "bg-blue-50" },
    { label: "Messages Today", value: today.messages || 0, icon: MessageSquare, color: "text-emerald-600", bg: "bg-emerald-50" },
    { label: "Profile Visits", value: today.visits || 0, icon: Eye, color: "text-violet-600", bg: "bg-violet-50" },
    { label: "Total Completed", value: stats?.total_completed || 0, icon: TrendingUp, color: "text-amber-600", bg: "bg-amber-50" },
  ];

  return (
    <div className="p-6 max-w-6xl" data-testid="dashboard-view">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-slate-900">Welcome back, {(user?.name || "").split(" ")[0]}</h2>
        <p className="text-sm text-slate-500 mt-0.5">Here's your LinkedIn outreach overview for today</p>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {statCards.map((s, i) => (
          <div key={i} className="bg-white rounded-xl border border-slate-200 p-4" data-testid={`stat-card-${i}`}>
            <div className="flex items-center justify-between mb-3">
              <div className={`w-9 h-9 rounded-lg ${s.bg} flex items-center justify-center`}>
                <s.icon size={18} className={s.color} />
              </div>
            </div>
            <div className="text-2xl font-bold text-slate-900">{s.value}</div>
            <div className="text-xs text-slate-500 mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Quick Actions + Active Campaigns */}
      <div className="grid lg:grid-cols-3 gap-4">
        {/* Quick Actions */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h3 className="text-sm font-semibold text-slate-900 mb-4">Quick Actions</h3>
          <div className="space-y-2.5">
            <button
              onClick={() => onNavigate("campaigns")}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm bg-blue-50 text-blue-700 hover:bg-blue-100 transition font-medium"
              data-testid="quick-new-campaign"
            >
              <Plus size={16} /> New Campaign
            </button>
            <button
              onClick={() => onNavigate("extension")}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm bg-slate-50 text-slate-700 hover:bg-slate-100 transition font-medium"
              data-testid="quick-extension"
            >
              <Chrome size={16} /> Get Chrome Extension
            </button>
            <button
              onClick={() => onNavigate("prospects")}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm bg-slate-50 text-slate-700 hover:bg-slate-100 transition font-medium"
            >
              <FileSpreadsheet size={16} /> Upload Prospect Sheet
            </button>
          </div>
        </div>

        {/* Active Campaigns */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-slate-900">Active Campaigns</h3>
            <span className="text-xs text-slate-400">{campaigns.length} total</span>
          </div>
          {campaigns.length === 0 ? (
            <div className="text-center py-8 text-slate-400 text-sm">
              No campaigns yet. Create your first campaign to start outreach.
            </div>
          ) : (
            <div className="space-y-2">
              {campaigns.slice(0, 5).map((c) => (
                <div key={c.campaign_id} className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-slate-50 border border-slate-100">
                  <div className={`w-2 h-2 rounded-full flex-shrink-0 ${c.status === "active" ? "bg-emerald-500" : c.status === "paused" ? "bg-amber-500" : "bg-slate-300"}`} />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-slate-800 truncate">{c.name}</div>
                    <div className="text-[10px] text-slate-400">{c.type} &middot; {c.completed_count || 0}/{c.total_prospects} done</div>
                  </div>
                  <div className="text-xs text-slate-500">{c.status}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}


// ============ Campaigns View ============
function CampaignsView({ ax, user }) {
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [expanded, setExpanded] = useState(null);

  const fetchCampaigns = useCallback(async () => {
    try {
      const { data } = await ax.get("/api/ext/campaigns");
      setCampaigns(data.campaigns || []);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [ax]);

  useEffect(() => { fetchCampaigns(); }, [fetchCampaigns]);

  const handlePause = async (id) => {
    await ax.post(`/api/ext/campaigns/${id}/pause`);
    fetchCampaigns();
  };
  const handleResume = async (id) => {
    await ax.post(`/api/ext/campaigns/${id}/resume`);
    fetchCampaigns();
  };
  const handleDelete = async (id) => {
    if (!window.confirm("Delete this campaign and all its tasks?")) return;
    await ax.delete(`/api/ext/campaigns/${id}`);
    fetchCampaigns();
  };

  if (loading) return <LoadingScreen />;

  return (
    <div className="p-6 max-w-5xl" data-testid="campaigns-view">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Campaigns</h2>
          <p className="text-sm text-slate-500">Manage your LinkedIn outreach campaigns</p>
        </div>
        <div className="flex gap-2">
          <button onClick={fetchCampaigns} className="px-3 py-2 rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50 transition text-sm" data-testid="refresh-campaigns">
            <RefreshCw size={16} />
          </button>
          <button
            onClick={() => setShowCreate(true)}
            className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium transition flex items-center gap-2"
            data-testid="create-campaign-btn"
          >
            <Plus size={16} /> New Campaign
          </button>
        </div>
      </div>

      {showCreate && <CreateCampaignForm ax={ax} onDone={() => { setShowCreate(false); fetchCampaigns(); }} onCancel={() => setShowCreate(false)} />}

      {campaigns.length === 0 && !showCreate ? (
        <EmptyState icon={Megaphone} title="No campaigns yet" desc="Create your first campaign to start LinkedIn outreach" />
      ) : (
        <div className="space-y-3">
          {campaigns.map((c) => (
            <CampaignCard
              key={c.campaign_id}
              campaign={c}
              ax={ax}
              expanded={expanded === c.campaign_id}
              onToggle={() => setExpanded(expanded === c.campaign_id ? null : c.campaign_id)}
              onPause={() => handlePause(c.campaign_id)}
              onResume={() => handleResume(c.campaign_id)}
              onDelete={() => handleDelete(c.campaign_id)}
              onRefresh={fetchCampaigns}
            />
          ))}
        </div>
      )}
    </div>
  );
}


function CampaignCard({ campaign: c, ax, expanded, onToggle, onPause, onResume, onDelete, onRefresh }) {
  const [tasks, setTasks] = useState([]);
  const [loadingTasks, setLoadingTasks] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    if (expanded) {
      setLoadingTasks(true);
      ax.get(`/api/ext/campaigns/${c.campaign_id}/tasks`).then(r => {
        setTasks(r.data.tasks || []);
        setLoadingTasks(false);
      }).catch(() => setLoadingTasks(false));
    }
  }, [expanded, ax, c.campaign_id, refreshKey]);

  const progress = c.total_prospects > 0 ? Math.round(((c.completed_count || 0) / c.total_prospects) * 100) : 0;
  const statusColor = c.status === "active" ? "bg-emerald-500" : c.status === "paused" ? "bg-amber-500" : "bg-slate-400";

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden" data-testid={`campaign-${c.campaign_id}`}>
      <div className="p-4 flex items-center gap-4 cursor-pointer hover:bg-slate-50/50 transition" onClick={onToggle}>
        <div className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${statusColor}`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-slate-900 truncate">{c.name}</span>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 capitalize">{c.type}</span>
          </div>
          <div className="text-xs text-slate-400 mt-0.5">{c.total_prospects} prospects &middot; Created {new Date(c.created_at).toLocaleDateString()}</div>
        </div>
        {/* Progress */}
        <div className="w-32 flex-shrink-0">
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="text-slate-500">{c.completed_count || 0}/{c.total_prospects}</span>
            <span className="font-medium text-blue-600">{progress}%</span>
          </div>
          <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
            <div className="h-full bg-blue-600 rounded-full transition-all" style={{ width: `${progress}%` }} />
          </div>
        </div>
        {/* Actions */}
        <div className="flex items-center gap-1 flex-shrink-0" onClick={e => e.stopPropagation()}>
          {c.status === "active" ? (
            <button onClick={onPause} className="p-1.5 rounded-md hover:bg-amber-50 text-slate-400 hover:text-amber-600 transition" title="Pause" data-testid={`pause-campaign-${c.campaign_id}`}>
              <Pause size={14} />
            </button>
          ) : (
            <button onClick={onResume} className="p-1.5 rounded-md hover:bg-emerald-50 text-slate-400 hover:text-emerald-600 transition" title="Resume" data-testid={`resume-campaign-${c.campaign_id}`}>
              <Play size={14} />
            </button>
          )}
          <button onClick={onDelete} className="p-1.5 rounded-md hover:bg-red-50 text-slate-400 hover:text-red-600 transition" title="Delete" data-testid={`delete-campaign-${c.campaign_id}`}>
            <Trash2 size={14} />
          </button>
          {expanded ? <ChevronUp size={16} className="text-slate-400 ml-1" /> : <ChevronDown size={16} className="text-slate-400 ml-1" />}
        </div>
      </div>

      {/* Expanded: Task List + Upload */}
      {expanded && (
        <div className="border-t border-slate-100 bg-slate-50/50">
          <div className="p-4 flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Prospects / Tasks</span>
            <UploadButton ax={ax} campaignId={c.campaign_id} onDone={() => { setRefreshKey(k => k + 1); onRefresh(); }} />
          </div>
          {loadingTasks ? (
            <div className="flex justify-center py-6"><Loader2 size={20} className="animate-spin text-blue-600" /></div>
          ) : tasks.length === 0 ? (
            <div className="text-center py-6 text-sm text-slate-400">No prospects yet. Upload an XLSX file to add them.</div>
          ) : (
            <div className="max-h-80 overflow-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-100 sticky top-0">
                  <tr>
                    <th className="text-left px-4 py-2 text-xs font-semibold text-slate-500">Name</th>
                    <th className="text-left px-4 py-2 text-xs font-semibold text-slate-500">Company</th>
                    <th className="text-left px-4 py-2 text-xs font-semibold text-slate-500">Status</th>
                    <th className="text-left px-4 py-2 text-xs font-semibold text-slate-500">Profile</th>
                  </tr>
                </thead>
                <tbody>
                  {tasks.map((t) => (
                    <tr key={t.task_id} className="border-t border-slate-100 hover:bg-white transition">
                      <td className="px-4 py-2 text-slate-800">{t.prospect?.name || t.target_public_id || "—"}</td>
                      <td className="px-4 py-2 text-slate-500">{t.prospect?.company || "—"}</td>
                      <td className="px-4 py-2">
                        <StatusBadge status={t.status} />
                      </td>
                      <td className="px-4 py-2">
                        {t.target_profile_url && (
                          <a href={t.target_profile_url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline text-xs">View</a>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}


// ============ Create Campaign Form ============
function CreateCampaignForm({ ax, onDone, onCancel }) {
  const [name, setName] = useState("");
  const [type, setType] = useState("connect");
  const [message, setMessage] = useState("Hi {{first_name}}, I'd love to connect and explore synergies between our work.");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await ax.post("/api/ext/campaigns", {
        name, type, message_template: message, daily_limit: 20, prospects: [],
      });
      onDone();
    } catch (err) {
      alert(err.response?.data?.detail || "Failed to create campaign");
    }
    setLoading(false);
  };

  return (
    <div className="bg-white rounded-xl border border-blue-200 p-6 mb-4" data-testid="create-campaign-form">
      <h3 className="text-sm font-bold text-slate-900 mb-4">Create New Campaign</h3>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">Campaign Name</label>
            <input
              data-testid="campaign-name-input"
              value={name}
              onChange={e => setName(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-slate-50 focus:bg-white focus:border-blue-500 outline-none transition"
              placeholder="e.g., Q3 Outreach — Marketing Directors"
              required
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">Type</label>
            <select
              data-testid="campaign-type-select"
              value={type}
              onChange={e => setType(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-slate-50 focus:bg-white focus:border-blue-500 outline-none transition"
            >
              <option value="connect">Connection Request</option>
              <option value="message">Direct Message</option>
              <option value="visit">Profile Visit</option>
            </select>
          </div>
        </div>
        <div>
          <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">
            Message Template
            <span className="font-normal text-slate-400 ml-1">Use {"{{first_name}}"}, {"{{company}}"}, {"{{title}}"}</span>
          </label>
          <textarea
            data-testid="campaign-message-input"
            value={message}
            onChange={e => setMessage(e.target.value)}
            rows={3}
            className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-slate-50 focus:bg-white focus:border-blue-500 outline-none transition resize-none"
            placeholder="Write your outreach message..."
          />
        </div>
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onCancel} className="px-4 py-2 rounded-lg text-sm text-slate-500 hover:bg-slate-100 transition">Cancel</button>
          <button
            type="submit"
            disabled={loading || !name.trim()}
            className="px-5 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium transition disabled:opacity-50 flex items-center gap-2"
            data-testid="submit-campaign-btn"
          >
            {loading && <Loader2 size={14} className="animate-spin" />}
            Create Campaign
          </button>
        </div>
      </form>
    </div>
  );
}


// ============ Prospects View ============
function ProspectsView({ ax }) {
  const [campaigns, setCampaigns] = useState([]);
  const [selectedCampaign, setSelectedCampaign] = useState("");
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    ax.get("/api/ext/campaigns").then(r => {
      const list = r.data.campaigns || [];
      setCampaigns(list);
      setSelectedCampaign("all");
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [ax]);

  useEffect(() => {
    if (!selectedCampaign) return;
    if (selectedCampaign === "all") {
      // Fetch tasks for all campaigns
      Promise.all(
        campaigns.map(c => ax.get(`/api/ext/campaigns/${c.campaign_id}/tasks`).then(r => r.data.tasks || []).catch(() => []))
      ).then(results => setTasks(results.flat()));
    } else {
      ax.get(`/api/ext/campaigns/${selectedCampaign}/tasks`).then(r => setTasks(r.data.tasks || [])).catch(() => {});
    }
  }, [ax, selectedCampaign, campaigns]);

  const filtered = tasks.filter(t => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (t.prospect?.name || "").toLowerCase().includes(q) ||
           (t.prospect?.company || "").toLowerCase().includes(q) ||
           (t.target_public_id || "").toLowerCase().includes(q);
  });

  if (loading) return <LoadingScreen />;

  return (
    <div className="p-6 max-w-5xl" data-testid="prospects-view">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Prospects</h2>
          <p className="text-sm text-slate-500">View and manage prospects across all campaigns</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <select
          value={selectedCampaign}
          onChange={e => setSelectedCampaign(e.target.value)}
          className="px-3 py-2 rounded-lg border border-slate-200 text-sm bg-white text-slate-700"
          data-testid="campaign-filter"
        >
          <option value="all">All Campaigns</option>
          {campaigns.map(c => <option key={c.campaign_id} value={c.campaign_id}>{c.name}</option>)}
        </select>
        <div className="flex-1 relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 rounded-lg border border-slate-200 text-sm bg-white"
            placeholder="Search prospects..."
            data-testid="search-prospects"
          />
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        {filtered.length === 0 ? (
          <div className="text-center py-12 text-sm text-slate-400">No prospects found</div>
        ) : (
          <div className="overflow-auto max-h-[60vh]">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 sticky top-0">
                <tr>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500">Name</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500">Title</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500">Company</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500">Type</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500">Status</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500">Profile</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(t => (
                  <tr key={t.task_id} className="border-t border-slate-100 hover:bg-blue-50/30 transition">
                    <td className="px-4 py-2.5 font-medium text-slate-800">{t.prospect?.name || "—"}</td>
                    <td className="px-4 py-2.5 text-slate-500">{t.prospect?.title || "—"}</td>
                    <td className="px-4 py-2.5 text-slate-500">{t.prospect?.company || "—"}</td>
                    <td className="px-4 py-2.5"><span className="capitalize text-slate-600">{t.type}</span></td>
                    <td className="px-4 py-2.5"><StatusBadge status={t.status} /></td>
                    <td className="px-4 py-2.5">
                      {t.target_profile_url && (
                        <a href={t.target_profile_url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline text-xs">LinkedIn</a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}


// ============ Extension View ============
function ExtensionView() {
  const steps = [
    { num: "01", title: "Download Extension", desc: "Click the button below to download the LinkedLeads.ai Chrome Extension as a ZIP file." },
    { num: "02", title: "Install in Chrome", desc: 'Go to chrome://extensions, enable "Developer mode", click "Load unpacked" and select the extracted folder.' },
    { num: "03", title: "Login & Connect", desc: "Click the extension icon, enter your LinkedLeads.ai server URL and credentials to connect." },
    { num: "04", title: "Open LinkedIn", desc: "Navigate to linkedin.com and log in. The extension will auto-detect your session and start executing campaign tasks." },
  ];

  return (
    <div className="p-6 max-w-4xl" data-testid="extension-view">
      <div className="mb-8">
        <h2 className="text-xl font-bold text-slate-900">Chrome Extension</h2>
        <p className="text-sm text-slate-500 mt-0.5">Install the LinkedLeads.ai extension to automate LinkedIn outreach from your browser</p>
      </div>

      {/* Hero Card */}
      <div className="bg-gradient-to-r from-blue-600 to-blue-700 rounded-2xl p-8 mb-8 text-white">
        <div className="flex items-start gap-6">
          <div className="w-16 h-16 rounded-xl bg-white/20 backdrop-blur flex items-center justify-center flex-shrink-0">
            <Chrome size={32} />
          </div>
          <div className="flex-1">
            <h3 className="text-lg font-bold mb-2">LinkedLeads.ai Chrome Extension</h3>
            <p className="text-blue-100 text-sm mb-4">
              Runs outreach from your real browser — your IP, your session, your fingerprint. 
              LinkedIn sees you as a normal user, not a bot. Safe, compliant, and effective.
            </p>
            <div className="flex gap-3">
              <a
                href={`${API}/api/ext/download`}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-white text-blue-700 font-semibold text-sm hover:bg-blue-50 transition"
                data-testid="download-extension-btn"
              >
                <Download size={16} /> Download ZIP
              </a>
            </div>
          </div>
        </div>
      </div>

      {/* Steps */}
      <div className="grid md:grid-cols-2 gap-4 mb-8">
        {steps.map((s) => (
          <div key={s.num} className="bg-white rounded-xl border border-slate-200 p-5">
            <div className="text-xs font-bold text-blue-600 mb-2">STEP {s.num}</div>
            <h4 className="text-sm font-semibold text-slate-900 mb-1">{s.title}</h4>
            <p className="text-xs text-slate-500 leading-relaxed">{s.desc}</p>
          </div>
        ))}
      </div>

      {/* Features */}
      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <h3 className="text-sm font-semibold text-slate-900 mb-4">Extension Features</h3>
        <div className="grid md:grid-cols-3 gap-4">
          {[
            { icon: Zap, title: "Auto-Execute", desc: "Automatically processes pending campaign tasks when LinkedIn is open" },
            { icon: Clock, title: "Smart Timing", desc: "Human-like random delays and working-hours scheduling" },
            { icon: Shield, title: "Safe Limits", desc: "Built-in daily action limits to protect your LinkedIn account" },
            { icon: BarChart3, title: "Real-Time Stats", desc: "Track connects, messages, and visits from the extension popup" },
            { icon: UserPlus, title: "Auto-Connect", desc: "Send personalized connection requests with custom notes" },
            { icon: MessageSquare, title: "Auto-Message", desc: "Send messages to existing connections automatically" },
          ].map((f, i) => (
            <div key={i} className="flex gap-3">
              <div className="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center flex-shrink-0">
                <f.icon size={16} className="text-blue-600" />
              </div>
              <div>
                <div className="text-sm font-medium text-slate-800">{f.title}</div>
                <div className="text-xs text-slate-500">{f.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}


// ============ Settings View ============
function SettingsView({ ax, user }) {
  const [liAt, setLiAt] = useState("");
  const [jsessionid, setJsessionid] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  const handleSaveCookies = async () => {
    setSaving(true);
    setMsg("");
    try {
      await ax.post("/api/crm-auth/update-cookies", { li_at: liAt, jsessionid });
      setMsg("Cookies saved successfully!");
      setLiAt("");
      setJsessionid("");
    } catch (e) {
      setMsg(e.response?.data?.detail || "Failed to save cookies");
    }
    setSaving(false);
  };

  return (
    <div className="p-6 max-w-3xl" data-testid="settings-view">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-slate-900">Settings</h2>
        <p className="text-sm text-slate-500">Configure your LinkedLeads.ai CRM preferences</p>
      </div>

      {/* Account Info */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 mb-4">
        <h3 className="text-sm font-semibold text-slate-900 mb-4">Account</h3>
        <div className="grid gap-3 text-sm">
          <div className="flex justify-between">
            <span className="text-slate-500">Name</span>
            <span className="text-slate-900 font-medium">{user?.name}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Email</span>
            <span className="text-slate-900 font-medium">{user?.email}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Role</span>
            <span className="text-slate-900 font-medium capitalize">{user?.role?.replace("_", " ")}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">LinkedIn Cookie</span>
            <span className={`font-medium ${user?.has_cookie ? "text-emerald-600" : "text-amber-600"}`}>
              {user?.has_cookie ? "Connected" : "Not Set"}
            </span>
          </div>
        </div>
      </div>

      {/* LinkedIn Cookies (manual fallback) */}
      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <h3 className="text-sm font-semibold text-slate-900 mb-1">LinkedIn Cookies (Manual)</h3>
        <p className="text-xs text-slate-400 mb-4">Only needed if not using the Chrome Extension. The extension auto-detects your session.</p>
        {msg && (
          <div className={`text-sm px-3 py-2 rounded-lg mb-3 ${msg.includes("success") ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>{msg}</div>
        )}
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">li_at Cookie</label>
            <input
              value={liAt}
              onChange={e => setLiAt(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-slate-50 focus:bg-white focus:border-blue-500 outline-none transition font-mono"
              placeholder="Paste li_at cookie value"
              data-testid="li-at-input"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">JSESSIONID</label>
            <input
              value={jsessionid}
              onChange={e => setJsessionid(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-slate-50 focus:bg-white focus:border-blue-500 outline-none transition font-mono"
              placeholder='Paste JSESSIONID (with or without "ajax:" prefix)'
              data-testid="jsessionid-input"
            />
          </div>
          <button
            onClick={handleSaveCookies}
            disabled={saving || (!liAt && !jsessionid)}
            className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium transition disabled:opacity-50 flex items-center gap-2"
            data-testid="save-cookies-btn"
          >
            {saving && <Loader2 size={14} className="animate-spin" />} Save Cookies
          </button>
        </div>
      </div>
    </div>
  );
}


// ============ Admin View ============
function AdminView({ ax }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    ax.get("/api/crm-auth/users").then(r => {
      setUsers(r.data.users || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [ax]);

  if (loading) return <LoadingScreen />;

  return (
    <div className="p-6 max-w-4xl" data-testid="admin-view">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-slate-900">Admin Panel</h2>
        <p className="text-sm text-slate-500">Manage CRM users and permissions</p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500">Name</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500">Email</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500">Role</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500">LinkedIn</th>
            </tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id || u.email} className="border-t border-slate-100">
                <td className="px-4 py-3 font-medium text-slate-800">{u.name}</td>
                <td className="px-4 py-3 text-slate-500">{u.email}</td>
                <td className="px-4 py-3"><span className="capitalize text-slate-600">{u.role?.replace("_", " ")}</span></td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center gap-1 text-xs font-medium ${u.has_cookie ? "text-emerald-600" : "text-slate-400"}`}>
                    {u.has_cookie ? <><CheckCircle size={12} /> Connected</> : "Not Set"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}


// ============ Upload Button ============
function UploadButton({ ax, campaignId, onDone }) {
  const fileRef = useRef(null);
  const [uploading, setUploading] = useState(false);

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const { data } = await ax.post(`/api/ext/campaigns/${campaignId}/upload-prospects`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      alert(`Added ${data.prospects_added} prospects!`);
      onDone();
    } catch (err) {
      alert(err.response?.data?.detail || "Upload failed");
    }
    setUploading(false);
    if (fileRef.current) fileRef.current.value = "";
  };

  return (
    <>
      <input ref={fileRef} type="file" accept=".xlsx,.xls,.csv" className="hidden" onChange={handleUpload} />
      <button
        onClick={() => fileRef.current?.click()}
        disabled={uploading}
        className="px-3 py-1.5 rounded-lg text-xs font-medium bg-blue-50 text-blue-700 hover:bg-blue-100 transition flex items-center gap-1.5 disabled:opacity-50"
        data-testid="upload-prospects-btn"
      >
        {uploading ? <Loader2 size={12} className="animate-spin" /> : <Upload size={12} />}
        {uploading ? "Uploading..." : "Upload XLSX"}
      </button>
    </>
  );
}


// ============ Shared Components ============
function StatusBadge({ status }) {
  const styles = {
    pending: "bg-slate-100 text-slate-600",
    in_progress: "bg-blue-50 text-blue-700",
    completed: "bg-emerald-50 text-emerald-700",
    failed: "bg-red-50 text-red-700",
    paused: "bg-amber-50 text-amber-700",
  };
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${styles[status] || styles.pending}`}>
      {status === "completed" && <CheckCircle size={10} />}
      {status === "failed" && <XCircle size={10} />}
      {status === "in_progress" && <Loader2 size={10} className="animate-spin" />}
      {status}
    </span>
  );
}

function LoadingScreen() {
  return (
    <div className="flex items-center justify-center h-64">
      <Loader2 size={24} className="animate-spin text-blue-600" />
    </div>
  );
}

function EmptyState({ icon: Icon, title, desc }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
      <div className="w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center mx-auto mb-3">
        <Icon size={24} className="text-slate-400" />
      </div>
      <h3 className="text-sm font-semibold text-slate-700 mb-1">{title}</h3>
      <p className="text-xs text-slate-400">{desc}</p>
    </div>
  );
}
