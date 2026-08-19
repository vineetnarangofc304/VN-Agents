import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import {
  Building2, Plus, Sparkles, Send, Loader2, Image, Clock,
  Settings, Trash2, CheckCircle, XCircle, ChevronDown, ChevronUp, X
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const DEFAULT_PAGES = [
  { org_id: "69021406", name: "" },
  { org_id: "143338927", name: "" },
  { org_id: "142891970", name: "" },
  { org_id: "105361431", name: "" },
  { org_id: "125583973", name: "" },
];

export default function CompanyPagesView() {
  const [pages, setPages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedPage, setExpandedPage] = useState(null);
  const [showSetup, setShowSetup] = useState(false);

  // Setup form
  const [setupOrgId, setSetupOrgId] = useState("");
  const [setupName, setSetupName] = useState("");
  const [setupDesc, setSetupDesc] = useState("");
  const [setupPillars, setSetupPillars] = useState([]);
  const [newPillar, setNewPillar] = useState("");
  const [setupPostsPerDay, setSetupPostsPerDay] = useState(4);
  const [saving, setSaving] = useState(false);

  // Content generation
  const [generating, setGenerating] = useState(null);
  const [generatedContent, setGeneratedContent] = useState({});
  const [posting, setPosting] = useState(null);
  const [customTopic, setCustomTopic] = useState("");

  // Post history
  const [postHistory, setPostHistory] = useState({});

  const fetchPages = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/company-pages`);
      setPages(res.data.pages || []);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  }, []);

  const fetchHistory = useCallback(async (orgId) => {
    try {
      const res = await axios.get(`${API}/company-pages/${orgId}/posts?limit=10`);
      setPostHistory(prev => ({ ...prev, [orgId]: res.data.posts || [] }));
    } catch (err) { console.error(err); }
  }, []);

  useEffect(() => { fetchPages(); }, [fetchPages]);

  const handleSavePage = async () => {
    if (!setupName.trim()) return;
    setSaving(true);
    try {
      await axios.post(`${API}/company-pages`, {
        org_id: setupOrgId,
        name: setupName.trim(),
        description: setupDesc.trim(),
        pillars: setupPillars,
        posts_per_day: setupPostsPerDay,
        schedule_enabled: false,
      });
      fetchPages();
      setShowSetup(false);
      resetSetupForm();
    } catch (err) { console.error(err); }
    finally { setSaving(false); }
  };

  const resetSetupForm = () => {
    setSetupOrgId(""); setSetupName(""); setSetupDesc("");
    setSetupPillars([]); setNewPillar(""); setSetupPostsPerDay(4);
  };

  const handleToggleSchedule = async (orgId, enabled) => {
    try {
      await axios.put(`${API}/company-pages/${orgId}`, { schedule_enabled: enabled });
      fetchPages();
    } catch (err) { console.error(err); }
  };

  const handleGenerate = async (orgId, pillar) => {
    setGenerating(orgId);
    try {
      const res = await axios.post(`${API}/company-pages/${orgId}/generate`, {
        pillar: pillar || undefined,
        custom_topic: customTopic || undefined,
        generate_image: true,
      });
      setGeneratedContent(prev => ({ ...prev, [orgId]: res.data }));
      setCustomTopic("");
    } catch (err) {
      console.error(err);
      alert(err.response?.data?.detail || "Failed to generate content. Check AI service availability.");
    }
    finally { setGenerating(null); }
  };

  const handlePost = async (orgId) => {
    const gen = generatedContent[orgId];
    if (!gen?.content) return;
    setPosting(orgId);
    try {
      await axios.post(`${API}/company-pages/${orgId}/post`, {
        content: gen.content,
        image_path: gen.image_path || null,
      });
      setGeneratedContent(prev => { const n = { ...prev }; delete n[orgId]; return n; });
      fetchPages();
      fetchHistory(orgId);
    } catch (err) {
      console.error(err);
      alert(err.response?.data?.detail || "Failed to post. Make sure LinkedIn OAuth has w_organization_social permission.");
    }
    finally { setPosting(null); }
  };

  const handleDeletePage = async (orgId) => {
    if (!window.confirm("Remove this company page?")) return;
    try {
      await axios.delete(`${API}/company-pages/${orgId}`);
      fetchPages();
    } catch (err) { console.error(err); }
  };

  const handleUpdatePillars = async (orgId, pillars) => {
    try {
      await axios.put(`${API}/company-pages/${orgId}`, { pillars });
      fetchPages();
    } catch (err) { console.error(err); }
  };

  const startSetup = (orgId) => {
    setSetupOrgId(orgId);
    setShowSetup(true);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" style={{ color: "#a1a1aa" }}>
        <Loader2 size={20} className="animate-spin mr-2" /> Loading company pages...
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Building2 size={20} style={{ color: "#2563eb" }} />
          <h2 className="text-xl font-bold text-white tracking-tight" style={{ fontFamily: "'Manrope', sans-serif" }}>
            Company Pages
          </h2>
          <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "#27272a", color: "#a1a1aa" }}>
            {pages.length} pages
          </span>
        </div>
        <button
          data-testid="add-company-page-btn"
          onClick={() => { resetSetupForm(); setShowSetup(true); }}
          className="px-4 py-2 rounded-md text-sm font-medium text-white flex items-center gap-2"
          style={{ background: "#2563eb" }}
        >
          <Plus size={14} /> Add Page
        </button>
      </div>

      {/* OAuth Reminder */}
      <div className="rounded-md border p-4 flex items-start gap-3" style={{ background: "#18181b", borderColor: "#f59e0b40" }}>
        <Settings size={16} className="flex-shrink-0 mt-0.5" style={{ color: "#f59e0b" }} />
        <div>
          <p className="text-sm font-medium" style={{ color: "#f59e0b" }}>LinkedIn OAuth Required</p>
          <p className="text-xs mt-1 leading-relaxed" style={{ color: "#a1a1aa" }}>
            To post to company pages, your LinkedIn OAuth must include <code className="px-1 py-0.5 rounded text-xs" style={{ background: "#27272a", color: "#2563eb" }}>w_organization_social</code> permission.
            Go to <strong>LinkedIn Agent &rarr; Connect LinkedIn</strong> to re-authorize with the updated scope. You must be an admin on each company page.
          </p>
        </div>
      </div>

      {/* Setup Form */}
      {showSetup && (
        <div className="rounded-md border p-5 space-y-4" style={{ background: "#18181b", borderColor: "#27272a" }}>
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white" style={{ fontFamily: "'Manrope', sans-serif" }}>
              {setupOrgId ? `Setup Page: ${setupOrgId}` : "Add Company Page"}
            </h3>
            <button onClick={() => setShowSetup(false)} style={{ color: "#a1a1aa" }}><X size={16} /></button>
          </div>

          {!setupOrgId && (
            <>
              <p className="text-xs" style={{ color: "#a1a1aa" }}>Quick add from your pages:</p>
              <div className="flex flex-wrap gap-2">
                {DEFAULT_PAGES.filter(dp => !pages.find(p => p.org_id === dp.org_id)).map(dp => (
                  <button
                    key={dp.org_id}
                    onClick={() => startSetup(dp.org_id)}
                    className="px-3 py-1.5 rounded-md text-xs border transition-colors duration-150"
                    style={{ borderColor: "#27272a", color: "#fff" }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "#27272a"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                  >
                    Org #{dp.org_id}
                  </button>
                ))}
              </div>
              <div className="flex gap-2">
                <input value={setupOrgId} onChange={(e) => setSetupOrgId(e.target.value)} placeholder="Organization ID" className="px-3 py-2 rounded-md text-sm border flex-1" style={{ background: "#09090b", borderColor: "#27272a", color: "#fff" }} />
              </div>
            </>
          )}

          <input value={setupName} onChange={(e) => setSetupName(e.target.value)} placeholder="Company Name" className="w-full px-3 py-2 rounded-md text-sm border" style={{ background: "#09090b", borderColor: "#27272a", color: "#fff" }} />
          <textarea value={setupDesc} onChange={(e) => setSetupDesc(e.target.value)} placeholder="Company description (helps AI write better posts)" rows={2} className="w-full px-3 py-2 rounded-md text-sm border" style={{ background: "#09090b", borderColor: "#27272a", color: "#fff" }} />

          <div>
            <label className="text-xs uppercase tracking-[0.15em] mb-2 block" style={{ color: "#a1a1aa" }}>Content Pillars</label>
            <div className="flex flex-wrap gap-2 mb-2">
              {setupPillars.map((p, i) => (
                <span key={i} className="text-xs px-3 py-1.5 rounded-full flex items-center gap-1 border" style={{ borderColor: "#27272a", color: "#fff", background: "#27272a" }}>
                  {p}
                  <button onClick={() => setSetupPillars(setupPillars.filter((_, j) => j !== i))}><X size={10} /></button>
                </span>
              ))}
            </div>
            <div className="flex gap-2">
              <input value={newPillar} onChange={(e) => setNewPillar(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && newPillar.trim()) { setSetupPillars([...setupPillars, newPillar.trim()]); setNewPillar(""); } }} placeholder="Add a content pillar..." className="flex-1 px-3 py-1.5 rounded text-sm border" style={{ background: "#09090b", borderColor: "#27272a", color: "#fff" }} />
              <button onClick={() => { if (newPillar.trim()) { setSetupPillars([...setupPillars, newPillar.trim()]); setNewPillar(""); } }} className="px-3 py-1.5 rounded border text-sm" style={{ borderColor: "#27272a", color: "#a1a1aa" }}><Plus size={14} /></button>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <label className="text-xs" style={{ color: "#a1a1aa" }}>Posts per day:</label>
            <select value={setupPostsPerDay} onChange={(e) => setSetupPostsPerDay(Number(e.target.value))} className="px-3 py-1.5 rounded text-sm border" style={{ background: "#09090b", borderColor: "#27272a", color: "#fff" }}>
              {[1, 2, 3, 4, 5, 6].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>

          <button
            data-testid="save-company-page-btn"
            onClick={handleSavePage}
            disabled={saving || !setupName.trim() || !setupOrgId}
            className="px-5 py-2.5 rounded-md text-sm font-medium text-white flex items-center gap-2 disabled:opacity-40"
            style={{ background: "#2563eb" }}
          >
            {saving ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle size={14} />}
            Save Company Page
          </button>
        </div>
      )}

      {/* Company Pages Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {pages.map((page) => (
          <div
            key={page.org_id}
            data-testid={`company-page-${page.org_id}`}
            className="rounded-md border overflow-hidden"
            style={{ background: "#18181b", borderColor: "#27272a" }}
          >
            {/* Page Header */}
            <div className="px-5 py-4 border-b flex items-center justify-between" style={{ borderColor: "#27272a" }}>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-md flex items-center justify-center text-white font-bold text-sm" style={{ background: "#2563eb" }}>
                  {(page.name || "?")[0]}
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-white">{page.name}</h3>
                  <p className="text-xs" style={{ color: "#a1a1aa" }}>Org #{page.org_id}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  data-testid={`toggle-schedule-${page.org_id}`}
                  onClick={() => handleToggleSchedule(page.org_id, !page.schedule_enabled)}
                  className="text-xs px-3 py-1 rounded-full border font-medium transition-colors duration-150"
                  style={{
                    borderColor: page.schedule_enabled ? "#10b981" : "#27272a",
                    color: page.schedule_enabled ? "#10b981" : "#a1a1aa",
                    background: page.schedule_enabled ? "#10b98110" : "transparent",
                  }}
                >
                  {page.schedule_enabled ? "Auto ON" : "Auto OFF"}
                </button>
                <button onClick={() => handleDeletePage(page.org_id)} className="p-1.5 rounded" style={{ color: "#a1a1aa" }}><Trash2 size={14} /></button>
              </div>
            </div>

            {/* Stats */}
            <div className="px-5 py-3 flex items-center gap-4 border-b" style={{ borderColor: "#27272a" }}>
              <span className="text-xs" style={{ color: "#a1a1aa" }}>
                <strong className="text-white">{page.total_posts || 0}</strong> total posts
              </span>
              <span className="text-xs" style={{ color: "#a1a1aa" }}>
                <strong className="text-white">{page.posts_today || 0}</strong>/{page.posts_per_day || 4} today
              </span>
              <span className="text-xs" style={{ color: "#a1a1aa" }}>
                {page.pillars?.length || 0} pillars
              </span>
            </div>

            {/* Pillars */}
            <div className="px-5 py-3 border-b" style={{ borderColor: "#27272a" }}>
              <div className="flex flex-wrap gap-1.5">
                {(page.pillars || []).map((p, i) => (
                  <span key={i} className="text-xs px-2 py-0.5 rounded-full" style={{ background: "#2563eb20", color: "#3b82f6" }}>{p}</span>
                ))}
                {(!page.pillars || page.pillars.length === 0) && (
                  <span className="text-xs" style={{ color: "#a1a1aa" }}>No pillars set. Click expand to add.</span>
                )}
              </div>
            </div>

            {/* Actions */}
            <div className="px-5 py-3 flex items-center gap-2">
              <button
                data-testid={`generate-${page.org_id}`}
                onClick={() => handleGenerate(page.org_id, page.pillars?.[0])}
                disabled={generating === page.org_id}
                className="text-xs px-3 py-1.5 rounded-md flex items-center gap-1 text-white transition-colors duration-150"
                style={{ background: "#2563eb" }}
              >
                {generating === page.org_id ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
                Generate Post
              </button>
              <button
                onClick={() => {
                  setExpandedPage(expandedPage === page.org_id ? null : page.org_id);
                  if (expandedPage !== page.org_id) fetchHistory(page.org_id);
                }}
                className="text-xs px-3 py-1.5 rounded-md flex items-center gap-1 border"
                style={{ borderColor: "#27272a", color: "#a1a1aa" }}
              >
                {expandedPage === page.org_id ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                {expandedPage === page.org_id ? "Collapse" : "Expand"}
              </button>
            </div>

            {/* Generated Content Preview */}
            {generatedContent[page.org_id] && (
              <div className="px-5 py-3 border-t" style={{ borderColor: "#27272a", background: "#09090b" }}>
                <div className="flex items-center gap-2 mb-2">
                  <Sparkles size={12} style={{ color: "#f59e0b" }} />
                  <span className="text-xs font-medium" style={{ color: "#f59e0b" }}>Generated Content</span>
                </div>
                <p className="text-xs text-white leading-relaxed mb-3 whitespace-pre-wrap">
                  {generatedContent[page.org_id].content?.substring(0, 300)}...
                </p>
                {generatedContent[page.org_id].image_path && (
                  <div className="flex items-center gap-1 text-xs mb-3" style={{ color: "#10b981" }}>
                    <Image size={12} /> Infographic generated
                  </div>
                )}
                <div className="flex gap-2">
                  <button
                    data-testid={`post-${page.org_id}`}
                    onClick={() => handlePost(page.org_id)}
                    disabled={posting === page.org_id}
                    className="text-xs px-3 py-1.5 rounded-md flex items-center gap-1 text-white"
                    style={{ background: "#10b981" }}
                  >
                    {posting === page.org_id ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
                    Post Now
                  </button>
                  <button
                    onClick={() => setGeneratedContent(prev => { const n = { ...prev }; delete n[page.org_id]; return n; })}
                    className="text-xs px-3 py-1.5 rounded-md border"
                    style={{ borderColor: "#27272a", color: "#a1a1aa" }}
                  >
                    Discard
                  </button>
                </div>
              </div>
            )}

            {/* Expanded: History + Pillar Editor */}
            {expandedPage === page.org_id && (
              <div className="border-t" style={{ borderColor: "#27272a" }}>
                {/* Post History */}
                <div className="px-5 py-3">
                  <h4 className="text-xs font-semibold uppercase tracking-[0.15em] mb-2" style={{ color: "#a1a1aa" }}>Recent Posts</h4>
                  <div className="space-y-2 max-h-48 overflow-y-auto">
                    {(postHistory[page.org_id] || []).length === 0 ? (
                      <p className="text-xs" style={{ color: "#a1a1aa" }}>No posts yet</p>
                    ) : (postHistory[page.org_id] || []).map((post, i) => (
                      <div key={i} className="flex items-center justify-between py-1.5">
                        <div className="flex-1 min-w-0">
                          <p className="text-xs text-white truncate">{post.content?.substring(0, 80)}...</p>
                        </div>
                        <div className="flex items-center gap-2 ml-2">
                          <span className="text-xs px-1.5 py-0.5 rounded" style={{
                            background: post.status === "published" ? "#10b98120" : "#ef444420",
                            color: post.status === "published" ? "#10b981" : "#ef4444",
                          }}>{post.status}</span>
                          <span className="text-xs" style={{ color: "#a1a1aa" }}>{post.posted_at ? new Date(post.posted_at).toLocaleDateString() : ""}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Empty State */}
      {pages.length === 0 && !showSetup && (
        <div className="text-center py-12 rounded-md border" style={{ background: "#18181b", borderColor: "#27272a" }}>
          <Building2 size={32} className="mx-auto mb-3 opacity-30" style={{ color: "#a1a1aa" }} />
          <p className="text-sm mb-4" style={{ color: "#a1a1aa" }}>No company pages configured yet</p>
          <button
            onClick={() => setShowSetup(true)}
            className="px-4 py-2 rounded-md text-sm font-medium text-white"
            style={{ background: "#2563eb" }}
          >
            Add Your First Page
          </button>
        </div>
      )}
    </div>
  );
}
