import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import {
  Loader2, Search, Send, RefreshCw, Trash2, Filter,
  ExternalLink, MessageSquare, Sparkles, Key, CheckCircle,
  XCircle, Clock, ChevronDown, ChevronUp, Copy, Building2, Tag
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
  const [cookieStatus, setCookieStatus] = useState(null);
  const [liAt, setLiAt] = useState("");
  const [jsessionId, setJsessionId] = useState("");
  const [savingCookie, setSavingCookie] = useState(false);
  const [cookieMsg, setCookieMsg] = useState(null);

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

  const pollRef = useRef(null);

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

  useEffect(() => {
    fetchCookieStatus();
    fetchKeywords();
    fetchPosts();
    fetchSearchStatus();
  }, [fetchCookieStatus, fetchKeywords, fetchPosts, fetchSearchStatus]);

  useEffect(() => {
    fetchPosts();
  }, [filters, fetchPosts]);

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

  const handleSaveCookie = async () => {
    if (!liAt.trim()) return;
    setSavingCookie(true);
    setCookieMsg(null);
    try {
      const res = await axios.post(`${API}/li-search/cookie`, {
        li_at: liAt.trim(),
        jsessionid: jsessionId.trim() || null
      });
      setCookieMsg({ type: "success", text: `Connected as ${res.data.profile}` });
      fetchCookieStatus();
      setLiAt("");
      setJsessionId("");
    } catch (err) {
      setCookieMsg({ type: "error", text: err.response?.data?.detail || "Failed to save cookie" });
    } finally {
      setSavingCookie(false);
    }
  };

  const handleAddKeyword = () => {
    if (!newKeyword.trim() || keywords.includes(newKeyword.trim())) return;
    setKeywords([...keywords, newKeyword.trim()]);
    setNewKeyword("");
  };

  const handleRemoveKeyword = (kw) => setKeywords(keywords.filter(k => k !== kw));

  const handleSaveKeywords = async () => {
    setSavingKeywords(true);
    try {
      await axios.post(`${API}/li-search/keywords`, { keywords });
    } catch (err) { console.error(err); }
    finally { setSavingKeywords(false); }
  };

  const handleSearch = async () => {
    setSearching(true);
    try {
      await axios.post(`${API}/li-search/search`);
      fetchSearchStatus();
    } catch (err) {
      alert(err.response?.data?.detail || "Search failed");
    } finally {
      setSearching(false);
    }
  };

  const handleGenerateComment = async (post, company) => {
    setGeneratingComment(post._id);
    try {
      const res = await axios.post(`${API}/li-search/posts/${post._id}/generate-comment`, { company });
      setGeneratedComments(prev => ({ ...prev, [post._id]: res.data.comment }));
    } catch (err) {
      alert("Failed to generate comment");
    } finally {
      setGeneratingComment(null);
    }
  };

  const handlePostComment = async (post) => {
    const comment = generatedComments[post._id];
    if (!comment) return;
    setPostingComment(post._id);
    try {
      const res = await axios.post(`${API}/li-search/posts/${post._id}/comment`, {
        post_urn: post.post_urn,
        comment_text: comment
      });
      if (res.data.success) {
        fetchPosts();
        setGeneratedComments(prev => { const n = { ...prev }; delete n[post._id]; return n; });
      } else {
        alert(res.data.error || "Comment failed");
      }
    } catch (err) {
      alert(err.response?.data?.detail || "Failed to post comment");
    } finally {
      setPostingComment(null);
    }
  };

  const handleDeletePost = async (id) => {
    try {
      await axios.delete(`${API}/li-search/posts/${id}`);
      fetchPosts();
    } catch (err) { console.error(err); }
  };

  return (
    <div className="lisearch-container" data-testid="linkedin-search-agent">
      {/* Header Stats */}
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

      {/* Cookie Setup */}
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
        {!cookieStatus?.has_cookie && (
          <div className="lisearch-cookie-form">
            <p className="lisearch-hint">
              Paste your LinkedIn <code>li_at</code> cookie to enable search.
              Open LinkedIn → F12 → Application → Cookies → copy <code>li_at</code> value.
            </p>
            <div className="lisearch-input-row">
              <input
                data-testid="li-at-input"
                className="lisearch-input"
                placeholder="li_at cookie value"
                value={liAt}
                onChange={e => setLiAt(e.target.value)}
              />
              <input
                data-testid="jsession-input"
                className="lisearch-input lisearch-input-sm"
                placeholder="JSESSIONID (optional)"
                value={jsessionId}
                onChange={e => setJsessionId(e.target.value)}
              />
              <button
                data-testid="save-cookie-btn"
                className="lisearch-btn lisearch-btn-primary"
                onClick={handleSaveCookie}
                disabled={savingCookie || !liAt.trim()}
              >
                {savingCookie ? <Loader2 size={16} className="spin" /> : "Connect"}
              </button>
            </div>
            {cookieMsg && (
              <div className={`lisearch-msg lisearch-msg-${cookieMsg.type}`} data-testid="cookie-msg">
                {cookieMsg.type === "success" ? <CheckCircle size={14} /> : <XCircle size={14} />}
                {cookieMsg.text}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Keywords Config */}
      <div className="lisearch-section" data-testid="keywords-section">
        <div className="lisearch-section-header">
          <Search size={18} />
          <h3>Search Keywords</h3>
          <span className="lisearch-count">{keywords.length} keywords</span>
        </div>
        <div className="lisearch-keywords-list">
          {keywords.map(kw => (
            <span key={kw} className="lisearch-keyword-tag" data-testid={`keyword-${kw}`}>
              {kw}
              <button onClick={() => handleRemoveKeyword(kw)} className="lisearch-keyword-remove">&times;</button>
            </span>
          ))}
        </div>
        <div className="lisearch-input-row">
          <input
            data-testid="new-keyword-input"
            className="lisearch-input"
            placeholder="Add a search keyword..."
            value={newKeyword}
            onChange={e => setNewKeyword(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleAddKeyword()}
          />
          <button className="lisearch-btn lisearch-btn-outline" onClick={handleAddKeyword}>Add</button>
          <button
            data-testid="save-keywords-btn"
            className="lisearch-btn lisearch-btn-primary"
            onClick={handleSaveKeywords}
            disabled={savingKeywords}
          >
            {savingKeywords ? <Loader2 size={16} className="spin" /> : "Save"}
          </button>
        </div>
      </div>

      {/* Search Trigger */}
      <div className="lisearch-section" data-testid="search-trigger-section">
        <div className="lisearch-section-header">
          <Sparkles size={18} />
          <h3>Run Search</h3>
        </div>
        {searchStatus?.running ? (
          <div className="lisearch-progress" data-testid="search-progress">
            <Loader2 size={18} className="spin" />
            <span>
              Searching: <strong>{searchStatus.current_keyword}</strong>
              {" "}({searchStatus.keywords_done}/{searchStatus.total_keywords} keywords, {searchStatus.posts_found} new posts)
            </span>
          </div>
        ) : (
          <div className="lisearch-input-row">
            <button
              data-testid="start-search-btn"
              className="lisearch-btn lisearch-btn-accent"
              onClick={handleSearch}
              disabled={searching || !cookieStatus?.has_cookie}
            >
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
        <div
          className="lisearch-section-header lisearch-clickable"
          onClick={() => setShowFilters(!showFilters)}
        >
          <Filter size={18} />
          <h3>Filters</h3>
          {showFilters ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
        {showFilters && (
          <div className="lisearch-filters-grid" data-testid="filters-grid">
            <div className="lisearch-filter-group">
              <label>Category</label>
              <select
                data-testid="filter-category"
                value={filters.category}
                onChange={e => setFilters(f => ({ ...f, category: e.target.value }))}
                className="lisearch-select"
              >
                <option value="all">All Categories</option>
                {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v.label}</option>
                ))}
              </select>
            </div>
            <div className="lisearch-filter-group">
              <label>Company Match</label>
              <select
                data-testid="filter-company"
                value={filters.company_match}
                onChange={e => setFilters(f => ({ ...f, company_match: e.target.value }))}
                className="lisearch-select"
              >
                <option value="all">All Companies</option>
                {Object.entries(COMPANY_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v.label}</option>
                ))}
              </select>
            </div>
            <div className="lisearch-filter-group">
              <label>Relevance</label>
              <select
                data-testid="filter-relevance"
                value={filters.relevance}
                onChange={e => setFilters(f => ({ ...f, relevance: e.target.value }))}
                className="lisearch-select"
              >
                <option value="all">All</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
          </div>
        )}
      </div>

      {/* Posts List */}
      <div className="lisearch-posts" data-testid="posts-list">
        {posts.length === 0 ? (
          <div className="lisearch-empty">
            <Search size={40} style={{ opacity: 0.3 }} />
            <p>No posts found. Run a search to discover LinkedIn leads.</p>
          </div>
        ) : (
          posts.map(post => {
            const catInfo = CATEGORY_LABELS[post.category] || CATEGORY_LABELS.uncategorized;
            const compInfo = COMPANY_LABELS[post.company_match] || COMPANY_LABELS.unknown;
            const relColor = RELEVANCE_COLORS[post.relevance] || "#6b7280";
            const isExpanded = expandedPost === post._id;

            return (
              <div
                key={post._id}
                className={`lisearch-post-card ${isExpanded ? "lisearch-post-expanded" : ""}`}
                data-testid={`post-card-${post._id}`}
              >
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
                    {post.commented && (
                      <span className="lisearch-badge lisearch-badge-success">
                        <CheckCircle size={10} /> Commented
                      </span>
                    )}
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
                      <button
                        className="lisearch-btn lisearch-btn-primary lisearch-btn-sm"
                        onClick={() => handleGenerateComment(post, post.company_match || "fundle")}
                        disabled={generatingComment === post._id}
                        data-testid={`generate-comment-${post._id}`}
                      >
                        {generatingComment === post._id ? <Loader2 size={14} className="spin" /> : <Sparkles size={14} />}
                        Generate Comment
                      </button>
                      <button
                        className="lisearch-btn lisearch-btn-outline lisearch-btn-sm lisearch-btn-danger"
                        onClick={() => handleDeletePost(post._id)}
                        data-testid={`delete-post-${post._id}`}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>

                    {generatedComments[post._id] && (
                      <div className="lisearch-comment-preview" data-testid={`comment-preview-${post._id}`}>
                        <div className="lisearch-comment-header">
                          <MessageSquare size={14} /> Generated Comment
                        </div>
                        <textarea
                          className="lisearch-textarea"
                          value={generatedComments[post._id]}
                          onChange={e => setGeneratedComments(prev => ({ ...prev, [post._id]: e.target.value }))}
                          rows={4}
                        />
                        <div className="lisearch-comment-actions">
                          <button
                            className="lisearch-btn lisearch-btn-accent lisearch-btn-sm"
                            onClick={() => handlePostComment(post)}
                            disabled={postingComment === post._id}
                            data-testid={`post-comment-${post._id}`}
                          >
                            {postingComment === post._id ? <Loader2 size={14} className="spin" /> : <Send size={14} />}
                            Post Comment
                          </button>
                          <button
                            className="lisearch-btn lisearch-btn-outline lisearch-btn-sm"
                            onClick={() => {
                              navigator.clipboard.writeText(generatedComments[post._id]);
                            }}
                          >
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
          })
        )}
      </div>
    </div>
  );
};

export default LinkedInSearch;
