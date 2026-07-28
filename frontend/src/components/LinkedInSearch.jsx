import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import {
  Loader2, Search, Send, RefreshCw, Trash2, Filter,
  ExternalLink, MessageSquare, Sparkles, Key, CheckCircle,
  XCircle, Clock, ChevronDown, ChevronUp, Copy, Building2, Tag,
  Users, Mail, UserCheck, ChevronLeft, ChevronRight, Download
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const CATEGORY_LABELS = {
  performance_marketing: { label: "Performance Marketing", color: "#ef4444" },
  digital_marketing: { label: "Digital Marketing", color: "#f59e0b" },
  loyalty_rewards: { label: "Loyalty & Rewards", color: "#8b5cf6" },
  social_media: { label: "Social Media", color: "#ec4899" },
  branding: { label: "Branding", color: "#06b6d4" },
  d2c_ecommerce: { label: "D2C / E-commerce", color: "#14b8a6" },
  tech_development: { label: "Tech/Dev", color: "#6366f1" },
  b2b_sales: { label: "B2B Sales", color: "#22c55e" },
  general_agency: { label: "General Agency", color: "#64748b" },
  not_relevant: { label: "Not Relevant", color: "#475569" },
  uncategorized: { label: "Uncategorized", color: "#6b7280" },
};

const COMPANY_LABELS = {
  fundle: { label: "Fundle.ai", color: "#8b5cf6" },
  tagandpay: { label: "TagandPay", color: "#ef4444" },
  exceed: { label: "Exceed", color: "#22c55e" },
  any: { label: "Any", color: "#f59e0b" },
  none: { label: "None", color: "#475569" },
  unknown: { label: "Unknown", color: "#6b7280" },
};

const RELEVANCE_COLORS = { high: "#22c55e", medium: "#f59e0b", low: "#ef4444" };

const LinkedInSearch = () => {
  const [activeTab, setActiveTab] = useState("search");

  // Cookie state
  const [cookieStatus, setCookieStatus] = useState(null);
  const [liAt, setLiAt] = useState("");
  const [jsessionId, setJsessionId] = useState("");
  const [savingCookie, setSavingCookie] = useState(false);
  const [cookieMsg, setCookieMsg] = useState(null);

  // Search state
  const [keywords, setKeywords] = useState([]);
  const [newKeyword, setNewKeyword] = useState("");
  const [savingKeywords, setSavingKeywords] = useState(false);
  const [searchStatus, setSearchStatus] = useState(null);
  const [searching, setSearching] = useState(false);
  const [posts, setPosts] = useState([]);
  const [stats, setStats] = useState({});
  const [filters, setFilters] = useState({ category: "all", company_match: "all", relevance: "all" });
  const [showFilters, setShowFilters] = useState(false);
  const [expandedPost, setExpandedPost] = useState(null);
  const [generatingComment, setGeneratingComment] = useState(null);
  const [generatedComments, setGeneratedComments] = useState({});
  const [postingComment, setPostingComment] = useState(null);

  // Messaging state
  const [connections, setConnections] = useState([]);
  const [connectionsTotal, setConnectionsTotal] = useState(0);
  const [connPage, setConnPage] = useState(0);
  const [connSearch, setConnSearch] = useState("");
  const [loadingConns, setLoadingConns] = useState(false);
  const [selectedConns, setSelectedConns] = useState([]);
  const [messageText, setMessageText] = useState("");
  const [msgPurpose, setMsgPurpose] = useState("introduce services");
  const [syncScript, setSyncScript] = useState(null);
  const [showSyncScript, setShowSyncScript] = useState(false);
  const [pasteData, setPasteData] = useState("");
  const [importing, setImporting] = useState(false);
  const [msgCompany, setMsgCompany] = useState("fundle");
  const [generatingMsg, setGeneratingMsg] = useState(false);
  const [sendingMsg, setSendingMsg] = useState(false);
  const [sendResult, setSendResult] = useState(null);
  const [messageLog, setMessageLog] = useState([]);

  const pollRef = useRef(null);

  // Fetch functions
  const fetchCookieStatus = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/li-search/cookie`);
      setCookieStatus(res.data);
    } catch (err) { console.error(err); }
  }, []);

  const fetchKeywords = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/li-search/keywords`);
      setKeywords(res.data.keywords || []);
    } catch (err) { console.error(err); }
  }, []);

  const fetchPosts = useCallback(async () => {
    try {
      const params = {};
      if (filters.category !== "all") params.category = filters.category;
      if (filters.company_match !== "all") params.company_match = filters.company_match;
      if (filters.relevance !== "all") params.relevance = filters.relevance;
      const res = await axios.get(`${API}/li-search/posts`, { params });
      setPosts(res.data.posts || []);
      setStats(res.data.stats || {});
    } catch (err) { console.error(err); }
  }, [filters]);

  const fetchSearchStatus = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/li-search/search/status`);
      setSearchStatus(res.data);
      return res.data;
    } catch (err) { return null; }
  }, []);

  const fetchConnections = useCallback(async (page = 0, keyword = "") => {
    setLoadingConns(true);
    try {
      const res = await axios.get(`${API}/li-search/connections`, {
        params: { start: page * 40, count: 40, keyword }
      });
      setConnections(res.data.connections || []);
      setConnectionsTotal(res.data.total || 0);
    } catch (err) {
      console.error(err);
      if (err.response?.status === 400) {
        setConnections([]);
      }
    } finally { setLoadingConns(false); }
  }, []);

  const fetchMessageLog = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/li-search/messages/log`);
      setMessageLog(res.data.messages || []);
    } catch (err) { console.error(err); }
  }, []);

  useEffect(() => {
    fetchCookieStatus();
    fetchKeywords();
    fetchPosts();
    fetchSearchStatus();
  }, [fetchCookieStatus, fetchKeywords, fetchPosts, fetchSearchStatus]);

  useEffect(() => { fetchPosts(); }, [filters, fetchPosts]);

  useEffect(() => {
    if (activeTab === "messaging" && cookieStatus?.has_cookie) {
      fetchConnections(0, "");
      fetchMessageLog();
    }
  }, [activeTab, cookieStatus, fetchConnections, fetchMessageLog]);

  // Poll search status
  useEffect(() => {
    if (searchStatus?.running) {
      pollRef.current = setInterval(async () => {
        const st = await fetchSearchStatus();
        if (!st?.running) {
          clearInterval(pollRef.current);
          fetchPosts();
        }
      }, 3000);
      return () => clearInterval(pollRef.current);
    }
  }, [searchStatus?.running, fetchSearchStatus, fetchPosts]);

  // Cookie handlers
  const handleSaveCookie = async () => {
    if (!liAt.trim()) return;
    setSavingCookie(true);
    setCookieMsg(null);
    try {
      const res = await axios.post(`${API}/li-search/cookie`, {
        li_at: liAt.trim(), jsessionid: jsessionId.trim() || null
      });
      if (res.data.warning) {
        setCookieMsg({ type: "success", text: `Cookie saved. ${res.data.warning}` });
      } else {
        setCookieMsg({ type: "success", text: `Connected as ${res.data.profile}` });
      }
      fetchCookieStatus();
      setLiAt("");
      setJsessionId("");
    } catch (err) {
      setCookieMsg({ type: "error", text: err.response?.data?.detail || "Failed to save cookie" });
    } finally { setSavingCookie(false); }
  };

  // Search handlers
  const handleAddKeyword = () => {
    if (!newKeyword.trim() || keywords.includes(newKeyword.trim())) return;
    setKeywords([...keywords, newKeyword.trim()]);
    setNewKeyword("");
  };
  const handleRemoveKeyword = (kw) => setKeywords(keywords.filter(k => k !== kw));
  const handleSaveKeywords = async () => {
    setSavingKeywords(true);
    try { await axios.post(`${API}/li-search/keywords`, { keywords }); }
    catch (err) { console.error(err); }
    finally { setSavingKeywords(false); }
  };
  const handleSearch = async () => {
    setSearching(true);
    try {
      await axios.post(`${API}/li-search/search`);
      fetchSearchStatus();
    } catch (err) { alert(err.response?.data?.detail || "Search failed"); }
    finally { setSearching(false); }
  };
  const handleGenerateComment = async (post, company) => {
    setGeneratingComment(post._id);
    try {
      const res = await axios.post(`${API}/li-search/posts/${post._id}/generate-comment`, { company });
      setGeneratedComments(prev => ({ ...prev, [post._id]: res.data.comment }));
    } catch (err) { alert("Failed to generate comment"); }
    finally { setGeneratingComment(null); }
  };
  const handlePostComment = async (post) => {
    const comment = generatedComments[post._id];
    if (!comment) return;
    setPostingComment(post._id);
    try {
      const res = await axios.post(`${API}/li-search/posts/${post._id}/comment`, {
        post_urn: post.post_urn, comment_text: comment
      });
      if (res.data.success) {
        fetchPosts();
        setGeneratedComments(prev => { const n = { ...prev }; delete n[post._id]; return n; });
      } else { alert(res.data.error || "Comment failed"); }
    } catch (err) { alert(err.response?.data?.detail || "Failed"); }
    finally { setPostingComment(null); }
  };
  const handleDeletePost = async (id) => {
    try { await axios.delete(`${API}/li-search/posts/${id}`); fetchPosts(); }
    catch (err) { console.error(err); }
  };

  // Messaging handlers
  const toggleConnSelection = (conn) => {
    const id = conn.public_id;
    if (selectedConns.find(c => c.public_id === id)) {
      setSelectedConns(selectedConns.filter(c => c.public_id !== id));
    } else {
      setSelectedConns([...selectedConns, conn]);
    }
  };

  const handleSelectAll = () => {
    if (selectedConns.length === connections.length) {
      setSelectedConns([]);
    } else {
      setSelectedConns([...connections]);
    }
  };

  const handleGenerateMessage = async () => {
    if (selectedConns.length === 0) return;
    setGeneratingMsg(true);
    try {
      const first = selectedConns[0];
      const res = await axios.post(`${API}/li-search/message/generate`, {
        recipient_name: `${first.first_name} ${first.last_name}`,
        recipient_title: first.occupation || "",
        purpose: msgPurpose,
        company: msgCompany
      });
      setMessageText(res.data.message);
    } catch (err) { alert("Failed to generate message"); }
    finally { setGeneratingMsg(false); }
  };

  const handleSendMessages = async () => {
    if (!messageText.trim() || selectedConns.length === 0) return;
    setSendingMsg(true);
    setSendResult(null);
    try {
      const recipients = selectedConns.map(c => ({
        name: c.full_name || `${c.first_name} ${c.last_name}`,
        profile_url: c.profile_url,
        public_id: c.public_id,
        entity_urn: c.entity_urn || c.urn || ""
      }));
      const res = await axios.post(`${API}/li-search/message/script`, {
        recipients,
        message: messageText
      });
      const script = res.data.script;
      // Try clipboard, but don't fail if it doesn't work
      try {
        await navigator.clipboard.writeText(script);
      } catch (clipErr) {
        // Fallback: use textarea trick
        const ta = document.createElement("textarea");
        ta.value = script;
        ta.style.position = "fixed";
        ta.style.left = "-9999px";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      }
      setSendResult({
        sent: selectedConns.length,
        failed: 0,
        script: true,
        scriptText: script
      });
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || "Unknown error";
      setSendResult({ sent: 0, failed: selectedConns.length, error: detail });
    } finally { setSendingMsg(false); }
  };

  const handleConnSearch = () => {
    setConnPage(0);
    fetchConnections(0, connSearch);
  };

  const handleConnPageChange = (dir) => {
    const newPage = connPage + dir;
    if (newPage < 0) return;
    setConnPage(newPage);
    fetchConnections(newPage, connSearch);
  };

  const handleImportPaste = async () => {
    if (!pasteData.trim()) return;
    setImporting(true);
    try {
      const connections = JSON.parse(pasteData);
      if (!Array.isArray(connections)) throw new Error("Not an array");
      const res = await axios.post(`${API}/li-search/connections/push`, { connections });
      alert(`Imported ${res.data.stored} connections! Total: ${res.data.total}`);
      setPasteData("");
      fetchConnections(0, "");
    } catch (err) {
      if (err.message === "Not an array" || err instanceof SyntaxError) {
        alert("Invalid data. Make sure you copied the data from the LinkedIn console script.");
      } else {
        alert(err.response?.data?.detail || "Import failed");
      }
    } finally { setImporting(false); }
  };

  return (
    <div className="lisearch-container" data-testid="linkedin-search-agent">
      {/* Tabs */}
      <div className="lisearch-tabs" data-testid="agent-tabs">
        <button
          className={`lisearch-tab ${activeTab === "search" ? "lisearch-tab-active" : ""}`}
          onClick={() => setActiveTab("search")}
          data-testid="tab-search"
        >
          <Search size={16} /> Post Search
        </button>
        <button
          className={`lisearch-tab ${activeTab === "messaging" ? "lisearch-tab-active" : ""}`}
          onClick={() => setActiveTab("messaging")}
          data-testid="tab-messaging"
        >
          <Mail size={16} /> Messaging
        </button>
      </div>

      {/* Stats Row */}
      {activeTab === "search" && (
        <div className="lisearch-stats-row" data-testid="lisearch-stats">
          <div className="lisearch-stat-card">
            <span className="lisearch-stat-num">{stats.total_posts || 0}</span>
            <span className="lisearch-stat-label">Total Posts</span>
          </div>
          <div className="lisearch-stat-card" style={{ borderColor: "#22c55e" }}>
            <span className="lisearch-stat-num" style={{ color: "#22c55e" }}>{stats.high_relevance || 0}</span>
            <span className="lisearch-stat-label">High Relevance</span>
          </div>
          <div className="lisearch-stat-card" style={{ borderColor: "#3b82f6" }}>
            <span className="lisearch-stat-num" style={{ color: "#3b82f6" }}>{stats.commented || 0}</span>
            <span className="lisearch-stat-label">Commented</span>
          </div>
        </div>
      )}

      {/* Cookie Setup — shared between tabs */}
      <div className="lisearch-section" data-testid="cookie-section">
        <div className="lisearch-section-header">
          <Key size={18} />
          <h3>LinkedIn Session</h3>
          {cookieStatus?.has_cookie && (
            <span className="lisearch-badge lisearch-badge-success">
              <CheckCircle size={12} /> Connected: {cookieStatus.profile_name}
            </span>
          )}
        </div>
        <div className="lisearch-cookie-form">
          <p className="lisearch-hint">
            Paste your LinkedIn <code>li_at</code> cookie to enable search & messaging.
            Open LinkedIn → F12 → Application → Cookies → copy <code>li_at</code> value.
            {cookieStatus?.has_cookie && " You can update the cookie below if the current one expired."}
          </p>
          <div className="lisearch-input-row">
            <input data-testid="li-at-input" className="lisearch-input" placeholder="li_at cookie value"
              value={liAt} onChange={e => setLiAt(e.target.value)} />
            <input data-testid="jsession-input" className="lisearch-input lisearch-input-sm" placeholder="JSESSIONID (optional)"
              value={jsessionId} onChange={e => setJsessionId(e.target.value)} />
            <button data-testid="save-cookie-btn" className="lisearch-btn lisearch-btn-primary"
              onClick={handleSaveCookie} disabled={savingCookie || !liAt.trim()}>
              {savingCookie ? <Loader2 size={16} className="spin" /> : cookieStatus?.has_cookie ? "Update" : "Connect"}
            </button>
          </div>
          {cookieMsg && (
            <div className={`lisearch-msg lisearch-msg-${cookieMsg.type}`} data-testid="cookie-msg">
              {cookieMsg.type === "success" ? <CheckCircle size={14} /> : <XCircle size={14} />}
              {cookieMsg.text}
            </div>
          )}
        </div>
      </div>

      {/* ==================== SEARCH TAB ==================== */}
      {activeTab === "search" && (
        <>
          {/* Keywords */}
          <div className="lisearch-section" data-testid="keywords-section">
            <div className="lisearch-section-header">
              <Search size={18} /><h3>Search Keywords</h3>
              <span className="lisearch-count">{keywords.length} keywords</span>
            </div>
            <div className="lisearch-keywords-list">
              {keywords.map(kw => (
                <span key={kw} className="lisearch-keyword-tag">
                  {kw}
                  <button onClick={() => handleRemoveKeyword(kw)} className="lisearch-keyword-remove">&times;</button>
                </span>
              ))}
            </div>
            <div className="lisearch-input-row">
              <input data-testid="new-keyword-input" className="lisearch-input" placeholder="Add a search keyword..."
                value={newKeyword} onChange={e => setNewKeyword(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleAddKeyword()} />
              <button className="lisearch-btn lisearch-btn-outline" onClick={handleAddKeyword}>Add</button>
              <button data-testid="save-keywords-btn" className="lisearch-btn lisearch-btn-primary"
                onClick={handleSaveKeywords} disabled={savingKeywords}>
                {savingKeywords ? <Loader2 size={16} className="spin" /> : "Save"}
              </button>
            </div>
          </div>

          {/* Search Trigger */}
          <div className="lisearch-section" data-testid="search-trigger-section">
            <div className="lisearch-section-header"><Sparkles size={18} /><h3>Run Search</h3></div>
            {searchStatus?.running ? (
              <div className="lisearch-progress" data-testid="search-progress">
                <Loader2 size={18} className="spin" />
                <span>Searching: <strong>{searchStatus.current_keyword}</strong>
                  {" "}({searchStatus.keywords_done}/{searchStatus.total_keywords} keywords, {searchStatus.posts_found} new posts)</span>
              </div>
            ) : (
              <div className="lisearch-input-row">
                <button data-testid="start-search-btn" className="lisearch-btn lisearch-btn-accent"
                  onClick={handleSearch} disabled={searching || !cookieStatus?.has_cookie}>
                  {searching ? <Loader2 size={16} className="spin" /> : <Search size={16} />}
                  Search LinkedIn Posts
                </button>
                <button className="lisearch-btn lisearch-btn-outline" onClick={fetchPosts}>
                  <RefreshCw size={16} /> Refresh
                </button>
              </div>
            )}
          </div>

          {/* Filters */}
          <div className="lisearch-section" data-testid="filters-section">
            <div className="lisearch-section-header lisearch-clickable" onClick={() => setShowFilters(!showFilters)}>
              <Filter size={18} /><h3>Filters</h3>
              {showFilters ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </div>
            {showFilters && (
              <div className="lisearch-filters-grid" data-testid="filters-grid">
                <div className="lisearch-filter-group">
                  <label>Category</label>
                  <select data-testid="filter-category" value={filters.category}
                    onChange={e => setFilters(f => ({ ...f, category: e.target.value }))} className="lisearch-select">
                    <option value="all">All Categories</option>
                    {Object.entries(CATEGORY_LABELS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
                  </select>
                </div>
                <div className="lisearch-filter-group">
                  <label>Company Match</label>
                  <select data-testid="filter-company" value={filters.company_match}
                    onChange={e => setFilters(f => ({ ...f, company_match: e.target.value }))} className="lisearch-select">
                    <option value="all">All Companies</option>
                    {Object.entries(COMPANY_LABELS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
                  </select>
                </div>
                <div className="lisearch-filter-group">
                  <label>Relevance</label>
                  <select data-testid="filter-relevance" value={filters.relevance}
                    onChange={e => setFilters(f => ({ ...f, relevance: e.target.value }))} className="lisearch-select">
                    <option value="all">All</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                </div>
              </div>
            )}
          </div>

          {/* Posts */}
          <div className="lisearch-posts" data-testid="posts-list">
            {posts.length === 0 ? (
              <div className="lisearch-empty">
                <Search size={40} style={{ opacity: 0.3 }} />
                <p>No posts found. Run a search to discover LinkedIn leads.</p>
              </div>
            ) : posts.map(post => {
              const catInfo = CATEGORY_LABELS[post.category] || CATEGORY_LABELS.uncategorized;
              const compInfo = COMPANY_LABELS[post.company_match] || COMPANY_LABELS.unknown;
              const relColor = RELEVANCE_COLORS[post.relevance] || "#6b7280";
              const isExpanded = expandedPost === post._id;
              return (
                <div key={post._id} className={`lisearch-post-card ${isExpanded ? "lisearch-post-expanded" : ""}`}
                  data-testid={`post-card-${post._id}`}>
                  <div className="lisearch-post-top" onClick={() => setExpandedPost(isExpanded ? null : post._id)}>
                    <div className="lisearch-post-meta">
                      <strong className="lisearch-post-author">{post.author_name || "Unknown Author"}</strong>
                      <span className="lisearch-post-title">{post.author_title || ""}</span>
                    </div>
                    <div className="lisearch-post-badges">
                      <span className="lisearch-badge" style={{ background: catInfo.color + "22", color: catInfo.color, borderColor: catInfo.color + "44" }}>
                        <Tag size={10} /> {catInfo.label}
                      </span>
                      <span className="lisearch-badge" style={{ background: compInfo.color + "22", color: compInfo.color, borderColor: compInfo.color + "44" }}>
                        <Building2 size={10} /> {compInfo.label}
                      </span>
                      <span className="lisearch-badge" style={{ background: relColor + "22", color: relColor, borderColor: relColor + "44" }}>
                        {post.relevance}
                      </span>
                      {post.commented && <span className="lisearch-badge lisearch-badge-success"><CheckCircle size={10} /> Commented</span>}
                    </div>
                  </div>
                  <div className="lisearch-post-summary">{post.summary || post.text?.substring(0, 150)}</div>
                  {isExpanded && (
                    <div className="lisearch-post-detail">
                      <div className="lisearch-post-text">{post.text}</div>
                      <div className="lisearch-post-actions">
                        {post.post_url && (
                          <a href={post.post_url} target="_blank" rel="noreferrer" className="lisearch-btn lisearch-btn-outline lisearch-btn-sm">
                            <ExternalLink size={14} /> View Post
                          </a>
                        )}
                        <button className="lisearch-btn lisearch-btn-primary lisearch-btn-sm"
                          onClick={() => handleGenerateComment(post, post.company_match || "fundle")}
                          disabled={generatingComment === post._id}>
                          {generatingComment === post._id ? <Loader2 size={14} className="spin" /> : <Sparkles size={14} />}
                          Generate Comment
                        </button>
                        <button className="lisearch-btn lisearch-btn-outline lisearch-btn-sm lisearch-btn-danger"
                          onClick={() => handleDeletePost(post._id)}>
                          <Trash2 size={14} />
                        </button>
                      </div>
                      {generatedComments[post._id] && (
                        <div className="lisearch-comment-preview" data-testid={`comment-preview-${post._id}`}>
                          <div className="lisearch-comment-header"><MessageSquare size={14} /> Generated Comment</div>
                          <textarea className="lisearch-textarea" value={generatedComments[post._id]}
                            onChange={e => setGeneratedComments(prev => ({ ...prev, [post._id]: e.target.value }))} rows={4} />
                          <div className="lisearch-comment-actions">
                            <button className="lisearch-btn lisearch-btn-accent lisearch-btn-sm"
                              onClick={() => handlePostComment(post)} disabled={postingComment === post._id}>
                              {postingComment === post._id ? <Loader2 size={14} className="spin" /> : <Send size={14} />}
                              Post Comment
                            </button>
                            <button className="lisearch-btn lisearch-btn-outline lisearch-btn-sm"
                              onClick={() => navigator.clipboard.writeText(generatedComments[post._id])}>
                              <Copy size={14} /> Copy
                            </button>
                          </div>
                        </div>
                      )}
                      <div className="lisearch-post-footer">
                        <span><Clock size={12} /> {post.time_ago || "Recently"}</span>
                        <span>Keyword: {post.search_keyword}</span>
                        {post.likes > 0 && <span>{post.likes} likes</span>}
                        {post.comments_count > 0 && <span>{post.comments_count} comments</span>}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* ==================== MESSAGING TAB ==================== */}
      {activeTab === "messaging" && (
        <>
          {/* Messaging Stats */}
          <div className="lisearch-stats-row">
            <div className="lisearch-stat-card">
              <span className="lisearch-stat-num">{connectionsTotal}</span>
              <span className="lisearch-stat-label">Connections</span>
            </div>
            <div className="lisearch-stat-card" style={{ borderColor: "#8b5cf6" }}>
              <span className="lisearch-stat-num" style={{ color: "#8b5cf6" }}>{selectedConns.length}</span>
              <span className="lisearch-stat-label">Selected</span>
            </div>
            <div className="lisearch-stat-card" style={{ borderColor: "#22c55e" }}>
              <span className="lisearch-stat-num" style={{ color: "#22c55e" }}>{messageLog.length}</span>
              <span className="lisearch-stat-label">Messages Sent</span>
            </div>
          </div>

          {/* Sync Script */}
          <div className="lisearch-section" data-testid="sync-section">
            <div className="lisearch-section-header">
              <Download size={18} /><h3>Sync Connections from LinkedIn</h3>
            </div>
            <p className="lisearch-hint" style={{ marginBottom: 12 }}>
              To import your LinkedIn connections, run a small script in your browser console while on LinkedIn.
            </p>
            <div className="lisearch-input-row">
              <button className="lisearch-btn lisearch-btn-primary" data-testid="show-sync-script-btn"
                onClick={async () => {
                  if (!syncScript) {
                    try {
                      const res = await axios.get(`${API}/li-search/browser-script`);
                      setSyncScript(res.data);
                    } catch(e) { alert("Failed to load script"); }
                  }
                  setShowSyncScript(!showSyncScript);
                }}>
                {showSyncScript ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                {showSyncScript ? "Hide Script" : "Show Sync Script"}
              </button>
            </div>
            {showSyncScript && syncScript && (
              <div style={{ marginTop: 12 }}>
                <div className="lisearch-hint" style={{ marginBottom: 8 }}>
                  {syncScript.instructions?.map((step, i) => (
                    <div key={i} style={{ marginBottom: 4 }}>{step}</div>
                  ))}
                </div>
                <div style={{ position: "relative" }}>
                  <textarea className="lisearch-textarea" readOnly value={syncScript.script} rows={6}
                    style={{ fontFamily: "monospace", fontSize: 11 }} data-testid="sync-script-textarea" />
                  <button className="lisearch-btn lisearch-btn-outline lisearch-btn-sm"
                    style={{ position: "absolute", top: 8, right: 8 }}
                    onClick={() => { navigator.clipboard.writeText(syncScript.script); alert("Script copied!"); }}>
                    <Copy size={12} /> Copy
                  </button>
                </div>
              </div>
            )}

            {/* Paste & Import */}
            <div style={{ marginTop: 16 }}>
              <label className="lisearch-hint" style={{ display: "block", marginBottom: 6, fontWeight: 500 }}>
                Paste copied connections data below:
              </label>
              <textarea className="lisearch-textarea" placeholder='After running the script on LinkedIn, paste the copied data here (Ctrl+V)...'
                value={pasteData} onChange={e => setPasteData(e.target.value)} rows={3}
                data-testid="paste-connections-textarea" />
              <button className="lisearch-btn lisearch-btn-accent" style={{ marginTop: 8 }}
                onClick={handleImportPaste} disabled={importing || !pasteData.trim()}
                data-testid="import-connections-btn">
                {importing ? <Loader2 size={14} className="spin" /> : <Download size={14} />}
                Import Connections
              </button>
            </div>
          </div>

          {/* Connections List */}
          <div className="lisearch-section" data-testid="connections-section">
            <div className="lisearch-section-header">
              <Users size={18} /><h3>Your Connections</h3>
              <span className="lisearch-count">{connectionsTotal} synced</span>
            </div>

            <div className="lisearch-input-row" style={{ marginBottom: 12 }}>
              <input className="lisearch-input" placeholder="Search connections by name..."
                value={connSearch} onChange={e => setConnSearch(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleConnSearch()}
                data-testid="conn-search-input" />
              <button className="lisearch-btn lisearch-btn-primary" onClick={handleConnSearch}>
                <Search size={14} /> Search
              </button>
              <button className="lisearch-btn lisearch-btn-outline" onClick={() => fetchConnections(connPage, connSearch)}>
                <RefreshCw size={14} />
              </button>
            </div>

            {loadingConns ? (
              <div className="lisearch-progress"><Loader2 size={18} className="spin" /> Loading connections...</div>
            ) : connections.length === 0 ? (
              <div className="lisearch-empty" style={{ padding: "30px 20px" }}>
                <Users size={28} style={{ opacity: 0.3 }} />
                <p>No connections synced yet. Use the sync script above to import your LinkedIn connections.</p>
              </div>
            ) : (
              <>
                <div className="lisearch-conn-toolbar">
                  <button className="lisearch-btn lisearch-btn-outline lisearch-btn-sm" onClick={handleSelectAll}
                    data-testid="select-all-btn">
                    <UserCheck size={14} /> {selectedConns.length === connections.length && connections.length > 0 ? "Deselect All" : "Select All"}
                  </button>
                  <span className="lisearch-count">{selectedConns.length} selected</span>
                </div>

                <div className="lisearch-conn-grid" data-testid="connections-grid">
                  {connections.map(conn => {
                    const isSelected = selectedConns.find(c => c.public_id === conn.public_id);
                    return (
                      <div key={conn.public_id}
                        className={`lisearch-conn-card ${isSelected ? "lisearch-conn-selected" : ""}`}
                        onClick={() => toggleConnSelection(conn)}
                        data-testid={`conn-${conn.public_id}`}>
                        <div className="lisearch-conn-avatar">
                          {conn.avatar_url ? (
                            <img src={conn.avatar_url} alt="" />
                          ) : (
                            <div className="lisearch-conn-avatar-placeholder">
                              {(conn.first_name?.[0] || "?")}{(conn.last_name?.[0] || "")}
                            </div>
                          )}
                          {isSelected && <div className="lisearch-conn-check"><CheckCircle size={14} /></div>}
                        </div>
                        <div className="lisearch-conn-info">
                          <strong>{conn.first_name} {conn.last_name}</strong>
                          <span>{conn.occupation || ""}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>

                {connections.length > 0 && (
                  <div className="lisearch-pagination">
                    <button className="lisearch-btn lisearch-btn-outline lisearch-btn-sm"
                      onClick={() => handleConnPageChange(-1)} disabled={connPage === 0}>
                      <ChevronLeft size={14} /> Prev
                    </button>
                    <span className="lisearch-count">Page {connPage + 1}</span>
                    <button className="lisearch-btn lisearch-btn-outline lisearch-btn-sm"
                      onClick={() => handleConnPageChange(1)} disabled={connections.length < 40}>
                      Next <ChevronRight size={14} />
                    </button>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Compose Message */}
          <div className="lisearch-section" data-testid="compose-section">
            <div className="lisearch-section-header">
              <MessageSquare size={18} /><h3>Compose Message</h3>
            </div>

            {selectedConns.length > 0 && (
              <div className="lisearch-selected-preview">
                <span>Sending to: </span>
                {selectedConns.slice(0, 5).map(c => (
                  <span key={c.public_id} className="lisearch-keyword-tag">
                    {c.first_name} {c.last_name}
                    <button onClick={() => toggleConnSelection(c)} className="lisearch-keyword-remove">&times;</button>
                  </span>
                ))}
                {selectedConns.length > 5 && <span className="lisearch-count">+{selectedConns.length - 5} more</span>}
              </div>
            )}

            <div className="lisearch-compose-controls">
              <div className="lisearch-filter-group">
                <label>Purpose</label>
                <select className="lisearch-select" value={msgPurpose}
                  onChange={e => setMsgPurpose(e.target.value)} data-testid="msg-purpose-select">
                  <option value="introduce services">Introduce Services</option>
                  <option value="schedule a call">Schedule a Call</option>
                  <option value="partnership opportunity">Partnership Opportunity</option>
                  <option value="follow up on previous conversation">Follow Up</option>
                  <option value="share industry insights">Share Insights</option>
                </select>
              </div>
              <div className="lisearch-filter-group">
                <label>As Company</label>
                <select className="lisearch-select" value={msgCompany}
                  onChange={e => setMsgCompany(e.target.value)} data-testid="msg-company-select">
                  <option value="fundle">Fundle.ai</option>
                  <option value="tagandpay">TagandPay</option>
                  <option value="exceed">Exceed</option>
                </select>
              </div>
              <div className="lisearch-filter-group" style={{ display: "flex", alignItems: "flex-end" }}>
                <button className="lisearch-btn lisearch-btn-primary" onClick={handleGenerateMessage}
                  disabled={generatingMsg || selectedConns.length === 0} data-testid="generate-msg-btn">
                  {generatingMsg ? <Loader2 size={14} className="spin" /> : <Sparkles size={14} />}
                  AI Generate
                </button>
              </div>
            </div>

            <textarea className="lisearch-textarea" placeholder="Type your message here or click 'AI Generate'..."
              value={messageText} onChange={e => setMessageText(e.target.value)} rows={5}
              data-testid="message-textarea" />

            <div className="lisearch-input-row" style={{ marginTop: 12 }}>
              <button className="lisearch-btn lisearch-btn-accent" onClick={handleSendMessages}
                disabled={sendingMsg || !messageText.trim() || selectedConns.length === 0}
                data-testid="send-messages-btn">
                {sendingMsg ? <Loader2 size={16} className="spin" /> : <Send size={16} />}
                Send to {selectedConns.length} Connection{selectedConns.length !== 1 ? "s" : ""} via LinkedIn
              </button>
            </div>

            {sendResult?.script && (
              <div style={{ marginTop: 12 }}>
                <div className="lisearch-msg lisearch-msg-success" data-testid="send-result">
                  <CheckCircle size={14} />
                  Auto-send script copied to clipboard! Paste it in LinkedIn's console (F12 → Console → allow pasting → Ctrl+V → Enter)
                </div>
                <details style={{ marginTop: 8 }}>
                  <summary className="lisearch-hint" style={{ cursor: "pointer", fontWeight: 500 }}>
                    View/Copy Script
                  </summary>
                  <div style={{ position: "relative", marginTop: 8 }}>
                    <textarea className="lisearch-textarea" readOnly value={sendResult.scriptText} rows={5}
                      style={{ fontFamily: "monospace", fontSize: 11 }} />
                    <button className="lisearch-btn lisearch-btn-outline lisearch-btn-sm"
                      style={{ position: "absolute", top: 8, right: 8 }}
                      onClick={() => { navigator.clipboard.writeText(sendResult.scriptText); }}>
                      <Copy size={12} /> Copy
                    </button>
                  </div>
                </details>
              </div>
            )}

            {sendResult?.error && (
              <div className="lisearch-msg lisearch-msg-error" style={{ marginTop: 12 }}>
                <XCircle size={14} /> {sendResult.error}
              </div>
            )}
          </div>

          {/* Message Log */}
          {messageLog.length > 0 && (
            <div className="lisearch-section" data-testid="message-log-section">
              <div className="lisearch-section-header">
                <Clock size={18} /><h3>Message Log</h3>
                <span className="lisearch-count">{messageLog.length} sent</span>
              </div>
              <div className="lisearch-log-list">
                {messageLog.slice(0, 20).map(msg => (
                  <div key={msg._id} className="lisearch-log-item">
                    <span className="lisearch-log-time">
                      {msg.sent_at ? new Date(msg.sent_at).toLocaleString() : ""}
                    </span>
                    <span className="lisearch-log-text">{msg.message_text?.substring(0, 100)}...</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default LinkedInSearch;
