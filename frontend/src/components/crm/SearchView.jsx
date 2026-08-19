import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import {
  Search, Loader2, Sparkles, Send, ExternalLink, Filter, Plus, X,
  ChevronDown, ChevronUp, Copy, Tag, RefreshCw, MessageSquare
} from "lucide-react";

const CATEGORY_COLORS = {
  performance_marketing: "#ef4444", digital_marketing: "#f59e0b", loyalty_rewards: "#8b5cf6",
  social_media: "#ec4899", branding: "#06b6d4", d2c_ecommerce: "#14b8a6",
  tech_development: "#6366f1", b2b_sales: "#22c55e", general_agency: "#64748b",
  not_relevant: "#475569", uncategorized: "#6b7280",
};
const CATEGORY_LABELS = {
  performance_marketing: "Performance Marketing", digital_marketing: "Digital Marketing",
  loyalty_rewards: "Loyalty & Rewards", social_media: "Social Media", branding: "Branding",
  d2c_ecommerce: "D2C / E-commerce", tech_development: "Tech/Dev", b2b_sales: "B2B Sales",
  general_agency: "General Agency", not_relevant: "Not Relevant", uncategorized: "Uncategorized",
};
const RELEVANCE_COLORS = { high: "#10b981", medium: "#f59e0b", low: "#ef4444" };

export default function SearchView({ API, cookieStatus }) {
  const [keywords, setKeywords] = useState([]);
  const [newKeyword, setNewKeyword] = useState("");
  const [posts, setPosts] = useState([]);
  const [stats, setStats] = useState({});
  const [searching, setSearching] = useState(false);
  const [searchStatus, setSearchStatus] = useState(null);
  const [filters, setFilters] = useState({ category: "all", company_match: "all", relevance: "all" });
  const [showFilters, setShowFilters] = useState(false);
  const [expandedPost, setExpandedPost] = useState(null);
  const [generatingComment, setGeneratingComment] = useState(null);
  const [generatedComments, setGeneratedComments] = useState({});
  const [postingComment, setPostingComment] = useState(null);
  const pollRef = useRef(null);

  const fetchKeywords = useCallback(async () => {
    try { const r = await axios.get(`${API}/li-search/keywords`); setKeywords(r.data.keywords || []); } catch {}
  }, [API]);

  const fetchPosts = useCallback(async () => {
    try {
      const params = {};
      if (filters.category !== "all") params.category = filters.category;
      if (filters.company_match !== "all") params.company_match = filters.company_match;
      if (filters.relevance !== "all") params.relevance = filters.relevance;
      const r = await axios.get(`${API}/li-search/posts`, { params });
      setPosts(r.data.posts || []); setStats(r.data.stats || {});
    } catch {}
  }, [API, filters]);

  const fetchSearchStatus = useCallback(async () => {
    try { const r = await axios.get(`${API}/li-search/search/status`); setSearchStatus(r.data); return r.data; } catch { return null; }
  }, [API]);

  useEffect(() => { fetchKeywords(); fetchPosts(); fetchSearchStatus(); }, [fetchKeywords, fetchPosts, fetchSearchStatus]);
  useEffect(() => { fetchPosts(); }, [filters, fetchPosts]);
  useEffect(() => {
    if (searchStatus?.running) {
      pollRef.current = setInterval(async () => {
        const st = await fetchSearchStatus();
        if (!st?.running) { clearInterval(pollRef.current); fetchPosts(); }
      }, 3000);
      return () => clearInterval(pollRef.current);
    }
  }, [searchStatus?.running, fetchSearchStatus, fetchPosts]);

  const handleSaveKeywords = async () => {
    try { await axios.post(`${API}/li-search/keywords`, { keywords }); } catch {}
  };
  const handleAddKeyword = () => {
    if (!newKeyword.trim() || keywords.includes(newKeyword.trim())) return;
    setKeywords([...keywords, newKeyword.trim()]); setNewKeyword("");
  };

  const handleSearch = async () => {
    setSearching(true);
    try {
      await axios.post(`${API}/li-search/search`);
      setSearchStatus({ running: true });
    } catch {} finally { setSearching(false); }
  };

  const handleGenerateComment = async (postId) => {
    setGeneratingComment(postId);
    try {
      const r = await axios.post(`${API}/li-search/posts/${postId}/generate-comment`, { company: "fundle" });
      setGeneratedComments(prev => ({ ...prev, [postId]: r.data.comment }));
    } catch {} finally { setGeneratingComment(null); }
  };

  const handlePostComment = async (postId) => {
    const comment = generatedComments[postId];
    if (!comment) return;
    setPostingComment(postId);
    try {
      await axios.post(`${API}/li-search/posts/${postId}/comment`, { comment_text: comment });
      setGeneratedComments(prev => { const n = { ...prev }; delete n[postId]; return n; });
      fetchPosts();
    } catch {} finally { setPostingComment(null); }
  };

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Search Keywords */}
      <div className="rounded-md border p-5" style={{ background: "#18181b", borderColor: "#27272a" }}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2" style={{ fontFamily: "'Manrope', sans-serif" }}>
            <Search size={16} style={{ color: "#2563eb" }} /> Search Keywords
          </h3>
          <span className="text-xs" style={{ color: "#a1a1aa" }}>{keywords.length} keywords</span>
        </div>

        <div className="flex flex-wrap gap-2 mb-3">
          {keywords.map(kw => (
            <span key={kw} className="text-xs px-3 py-1.5 rounded-full flex items-center gap-1.5 border" style={{ borderColor: "#27272a", color: "#fff", background: "#27272a" }}>
              {kw}
              <button onClick={() => setKeywords(keywords.filter(k => k !== kw))} className="hover:text-red-400">
                <X size={12} />
              </button>
            </span>
          ))}
        </div>

        <div className="flex gap-2">
          <input
            data-testid="add-keyword-input"
            value={newKeyword}
            onChange={(e) => setNewKeyword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAddKeyword()}
            placeholder="Add a search keyword..."
            className="flex-1 px-3 py-2 rounded-md text-sm border"
            style={{ background: "#09090b", borderColor: "#27272a", color: "#fff" }}
          />
          <button onClick={handleAddKeyword} className="px-3 py-2 rounded-md border text-sm" style={{ borderColor: "#27272a", color: "#a1a1aa" }}>
            <Plus size={16} />
          </button>
          <button onClick={handleSaveKeywords} className="px-4 py-2 rounded-md text-sm font-medium text-white" style={{ background: "#2563eb" }}>
            Save
          </button>
        </div>

        {/* Search Button */}
        <div className="flex items-center gap-3 mt-4">
          <button
            data-testid="search-posts-btn"
            onClick={handleSearch}
            disabled={searching || searchStatus?.running || !cookieStatus?.has_cookie}
            className="px-5 py-2.5 rounded-md text-sm font-medium text-white flex items-center gap-2 transition-colors duration-150 disabled:opacity-50"
            style={{ background: "#2563eb" }}
          >
            {searching || searchStatus?.running ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
            {searchStatus?.running ? `Searching... (${searchStatus.processed || 0}/${searchStatus.total || 0})` : "Search LinkedIn Posts"}
          </button>
          <button onClick={fetchPosts} className="px-3 py-2.5 rounded-md border text-sm" style={{ borderColor: "#27272a", color: "#a1a1aa" }}>
            <RefreshCw size={16} />
          </button>
        </div>
      </div>

      {/* Stats Bar */}
      <div className="flex items-center gap-4">
        <span className="text-sm font-medium text-white">{stats.total || 0} posts</span>
        <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "#10b98120", color: "#10b981" }}>{stats.high || 0} high</span>
        <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "#f59e0b20", color: "#f59e0b" }}>{stats.medium || 0} medium</span>
        <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "#ef444420", color: "#ef4444" }}>{stats.low || 0} low</span>
        <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "#6b728020", color: "#6b7280" }}>{stats.commented || 0} commented</span>
        <div className="ml-auto">
          <button
            data-testid="toggle-filters-btn"
            onClick={() => setShowFilters(!showFilters)}
            className="flex items-center gap-1 text-xs px-3 py-1.5 rounded-md border"
            style={{ borderColor: "#27272a", color: "#a1a1aa" }}
          >
            <Filter size={14} /> Filters {showFilters ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </button>
        </div>
      </div>

      {/* Filters */}
      {showFilters && (
        <div className="flex gap-3 p-4 rounded-md border" style={{ background: "#18181b", borderColor: "#27272a" }}>
          <select value={filters.category} onChange={(e) => setFilters({ ...filters, category: e.target.value })} className="px-3 py-1.5 rounded text-sm border" style={{ background: "#09090b", borderColor: "#27272a", color: "#fff" }}>
            <option value="all">All Categories</option>
            {Object.entries(CATEGORY_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <select value={filters.relevance} onChange={(e) => setFilters({ ...filters, relevance: e.target.value })} className="px-3 py-1.5 rounded text-sm border" style={{ background: "#09090b", borderColor: "#27272a", color: "#fff" }}>
            <option value="all">All Relevance</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <select value={filters.company_match} onChange={(e) => setFilters({ ...filters, company_match: e.target.value })} className="px-3 py-1.5 rounded text-sm border" style={{ background: "#09090b", borderColor: "#27272a", color: "#fff" }}>
            <option value="all">All Companies</option>
            <option value="fundle">Fundle</option>
            <option value="tagandpay">TagandPay</option>
            <option value="exceed">Exceed</option>
          </select>
        </div>
      )}

      {/* Posts List */}
      <div className="space-y-3">
        {posts.map((post) => (
          <div
            key={post._id || post.post_urn}
            data-testid={`post-card-${post._id}`}
            className="rounded-md border p-4 transition-colors duration-150"
            style={{ background: "#18181b", borderColor: "#27272a" }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = "#2563eb40"; }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = "#27272a"; }}
          >
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <p className="text-sm font-medium text-white">{post.author_name || "Unknown"}</p>
                  {post.category && (
                    <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: `${CATEGORY_COLORS[post.category] || "#6b7280"}20`, color: CATEGORY_COLORS[post.category] || "#6b7280" }}>
                      {CATEGORY_LABELS[post.category] || post.category}
                    </span>
                  )}
                  <span className="text-xs px-2 py-0.5 rounded-full font-medium" style={{ background: `${RELEVANCE_COLORS[post.relevance] || "#6b7280"}20`, color: RELEVANCE_COLORS[post.relevance] || "#6b7280" }}>
                    {post.relevance}
                  </span>
                </div>
                <p className="text-xs mb-2" style={{ color: "#a1a1aa" }}>{post.author_headline}</p>
                <p className="text-sm text-white leading-relaxed">
                  {expandedPost === post._id ? post.post_text : (post.post_text || "").substring(0, 200)}
                  {(post.post_text || "").length > 200 && (
                    <button onClick={() => setExpandedPost(expandedPost === post._id ? null : post._id)} className="ml-1 text-xs" style={{ color: "#2563eb" }}>
                      {expandedPost === post._id ? "less" : "...more"}
                    </button>
                  )}
                </p>
              </div>
              <div className="flex items-center gap-2 ml-4 flex-shrink-0">
                {post.post_url && (
                  <a href={post.post_url} target="_blank" rel="noreferrer" className="p-2 rounded-md border transition-colors duration-150" style={{ borderColor: "#27272a", color: "#a1a1aa" }}>
                    <ExternalLink size={14} />
                  </a>
                )}
              </div>
            </div>

            {/* Comment Actions */}
            <div className="flex items-center gap-2 mt-3 pt-3 border-t" style={{ borderColor: "#27272a" }}>
              {post.comment_posted ? (
                <span className="text-xs flex items-center gap-1" style={{ color: "#10b981" }}>
                  <MessageSquare size={12} /> Commented
                </span>
              ) : (
                <>
                  <button
                    data-testid={`generate-comment-${post._id}`}
                    onClick={() => handleGenerateComment(post._id)}
                    disabled={generatingComment === post._id}
                    className="text-xs px-3 py-1.5 rounded-md flex items-center gap-1 transition-colors duration-150"
                    style={{ background: "#27272a", color: "#fff" }}
                  >
                    {generatingComment === post._id ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
                    AI Comment
                  </button>
                  {generatedComments[post._id] && (
                    <>
                      <div className="flex-1 text-xs px-3 py-1.5 rounded-md border max-w-md truncate" style={{ borderColor: "#27272a", color: "#a1a1aa" }}>
                        {generatedComments[post._id]}
                      </div>
                      <button
                        onClick={() => handlePostComment(post._id)}
                        disabled={postingComment === post._id}
                        className="text-xs px-3 py-1.5 rounded-md flex items-center gap-1 text-white"
                        style={{ background: "#2563eb" }}
                      >
                        {postingComment === post._id ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
                        Post
                      </button>
                    </>
                  )}
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
