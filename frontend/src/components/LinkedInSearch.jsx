import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import {
  Loader2, Search, Send, RefreshCw, Trash2, Filter,
  ExternalLink, MessageSquare, Sparkles, Key, CheckCircle,
  XCircle, Clock, ChevronDown, ChevronUp, Copy, Building2, Tag,
  Users, Mail, UserCheck, ChevronLeft, ChevronRight, Download, Plug
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

      {/* ==================== MESSAGING / CRM TAB ==================== */}
      {activeTab === "messaging" && (
        <CRMTab />
      )}
    </div>
  );
};

/* ==================== CRM TAB COMPONENT ==================== */
const CRMTab = () => {
  const [view, setView] = useState("contacts"); // contacts | compose | log | detail
  const [contacts, setContacts] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("full_name");
  const [sortDir, setSortDir] = useState(1);
  const [filterContacted, setFilterContacted] = useState("");
  const [filterCompany, setFilterCompany] = useState("");
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState([]);
  const [stats, setStats] = useState(null);
  const [detailContact, setDetailContact] = useState(null);
  const [messageText, setMessageText] = useState("");
  const [sendResult, setSendResult] = useState(null);
  const [sendingMsg, setSendingMsg] = useState(false);
  const [msgLog, setMsgLog] = useState([]);
  const [msgLogTotal, setMsgLogTotal] = useState(0);
  const [syncScript, setSyncScript] = useState(null);
  const [showSync, setShowSync] = useState(false);
  const [pasteData, setPasteData] = useState("");
  const [importing, setImporting] = useState(false);
  const PAGE_SIZE = 50;

  const fetchContacts = useCallback(async (p = 0) => {
    setLoading(true);
    try {
      const params = { start: p * PAGE_SIZE, count: PAGE_SIZE, sort_by: sortBy, sort_dir: sortDir };
      if (search) params.keyword = search;
      if (filterContacted) params.filter_contacted = filterContacted;
      if (filterCompany) params.filter_company = filterCompany;
      const res = await axios.get(`${API}/li-search/connections`, { params });
      setContacts(res.data.connections || []);
      setTotal(res.data.total || 0);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [search, sortBy, sortDir, filterContacted, filterCompany]);

  const fetchStats = async () => {
    try {
      const res = await axios.get(`${API}/li-search/connections/stats/overview`);
      setStats(res.data);
    } catch (e) {}
  };

  const fetchMsgLog = async (p = 0) => {
    try {
      const res = await axios.get(`${API}/li-search/messages/log`, { params: { start: p * 50, count: 50 } });
      setMsgLog(res.data.messages || []);
      setMsgLogTotal(res.data.total || 0);
    } catch (e) {}
  };

  useEffect(() => { fetchContacts(page); }, [page, fetchContacts]);
  useEffect(() => { fetchStats(); }, []);

  const toggleSelect = (c) => {
    setSelected(prev => prev.find(s => s.public_id === c.public_id)
      ? prev.filter(s => s.public_id !== c.public_id)
      : [...prev, c]);
  };
  const selectAll = () => {
    if (selected.length === contacts.length) setSelected([]);
    else setSelected([...contacts]);
  };

  const openDetail = async (publicId) => {
    try {
      const res = await axios.get(`${API}/li-search/connections/${publicId}`);
      setDetailContact(res.data);
      setView("detail");
    } catch (e) { console.error(e); }
  };

  const handleImport = async () => {
    if (!pasteData.trim()) return;
    setImporting(true);
    try {
      const parsed = JSON.parse(pasteData.trim());
      const arr = Array.isArray(parsed) ? parsed : [parsed];
      const res = await axios.post(`${API}/li-search/connections/push`, { connections: arr });
      alert(`Imported! New: ${res.data.new}, Duplicates skipped: ${res.data.duplicates}, Total: ${res.data.total}`);
      setPasteData("");
      fetchContacts(0); fetchStats();
    } catch (e) { alert("Invalid data format"); }
    finally { setImporting(false); }
  };

  const handleCompose = async () => {
    if (!selected.length || !messageText.trim()) return;
    setSendingMsg(true); setSendResult(null);
    try {
      const recipients = selected.map(c => ({
        name: c.full_name || `${c.first_name} ${c.last_name}`,
        public_id: c.public_id, entity_urn: c.entity_urn || "",
        occupation: c.occupation || ""
      }));
      // Push to extension queue
      await axios.post(`${API}/li-search/message/queue`, { recipients, message: messageText });
      // Log messages
      for (const r of recipients) {
        await axios.post(`${API}/li-search/messages/log`, {
          public_id: r.public_id, recipient_name: r.name, message: messageText
        }).catch(() => {});
      }
      fetchStats();
      setSendResult({ queued: true, count: recipients.length });
    } catch (e) { setSendResult({ error: e.response?.data?.detail || "Failed" }); }
    finally { setSendingMsg(false); }
  };

  const doSearch = () => { setPage(0); fetchContacts(0); };

  return (
    <>
      {/* Stats Bar */}
      <div className="crm-stats" data-testid="crm-stats">
        <div className="crm-stat-card">
          <span className="crm-stat-num">{stats?.total_connections || 0}</span>
          <span className="crm-stat-label">Total Contacts</span>
        </div>
        <div className="crm-stat-card crm-stat-green">
          <span className="crm-stat-num">{stats?.contacted || 0}</span>
          <span className="crm-stat-label">Contacted</span>
        </div>
        <div className="crm-stat-card crm-stat-amber">
          <span className="crm-stat-num">{stats?.not_contacted || 0}</span>
          <span className="crm-stat-label">Not Contacted</span>
        </div>
        <div className="crm-stat-card crm-stat-purple">
          <span className="crm-stat-num">{stats?.total_messages || 0}</span>
          <span className="crm-stat-label">Messages Sent</span>
        </div>
        <div className="crm-stat-card">
          <span className="crm-stat-num">{selected.length}</span>
          <span className="crm-stat-label">Selected</span>
        </div>
      </div>

      {/* Nav */}
      <div className="crm-nav" data-testid="crm-nav">
        {[["contacts", "Contacts"], ["compose", "Compose"], ["log", "Message Log"], ["sync", "Sync"]].map(([k, l]) => (
          <button key={k} className={`crm-nav-btn ${(view === k || (k === "sync" && showSync)) ? "active" : ""}`}
            onClick={() => { if (k === "sync") { setShowSync(!showSync); if (view !== "contacts") setView("contacts"); }
              else { setView(k); setShowSync(false); if (k === "log") fetchMsgLog(); } }}
            data-testid={`crm-nav-${k}`}>
            {k === "contacts" && <Users size={14} />}
            {k === "compose" && <MessageSquare size={14} />}
            {k === "log" && <Clock size={14} />}
            {k === "sync" && <Download size={14} />}
            {l}
          </button>
        ))}
        <a href="/linkedin-lead-agent-extension.zip" download className="crm-nav-btn" style={{ textDecoration: "none", marginLeft: "auto" }}>
          <Download size={14} /> Extension
        </a>
      </div>

      {/* Sync Panel (collapsible) */}
      {showSync && (
        <div className="crm-sync-panel" data-testid="sync-panel">
          <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
            <button className="crm-btn crm-btn-primary" onClick={async () => {
              if (!syncScript) {
                try { const r = await axios.get(`${API}/li-search/browser-script`); setSyncScript(r.data); } catch(e) {}
              }
            }}>
              {syncScript ? <Copy size={13} /> : <Download size={13} />}
              {syncScript ? "Script Ready" : "Load Sync Script"}
            </button>
            {syncScript && (
              <button className="crm-btn crm-btn-accent" onClick={() => { navigator.clipboard.writeText(syncScript.script); alert("Copied!"); }}>
                <Copy size={13} /> Copy Script
              </button>
            )}
          </div>
          {syncScript && (
            <div className="crm-sync-steps">
              {syncScript.instructions?.map((s, i) => <div key={i} className="crm-sync-step">{s}</div>)}
            </div>
          )}
          <div style={{ marginTop: 10 }}>
            <textarea className="crm-textarea" placeholder="Paste copied connections JSON here..." rows={2}
              value={pasteData} onChange={e => setPasteData(e.target.value)} data-testid="paste-input" />
            <button className="crm-btn crm-btn-accent" style={{ marginTop: 6 }}
              onClick={handleImport} disabled={importing || !pasteData.trim()} data-testid="import-btn">
              {importing ? <Loader2 size={13} className="spin" /> : <Download size={13} />} Import
            </button>
          </div>
        </div>
      )}

      {/* ===== CONTACTS VIEW ===== */}
      {view === "contacts" && (
        <div className="crm-contacts" data-testid="crm-contacts">
          {/* Search & Filters */}
          <div className="crm-toolbar">
            <div className="crm-search-box">
              <Search size={14} />
              <input placeholder="Search name, title, company..." value={search}
                onChange={e => setSearch(e.target.value)}
                onKeyDown={e => e.key === "Enter" && doSearch()} data-testid="crm-search" />
            </div>
            <select className="crm-select" value={filterContacted} onChange={e => { setFilterContacted(e.target.value); setPage(0); }}
              data-testid="filter-contacted">
              <option value="">All</option>
              <option value="yes">Contacted</option>
              <option value="no">Not Contacted</option>
            </select>
            <select className="crm-select" value={sortBy} onChange={e => { setSortBy(e.target.value); setPage(0); }}
              data-testid="sort-by">
              <option value="full_name">Name A-Z</option>
              <option value="occupation">Title</option>
              <option value="company">Company</option>
              <option value="last_contacted">Last Contacted</option>
              <option value="messages_sent">Most Messaged</option>
              <option value="synced_at">Recently Synced</option>
            </select>
            <button className="crm-btn crm-btn-sm" onClick={selectAll} data-testid="select-all">
              <UserCheck size={13} /> {selected.length === contacts.length && contacts.length > 0 ? "Deselect" : "Select All"}
            </button>
          </div>

          {/* Company filter */}
          {stats?.top_companies?.length > 0 && (
            <div className="crm-company-chips">
              <button className={`crm-chip ${!filterCompany ? "active" : ""}`}
                onClick={() => { setFilterCompany(""); setPage(0); }}>All</button>
              {stats.top_companies.slice(0, 6).map(tc => (
                <button key={tc.company} className={`crm-chip ${filterCompany === tc.company ? "active" : ""}`}
                  onClick={() => { setFilterCompany(filterCompany === tc.company ? "" : tc.company); setPage(0); }}>
                  {tc.company} ({tc.count})
                </button>
              ))}
            </div>
          )}

          {/* Table */}
          {loading ? (
            <div className="crm-loading"><Loader2 size={20} className="spin" /> Loading...</div>
          ) : contacts.length === 0 ? (
            <div className="crm-empty"><Users size={28} /><p>No contacts found. Sync your LinkedIn connections first.</p></div>
          ) : (
            <div className="crm-table-wrap" data-testid="contacts-table">
              <table className="crm-table">
                <thead>
                  <tr>
                    <th style={{width:36}}></th>
                    <th>Name</th>
                    <th>Title / Company</th>
                    <th>Msgs</th>
                    <th>Last Contact</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {contacts.map(c => {
                    const isSel = selected.find(s => s.public_id === c.public_id);
                    return (
                      <tr key={c.public_id} className={isSel ? "crm-row-selected" : ""} data-testid={`row-${c.public_id}`}>
                        <td>
                          <input type="checkbox" checked={!!isSel} onChange={() => toggleSelect(c)} />
                        </td>
                        <td className="crm-name-cell" onClick={() => openDetail(c.public_id)} style={{cursor:"pointer"}}>
                          <div className="crm-avatar">{(c.first_name?.[0] || "?")}{(c.last_name?.[0] || "")}</div>
                          <div>
                            <strong>{c.full_name || `${c.first_name} ${c.last_name}`}</strong>
                          </div>
                        </td>
                        <td className="crm-occ-cell">
                          <div className="crm-occ-text">{c.occupation || "—"}</div>
                          {c.company && <div className="crm-company-text">{c.company}</div>}
                        </td>
                        <td className="crm-msg-count">{c.messages_sent || 0}</td>
                        <td className="crm-date-cell">
                          {c.last_contacted ? new Date(c.last_contacted).toLocaleDateString() : <span className="crm-not-contacted">Never</span>}
                        </td>
                        <td>
                          <div style={{display:"flex",gap:4}}>
                            <button className="crm-btn crm-btn-xs" onClick={() => openDetail(c.public_id)} title="View"><Users size={12} /></button>
                            <a href={c.profile_url} target="_blank" rel="noreferrer" className="crm-btn crm-btn-xs" title="LinkedIn"><ExternalLink size={12} /></a>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          <div className="crm-pagination">
            <button className="crm-btn crm-btn-sm" disabled={page === 0} onClick={() => setPage(p => p - 1)}>
              <ChevronLeft size={14} /> Prev
            </button>
            <span className="crm-page-info">
              {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total}
            </span>
            <button className="crm-btn crm-btn-sm" disabled={(page + 1) * PAGE_SIZE >= total} onClick={() => setPage(p => p + 1)}>
              Next <ChevronRight size={14} />
            </button>
          </div>

          {/* Quick compose bar when contacts selected */}
          {selected.length > 0 && view === "contacts" && (
            <div className="crm-compose-bar" data-testid="quick-compose">
              <span>{selected.length} selected</span>
              <button className="crm-btn crm-btn-primary" onClick={() => setView("compose")}>
                <MessageSquare size={14} /> Compose Message
              </button>
              <button className="crm-btn crm-btn-sm" onClick={() => setSelected([])}>Clear</button>
            </div>
          )}
        </div>
      )}

      {/* ===== COMPOSE VIEW ===== */}
      {view === "compose" && (
        <div className="crm-compose" data-testid="crm-compose">
          <div className="crm-compose-recipients">
            <h3><Send size={14} /> Sending to {selected.length} contact{selected.length !== 1 ? "s" : ""}</h3>
            <div className="crm-tag-list">
              {selected.slice(0, 10).map(c => (
                <span key={c.public_id} className="crm-tag">
                  {c.full_name || c.first_name} <button onClick={() => toggleSelect(c)}>&times;</button>
                </span>
              ))}
              {selected.length > 10 && <span className="crm-tag">+{selected.length - 10} more</span>}
            </div>
          </div>
          <textarea className="crm-textarea crm-compose-input" placeholder="Write your message..."
            value={messageText} onChange={e => setMessageText(e.target.value)} rows={6} data-testid="compose-textarea" />
          <div className="crm-compose-actions">
            <button className="crm-btn crm-btn-primary" onClick={handleCompose}
              disabled={sendingMsg || !messageText.trim() || !selected.length} data-testid="send-compose"
              style={{padding: "12px 24px", fontSize: 14}}>
              {sendingMsg ? <Loader2 size={16} className="spin" /> : <Send size={16} />}
              Send to Extension ({selected.length})
            </button>
            <button className="crm-btn crm-btn-sm" onClick={() => setView("contacts")}>Back to Contacts</button>
          </div>

          {sendResult?.queued && (
            <div className="crm-script-result" data-testid="compose-result">
              <div className="crm-msg-success">
                <CheckCircle size={14} />
                Queued {sendResult.count} messages to extension!
              </div>
              <div style={{background:"#0f172a",borderRadius:8,padding:14,marginTop:10,fontSize:12,color:"#cbd5e1",lineHeight:1.7}}>
                <strong style={{color:"#f1f5f9"}}>Next steps:</strong><br/>
                1. Go to LinkedIn (any page)<br/>
                2. Click the <strong style={{color:"#60a5fa"}}>⚡ Lead Agent</strong> button (bottom-right)<br/>
                3. Click <strong style={{color:"#c084fc"}}>"Check Message Queue"</strong><br/>
                4. The compose panel will show each recipient — click "Compose + Copy" for each<br/>
                5. Paste your message (Ctrl+V) in the compose window → Send
              </div>
            </div>
          )}
          {sendResult?.error && <div className="crm-msg-error"><XCircle size={14} /> {sendResult.error}</div>}
        </div>
      )}

      {/* ===== MESSAGE LOG ===== */}
      {view === "log" && (
        <div className="crm-log" data-testid="crm-log">
          <h3 style={{marginBottom:12}}><Clock size={16} /> Message Log ({msgLogTotal} total)</h3>
          {msgLog.length === 0 ? (
            <div className="crm-empty"><Mail size={28} /><p>No messages sent yet.</p></div>
          ) : (
            <div className="crm-table-wrap">
              <table className="crm-table">
                <thead><tr><th>Date</th><th>Recipient</th><th>Message</th></tr></thead>
                <tbody>
                  {msgLog.map(m => (
                    <tr key={m._id}>
                      <td className="crm-date-cell">{m.sent_at ? new Date(m.sent_at).toLocaleString() : ""}</td>
                      <td><strong>{m.recipient_name || m.public_id}</strong></td>
                      <td className="crm-occ-cell">{m.message?.substring(0, 100)}{m.message?.length > 100 ? "..." : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ===== CONTACT DETAIL ===== */}
      {view === "detail" && detailContact && (
        <div className="crm-detail" data-testid="crm-detail">
          <button className="crm-btn crm-btn-sm" onClick={() => { setView("contacts"); setDetailContact(null); }} style={{marginBottom:12}}>
            <ChevronLeft size={14} /> Back
          </button>
          <div className="crm-detail-header">
            <div className="crm-detail-avatar">{(detailContact.first_name?.[0] || "?")}{(detailContact.last_name?.[0] || "")}</div>
            <div>
              <h2>{detailContact.full_name}</h2>
              <p>{detailContact.occupation}</p>
              {detailContact.company && <p className="crm-company-text">{detailContact.company}</p>}
              <a href={detailContact.profile_url} target="_blank" rel="noreferrer" className="crm-detail-link">
                <ExternalLink size={12} /> LinkedIn Profile
              </a>
            </div>
          </div>
          <div className="crm-detail-stats">
            <div><strong>{detailContact.messages_sent || 0}</strong><span>Messages</span></div>
            <div><strong>{detailContact.last_contacted ? new Date(detailContact.last_contacted).toLocaleDateString() : "Never"}</strong><span>Last Contact</span></div>
            <div><strong>{detailContact.synced_at ? new Date(detailContact.synced_at).toLocaleDateString() : "—"}</strong><span>Synced</span></div>
          </div>
          <h3 style={{marginTop:16,marginBottom:8,fontSize:13}}><Clock size={14} /> Message History</h3>
          {(detailContact.message_history || []).length === 0 ? (
            <p style={{color:"#64748b",fontSize:12}}>No messages sent to this contact yet.</p>
          ) : (
            <div className="crm-history-list">
              {detailContact.message_history.map(m => (
                <div key={m._id} className="crm-history-item">
                  <span className="crm-history-date">{m.sent_at ? new Date(m.sent_at).toLocaleString() : ""}</span>
                  <p className="crm-history-msg">{m.message}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </>
  );
};

export default LinkedInSearch;
