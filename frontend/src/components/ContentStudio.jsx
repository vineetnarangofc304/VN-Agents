import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import {
  Loader2, Sparkles, Calendar, FileText, BarChart3, Settings, 
  PenLine, Image, Send, ChevronRight, Clock, CheckCircle, AlertCircle,
  Trash2, Edit3, Eye, Download, Plus, RefreshCw, Zap, BookOpen,
  LayoutGrid, List, Filter, Search, ExternalLink, Copy, Linkedin,
  ArrowRight, TrendingUp, Target, Layers, ChevronDown
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const VIEWS = {
  dashboard: { label: "Dashboard", icon: LayoutGrid },
  create: { label: "Create", icon: PenLine },
  library: { label: "Library", icon: BookOpen },
  calendar: { label: "Calendar", icon: Calendar },
  settings: { label: "Settings", icon: Settings },
};

const ContentStudio = () => {
  const [view, setView] = useState("dashboard");
  const [pillars, setPillars] = useState([]);
  const [stats, setStats] = useState({});
  const [posts, setPosts] = useState([]);
  const [calendar, setCalendar] = useState([]);
  const [oauthStatus, setOauthStatus] = useState(null);

  // Create view state
  const [selectedPillar, setSelectedPillar] = useState("");
  const [contentType, setContentType] = useState("linkedin-post");
  const [topicHint, setTopicHint] = useState("");
  const [generating, setGenerating] = useState(false);
  const [activePostId, setActivePostId] = useState(null);
  const [activePost, setActivePost] = useState(null);
  const [genStep, setGenStep] = useState("");

  // Calendar state
  const [calDays, setCalDays] = useState(30);
  const [genCal, setGenCal] = useState(false);

  // Infographic state
  const [genInfographic, setGenInfographic] = useState(null);

  const pollRef = useRef(null);

  const fetchPillars = useCallback(async () => {
    try { const r = await axios.get(`${API}/content-studio/pillars`); setPillars(r.data.pillars || []); } catch(e) {}
  }, []);
  const fetchStats = useCallback(async () => {
    try { const r = await axios.get(`${API}/content-studio/stats`); setStats(r.data); } catch(e) {}
  }, []);
  const fetchPosts = useCallback(async () => {
    try { const r = await axios.get(`${API}/content-studio/posts?limit=50`); setPosts(r.data.posts || []); } catch(e) {}
  }, []);
  const fetchCalendar = useCallback(async () => {
    try { const r = await axios.get(`${API}/content-studio/calendar`); setCalendar(r.data.calendar || []); } catch(e) {}
  }, []);
  const fetchOauth = useCallback(async () => {
    try { const r = await axios.get(`${API}/content-studio/oauth/status`); setOauthStatus(r.data); } catch(e) {}
  }, []);

  useEffect(() => { fetchPillars(); fetchStats(); fetchPosts(); fetchCalendar(); fetchOauth(); }, 
    [fetchPillars, fetchStats, fetchPosts, fetchCalendar, fetchOauth]);

  // Poll generation status
  useEffect(() => {
    if (activePostId && generating) {
      pollRef.current = setInterval(async () => {
        try {
          const r = await axios.get(`${API}/content-studio/posts/${activePostId}/status`);
          setActivePost(r.data);
          setGenStep(r.data.step || "");
          if (r.data.status !== "generating") {
            clearInterval(pollRef.current);
            setGenerating(false);
            fetchStats();
            fetchPosts();
          }
        } catch(e) {}
      }, 2000);
      return () => clearInterval(pollRef.current);
    }
  }, [activePostId, generating, fetchStats, fetchPosts]);

  const handleGenerate = async () => {
    if (!selectedPillar) return;
    setGenerating(true);
    setActivePost(null);
    setGenStep("research");
    try {
      const r = await axios.post(`${API}/content-studio/generate`, {
        pillar: selectedPillar, content_type: contentType, topic_hint: topicHint
      });
      setActivePostId(r.data.post_id);
    } catch(e) { alert(e.response?.data?.detail || "Generation failed"); setGenerating(false); }
  };

  const handleGenerateCalendar = async () => {
    setGenCal(true);
    try {
      await axios.post(`${API}/content-studio/calendar/generate`, { days: calDays });
      fetchCalendar();
    } catch(e) { alert("Calendar generation failed"); }
    finally { setGenCal(false); }
  };

  const handleGenerateInfographic = async (postId) => {
    setGenInfographic(postId);
    try {
      const r = await axios.post(`${API}/content-studio/posts/${postId}/infographic`);
      if (r.data.success) { fetchPosts(); }
      else { alert(r.data.error || "Infographic generation failed"); }
    } catch(e) { alert("Failed"); }
    finally { setGenInfographic(null); }
  };

  const handlePublish = async (postId) => {
    if (!oauthStatus?.connected) { alert("Connect LinkedIn first in Settings"); return; }
    try {
      const r = await axios.post(`${API}/content-studio/publish/${postId}`, { post_id: postId, include_image: true });
      if (r.data.success) { fetchPosts(); fetchStats(); alert("Published to LinkedIn!"); }
    } catch(e) { alert(e.response?.data?.detail || "Publish failed"); }
  };

  const handleDeletePost = async (postId) => {
    try { await axios.delete(`${API}/content-studio/posts/${postId}`); fetchPosts(); fetchStats(); } catch(e) {}
  };

  const handleConnectLinkedIn = async () => {
    try {
      const r = await axios.get(`${API}/content-studio/oauth/connect`);
      window.open(r.data.auth_url, "_blank");
    } catch(e) { alert("Failed to start OAuth"); }
  };

  const getPillarColor = (id) => pillars.find(p => p.id === id)?.color || "#0066FF";
  const getPillarName = (id) => pillars.find(p => p.id === id)?.name || id;

  return (
    <div className="cs-root" data-testid="content-studio">
      {/* Sidebar */}
      <nav className="cs-sidebar" data-testid="cs-sidebar">
        <div className="cs-sidebar-brand">
          <Zap size={20} className="cs-brand-icon" />
          <span>Content Studio</span>
        </div>
        {Object.entries(VIEWS).map(([key, v]) => (
          <button key={key} className={`cs-nav-item ${view === key ? "cs-nav-active" : ""}`}
            onClick={() => setView(key)} data-testid={`nav-${key}`}>
            <v.icon size={18} />
            <span>{v.label}</span>
          </button>
        ))}
        <div className="cs-sidebar-footer">
          {oauthStatus?.connected ? (
            <div className="cs-oauth-badge"><CheckCircle size={14} /> {oauthStatus.name}</div>
          ) : (
            <button className="cs-btn cs-btn-sm cs-btn-outline" onClick={handleConnectLinkedIn} data-testid="connect-linkedin-btn">
              <Linkedin size={14} /> Connect LinkedIn
            </button>
          )}
        </div>
      </nav>

      {/* Main Content */}
      <main className="cs-main">
        {/* ===== DASHBOARD ===== */}
        {view === "dashboard" && (
          <div className="cs-view" data-testid="dashboard-view">
            <div className="cs-view-header">
              <div>
                <h1 className="cs-h1">Content Studio</h1>
                <p className="cs-subtitle">AI-Powered Personal Brand Operating System</p>
              </div>
              <button className="cs-btn cs-btn-primary" onClick={() => setView("create")} data-testid="create-new-btn">
                <Plus size={16} /> Create Content
              </button>
            </div>

            {/* Stats Grid */}
            <div className="cs-stats-grid" data-testid="stats-grid">
              <div className="cs-stat-card">
                <div className="cs-stat-icon" style={{background: "#EEF2FF"}}><FileText size={20} color="#0066FF" /></div>
                <div className="cs-stat-info">
                  <span className="cs-stat-num">{stats.total_posts || 0}</span>
                  <span className="cs-stat-label">Total Content</span>
                </div>
              </div>
              <div className="cs-stat-card">
                <div className="cs-stat-icon" style={{background: "#F0FDF4"}}><CheckCircle size={20} color="#10B981" /></div>
                <div className="cs-stat-info">
                  <span className="cs-stat-num">{stats.published || 0}</span>
                  <span className="cs-stat-label">Published</span>
                </div>
              </div>
              <div className="cs-stat-card">
                <div className="cs-stat-icon" style={{background: "#FFF7ED"}}><Edit3 size={20} color="#F59E0B" /></div>
                <div className="cs-stat-info">
                  <span className="cs-stat-num">{stats.drafts || 0}</span>
                  <span className="cs-stat-label">Drafts</span>
                </div>
              </div>
              <div className="cs-stat-card">
                <div className="cs-stat-icon" style={{background: "#EFF6FF"}}><Calendar size={20} color="#3B82F6" /></div>
                <div className="cs-stat-info">
                  <span className="cs-stat-num">{stats.scheduled || 0}</span>
                  <span className="cs-stat-label">Scheduled</span>
                </div>
              </div>
            </div>

            {/* Content Pillars */}
            <div className="cs-section">
              <h2 className="cs-h3">Content Pillars</h2>
              <div className="cs-pillars-grid">
                {pillars.map(p => (
                  <div key={p.id} className="cs-pillar-chip" style={{borderColor: p.color + "44", color: p.color, background: p.color + "0A"}}
                    data-testid={`pillar-${p.id}`}>
                    <span className="cs-pillar-dot" style={{background: p.color}} />
                    {p.name}
                    {stats.pillar_distribution?.[p.id] && (
                      <span className="cs-pillar-count">{stats.pillar_distribution[p.id]}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Recent Content */}
            <div className="cs-section">
              <div className="cs-section-header">
                <h2 className="cs-h3">Recent Content</h2>
                <button className="cs-btn cs-btn-ghost" onClick={() => setView("library")}> View All <ChevronRight size={14} /></button>
              </div>
              {posts.length === 0 ? (
                <div className="cs-empty">
                  <PenLine size={32} strokeWidth={1.5} />
                  <p>No content yet. Start creating!</p>
                  <button className="cs-btn cs-btn-primary cs-btn-sm" onClick={() => setView("create")}><Plus size={14} /> Create First Post</button>
                </div>
              ) : (
                <div className="cs-posts-list">
                  {posts.slice(0, 5).map(post => (
                    <PostCard key={post.post_id} post={post} getPillarColor={getPillarColor} getPillarName={getPillarName}
                      onPublish={handlePublish} onDelete={handleDeletePost} onInfographic={handleGenerateInfographic}
                      genInfographic={genInfographic} />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ===== CREATE ===== */}
        {view === "create" && (
          <div className="cs-view" data-testid="create-view">
            <div className="cs-view-header">
              <div>
                <h1 className="cs-h1">Create Content</h1>
                <p className="cs-subtitle">AI-powered multi-step generation pipeline</p>
              </div>
            </div>

            <div className="cs-create-grid">
              {/* Left: Configuration */}
              <div className="cs-create-config">
                <div className="cs-card">
                  <h3 className="cs-card-title">Content Configuration</h3>
                  <div className="cs-field">
                    <label className="cs-label">Content Pillar</label>
                    <select className="cs-select" value={selectedPillar} onChange={e => setSelectedPillar(e.target.value)}
                      data-testid="select-pillar">
                      <option value="">Select a pillar...</option>
                      {pillars.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                    </select>
                  </div>
                  <div className="cs-field">
                    <label className="cs-label">Content Type</label>
                    <select className="cs-select" value={contentType} onChange={e => setContentType(e.target.value)}
                      data-testid="select-content-type">
                      <option value="linkedin-post">LinkedIn Post</option>
                      <option value="linkedin-article">LinkedIn Article</option>
                      <option value="carousel">Carousel</option>
                      <option value="case-study">Case Study</option>
                      <option value="framework">Framework</option>
                      <option value="infographic">Infographic</option>
                    </select>
                  </div>
                  <div className="cs-field">
                    <label className="cs-label">Topic Direction <span className="cs-optional">(optional)</span></label>
                    <textarea className="cs-textarea" placeholder="Give the AI a direction... e.g. 'Why most enterprise AI projects fail in the first 90 days'"
                      value={topicHint} onChange={e => setTopicHint(e.target.value)} rows={3} data-testid="topic-hint" />
                  </div>
                  <button className="cs-btn cs-btn-primary cs-btn-lg" onClick={handleGenerate}
                    disabled={generating || !selectedPillar} data-testid="generate-btn">
                    {generating ? <Loader2 size={18} className="spin" /> : <Sparkles size={18} />}
                    {generating ? "Generating..." : "Generate Content"}
                  </button>
                </div>

                {/* Generation Pipeline */}
                {(generating || activePost) && (
                  <div className="cs-card cs-pipeline" data-testid="generation-pipeline">
                    <h3 className="cs-card-title">AI Pipeline</h3>
                    <div className="cs-pipeline-steps">
                      {["research", "drafting", "reviewing", "complete"].map((step, i) => {
                        const isActive = genStep === step;
                        const isDone = ["research", "drafting", "reviewing", "complete"].indexOf(genStep) > i;
                        return (
                          <div key={step} className={`cs-step ${isActive ? "cs-step-active" : ""} ${isDone ? "cs-step-done" : ""}`}>
                            <div className="cs-step-indicator">
                              {isActive ? <Loader2 size={14} className="spin" /> : isDone ? <CheckCircle size={14} /> : <span>{i + 1}</span>}
                            </div>
                            <span className="cs-step-label">{step === "complete" ? "Complete" : step.charAt(0).toUpperCase() + step.slice(1)}</span>
                          </div>
                        );
                      })}
                    </div>
                    {activePost?.quality_score && (
                      <div className="cs-score">
                        <Target size={16} />
                        <span>Quality Score: <strong>{activePost.quality_score}/10</strong></span>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Right: Preview */}
              <div className="cs-create-preview">
                {activePost?.content ? (
                  <div className="cs-card cs-preview-card">
                    <div className="cs-preview-header">
                      <h3 className="cs-card-title">{activePost.title || "Generated Content"}</h3>
                      <div className="cs-preview-badges">
                        <span className="cs-badge" style={{background: getPillarColor(activePost.pillar) + "15", color: getPillarColor(activePost.pillar)}}>
                          {getPillarName(activePost.pillar)}
                        </span>
                        <span className="cs-badge cs-badge-type">{activePost.content_type}</span>
                      </div>
                    </div>
                    <div className="cs-preview-content" data-testid="preview-content">
                      {activePost.content}
                    </div>
                    <div className="cs-preview-actions">
                      <button className="cs-btn cs-btn-primary cs-btn-sm" onClick={() => handlePublish(activePost.post_id)}
                        disabled={!oauthStatus?.connected} data-testid="publish-btn">
                        <Send size={14} /> Publish to LinkedIn
                      </button>
                      <button className="cs-btn cs-btn-outline cs-btn-sm" onClick={() => handleGenerateInfographic(activePost.post_id)}
                        disabled={genInfographic === activePost.post_id} data-testid="gen-infographic-btn">
                        {genInfographic === activePost.post_id ? <Loader2 size={14} className="spin" /> : <Image size={14} />}
                        Generate Infographic
                      </button>
                      <button className="cs-btn cs-btn-ghost cs-btn-sm" onClick={() => navigator.clipboard.writeText(activePost.content)}>
                        <Copy size={14} /> Copy
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="cs-card cs-preview-empty">
                    <Sparkles size={40} strokeWidth={1} />
                    <h3>Your content will appear here</h3>
                    <p>Select a pillar, optionally give a direction, and hit Generate.</p>
                    <p className="cs-muted">The AI will research, draft, review, and polish your content through a multi-step pipeline.</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ===== LIBRARY ===== */}
        {view === "library" && (
          <div className="cs-view" data-testid="library-view">
            <div className="cs-view-header">
              <div>
                <h1 className="cs-h1">Content Library</h1>
                <p className="cs-subtitle">{posts.length} pieces of content</p>
              </div>
              <button className="cs-btn cs-btn-primary" onClick={() => setView("create")}>
                <Plus size={16} /> Create New
              </button>
            </div>
            {posts.length === 0 ? (
              <div className="cs-empty">
                <BookOpen size={32} strokeWidth={1.5} />
                <p>Your content library is empty</p>
              </div>
            ) : (
              <div className="cs-posts-list">
                {posts.map(post => (
                  <PostCard key={post.post_id} post={post} getPillarColor={getPillarColor} getPillarName={getPillarName}
                    onPublish={handlePublish} onDelete={handleDeletePost} onInfographic={handleGenerateInfographic}
                    genInfographic={genInfographic} expanded />
                ))}
              </div>
            )}
          </div>
        )}

        {/* ===== CALENDAR ===== */}
        {view === "calendar" && (
          <div className="cs-view" data-testid="calendar-view">
            <div className="cs-view-header">
              <div>
                <h1 className="cs-h1">Content Calendar</h1>
                <p className="cs-subtitle">{calendar.length} days planned</p>
              </div>
              <div className="cs-input-row">
                <select className="cs-select cs-select-sm" value={calDays} onChange={e => setCalDays(Number(e.target.value))}>
                  <option value={7}>7 days</option>
                  <option value={14}>14 days</option>
                  <option value={30}>30 days</option>
                  <option value={90}>90 days</option>
                </select>
                <button className="cs-btn cs-btn-primary" onClick={handleGenerateCalendar} disabled={genCal}
                  data-testid="gen-calendar-btn">
                  {genCal ? <Loader2 size={16} className="spin" /> : <Sparkles size={16} />}
                  Generate Calendar
                </button>
              </div>
            </div>
            {calendar.length === 0 ? (
              <div className="cs-empty">
                <Calendar size={32} strokeWidth={1.5} />
                <p>No calendar generated yet. Click generate to create your publishing schedule.</p>
              </div>
            ) : (
              <div className="cs-calendar-grid">
                {calendar.map((item, idx) => (
                  <div key={idx} className="cs-cal-card" data-testid={`cal-day-${item.day}`}>
                    <div className="cs-cal-date">{item.date}</div>
                    <div className="cs-cal-pillar">
                      <span className="cs-pillar-dot" style={{background: getPillarColor(item.pillar)}} />
                      {getPillarName(item.pillar)}
                    </div>
                    <div className="cs-cal-topic">{item.topic}</div>
                    <div className="cs-cal-meta">
                      <span className="cs-badge cs-badge-type">{item.content_type}</span>
                    </div>
                    {item.hook_idea && <div className="cs-cal-hook">"{item.hook_idea}"</div>}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ===== SETTINGS ===== */}
        {view === "settings" && (
          <div className="cs-view" data-testid="settings-view">
            <div className="cs-view-header">
              <h1 className="cs-h1">Settings</h1>
            </div>
            <div className="cs-card" style={{maxWidth: 600}}>
              <h3 className="cs-card-title">LinkedIn Connection</h3>
              <p className="cs-muted" style={{marginBottom: 16}}>Connect your LinkedIn account to publish content directly.</p>
              {oauthStatus?.connected ? (
                <div className="cs-oauth-connected">
                  <CheckCircle size={18} color="#10B981" />
                  <div>
                    <strong>{oauthStatus.name}</strong>
                    <span className="cs-muted">{oauthStatus.email}</span>
                  </div>
                </div>
              ) : (
                <button className="cs-btn cs-btn-primary" onClick={handleConnectLinkedIn} data-testid="connect-linkedin-settings">
                  <Linkedin size={16} /> Connect LinkedIn Account
                </button>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

// ===== Post Card Component =====
const PostCard = ({ post, getPillarColor, getPillarName, onPublish, onDelete, onInfographic, genInfographic, expanded }) => {
  const [showFull, setShowFull] = useState(expanded || false);
  const statusColors = { draft: "#F59E0B", published: "#10B981", generating: "#0066FF", error: "#EF4444" };

  return (
    <div className="cs-post-card" data-testid={`post-${post.post_id}`}>
      <div className="cs-post-top" onClick={() => setShowFull(!showFull)}>
        <div className="cs-post-meta">
          <span className="cs-badge" style={{background: getPillarColor(post.pillar) + "15", color: getPillarColor(post.pillar)}}>
            {getPillarName(post.pillar)}
          </span>
          <span className="cs-badge cs-badge-type">{post.content_type}</span>
          <span className="cs-badge" style={{background: (statusColors[post.status] || "#6B7280") + "15", color: statusColors[post.status] || "#6B7280"}}>
            {post.status}
          </span>
          {post.quality_score && (
            <span className="cs-badge" style={{background: "#EEF2FF", color: "#0066FF"}}>
              <Target size={10} /> {post.quality_score}/10
            </span>
          )}
        </div>
        <span className="cs-post-date">
          <Clock size={12} /> {post.created_at ? new Date(post.created_at).toLocaleDateString() : ""}
        </span>
      </div>
      <h4 className="cs-post-title">{post.title || "Untitled"}</h4>
      <p className="cs-post-excerpt">{(post.content || post.draft || "").substring(0, showFull ? 99999 : 200)}{!showFull && (post.content || "").length > 200 ? "..." : ""}</p>
      {showFull && (
        <div className="cs-post-actions">
          {post.status === "draft" && (
            <button className="cs-btn cs-btn-primary cs-btn-sm" onClick={() => onPublish(post.post_id)}>
              <Send size={14} /> Publish
            </button>
          )}
          <button className="cs-btn cs-btn-outline cs-btn-sm" onClick={() => onInfographic(post.post_id)}
            disabled={genInfographic === post.post_id}>
            {genInfographic === post.post_id ? <Loader2 size={14} className="spin" /> : <Image size={14} />}
            Infographic
          </button>
          {post.infographic_path && (
            <a href={`${API}/content-studio/posts/${post.post_id}/infographic`} target="_blank" rel="noreferrer"
              className="cs-btn cs-btn-outline cs-btn-sm"><Eye size={14} /> View Image</a>
          )}
          <button className="cs-btn cs-btn-ghost cs-btn-sm" onClick={() => navigator.clipboard.writeText(post.content || "")}>
            <Copy size={14} /> Copy
          </button>
          <button className="cs-btn cs-btn-ghost cs-btn-sm cs-btn-danger" onClick={() => onDelete(post.post_id)}>
            <Trash2 size={14} />
          </button>
        </div>
      )}
    </div>
  );
};

export default ContentStudio;
