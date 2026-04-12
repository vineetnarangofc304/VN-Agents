import { useState, useEffect, useCallback, useRef } from "react";
import {
  Loader2, Play, Square, Download, Search, Phone, User, MapPin,
  FileSpreadsheet, Globe, CheckCircle, RefreshCw, Filter
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const HearClearLeads = () => {
  const [status, setStatus] = useState(null);
  const [leads, setLeads] = useState([]);
  const [totalLeads, setTotalLeads] = useState(0);
  const [stats, setStats] = useState(null);
  const [categories, setCategories] = useState([]);
  const [filterCategory, setFilterCategory] = useState("");
  const [filterCity, setFilterCity] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const [isStarting, setIsStarting] = useState(false);
  const [statusMsg, setStatusMsg] = useState(null);
  const pollRef = useRef(null);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API}/hearclear-leads/status`);
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
        return data;
      }
    } catch (err) { console.error(err); }
    return null;
  }, []);

  const fetchLeads = useCallback(async () => {
    try {
      const params = new URLSearchParams({ page, per_page: 100 });
      if (filterCategory) params.set("category", filterCategory);
      if (filterCity) params.set("city", filterCity);
      if (searchQuery) params.set("search", searchQuery);
      const res = await fetch(`${API}/hearclear-leads/leads?${params}`);
      if (res.ok) {
        const data = await res.json();
        setLeads(data.leads || []);
        setTotalLeads(data.total || 0);
      }
    } catch (err) { console.error(err); }
  }, [page, filterCategory, filterCity, searchQuery]);

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch(`${API}/hearclear-leads/stats`);
      if (res.ok) setStats(await res.json());
    } catch (err) { console.error(err); }
  }, []);

  const fetchCategories = useCallback(async () => {
    try {
      const res = await fetch(`${API}/hearclear-leads/categories`);
      if (res.ok) {
        const data = await res.json();
        setCategories(data.categories || []);
      }
    } catch (err) { console.error(err); }
  }, []);

  useEffect(() => {
    fetchStatus();
    fetchLeads();
    fetchStats();
    fetchCategories();
  }, [fetchStatus, fetchLeads, fetchStats, fetchCategories]);

  useEffect(() => {
    fetchLeads();
  }, [page, filterCategory, filterCity, fetchLeads]);

  // Poll when running
  useEffect(() => {
    if (status?.status === "running") {
      pollRef.current = setInterval(async () => {
        const s = await fetchStatus();
        await fetchLeads();
        await fetchStats();
        if (s && s.status !== "running") clearInterval(pollRef.current);
      }, 5000);
      return () => clearInterval(pollRef.current);
    }
  }, [status?.status, fetchStatus, fetchLeads, fetchStats]);

  const handleStart = async () => {
    setIsStarting(true);
    try {
      const res = await fetch(`${API}/hearclear-leads/start`, { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        setStatusMsg({ type: "success", text: data.message || "Crawler started!" });
        fetchStatus();
      }
    } catch (err) {
      setStatusMsg({ type: "error", text: "Failed to start crawler" });
    } finally {
      setIsStarting(false);
    }
  };

  const handleStop = async () => {
    try {
      await fetch(`${API}/hearclear-leads/stop`, { method: "POST" });
      setStatusMsg({ type: "success", text: "Crawler stopped" });
      fetchStatus();
    } catch (err) {
      setStatusMsg({ type: "error", text: "Failed to stop" });
    }
  };

  const handleSearch = () => {
    setPage(1);
    fetchLeads();
  };

  const handleDownload = () => {
    const params = new URLSearchParams();
    if (filterCategory) params.set("category", filterCategory);
    if (filterCity) params.set("city", filterCity);
    window.open(`${API}/hearclear-leads/download?${params}`, "_blank");
  };

  const isRunning = status?.status === "running";
  const totalQueries = status?.total_queries || 0;
  const queriesDone = status?.queries_done || 0;
  const progress = totalQueries > 0 ? (queriesDone / totalQueries * 100).toFixed(1) : 0;

  return (
    <div className="hcl-container" data-testid="hearclear-leads">
      {/* Header */}
      <div className="hcl-header">
        <div>
          <h2 className="hcl-title">HearClear Lead Finder</h2>
          <p className="hcl-subtitle">Delhi NCR contact database — RWA, clubs, schools, govt, professionals & more</p>
        </div>
        {totalLeads > 0 && (
          <button className="hcl-download-btn" onClick={handleDownload} data-testid="download-leads-btn">
            <FileSpreadsheet size={16} /> Export {totalLeads.toLocaleString()} Leads
          </button>
        )}
      </div>

      {statusMsg && (
        <div className={`li-status-msg ${statusMsg.type}`}>
          <CheckCircle size={16} />
          <span>{statusMsg.text}</span>
          <button className="li-dismiss" onClick={() => setStatusMsg(null)}>&times;</button>
        </div>
      )}

      {/* Stats Cards */}
      {stats && stats.total_leads > 0 && (
        <div className="hcl-stats-grid" data-testid="lead-stats">
          <div className="hcl-stat-card">
            <span className="hcl-stat-num">{stats.total_leads.toLocaleString()}</span>
            <span className="hcl-stat-label">Total Contacts</span>
          </div>
          <div className="hcl-stat-card">
            <span className="hcl-stat-num">{stats.with_name.toLocaleString()}</span>
            <span className="hcl-stat-label">With Name</span>
          </div>
          <div className="hcl-stat-card">
            <span className="hcl-stat-num">{stats.with_email.toLocaleString()}</span>
            <span className="hcl-stat-label">With Email</span>
          </div>
          <div className="hcl-stat-card">
            <span className="hcl-stat-num">{Object.keys(stats.by_category || {}).length}</span>
            <span className="hcl-stat-label">Categories</span>
          </div>
        </div>
      )}

      {/* Category breakdown */}
      {stats && Object.keys(stats.by_category || {}).length > 0 && (
        <div className="hcl-breakdown" data-testid="category-breakdown">
          {Object.entries(stats.by_category).map(([cat, count]) => (
            <span key={cat} className="hcl-breakdown-chip">{cat}: {count.toLocaleString()}</span>
          ))}
        </div>
      )}

      {/* Controls */}
      <div className="hcl-controls" data-testid="crawl-controls">
        {!isRunning ? (
          <button className="ck-start-btn" onClick={handleStart} disabled={isStarting} data-testid="start-crawl-btn">
            {isStarting ? <><Loader2 className="spin" size={16} /> Starting...</> :
              queriesDone > 0 ? <><Play size={16} /> Resume Crawl</> : <><Play size={16} /> Start Crawl</>
            }
          </button>
        ) : (
          <button className="ck-stop-btn" onClick={handleStop} data-testid="stop-crawl-btn">
            <Square size={16} /> Stop Crawl
          </button>
        )}
      </div>

      {/* Progress */}
      {status && status.status !== "idle" && (
        <div className="hcl-progress" data-testid="crawl-progress">
          <div className="hcl-progress-header">
            <span className="hcl-progress-title">Crawl Progress</span>
            <span className={`ck-status-badge ${status.status}`}>
              {status.status === "resumable" ? "paused" : status.status}
            </span>
          </div>
          <div className="ck-progress-bar-container">
            <div className="ck-progress-bar" style={{ width: `${progress}%` }} />
          </div>
          <div className="hcl-progress-stats">
            <span>{queriesDone}/{totalQueries} queries</span>
            <span>{(status.files_downloaded || 0).toLocaleString()} files</span>
            <span className="hcl-highlight">{(status.contacts_extracted || 0).toLocaleString()} contacts</span>
            <span>{progress}%</span>
          </div>
          {isRunning && status.current_query && (
            <div className="ck-current-email">
              <Loader2 className="spin" size={14} /> {status.current_query}
            </div>
          )}
        </div>
      )}

      {/* Filters */}
      <div className="hcl-filters" data-testid="lead-filters">
        <div className="hcl-filter-row">
          <div className="hcl-search-box">
            <Search size={16} />
            <input
              type="text"
              placeholder="Search phone, name, email..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              data-testid="lead-search-input"
            />
          </div>
          <select
            value={filterCategory}
            onChange={(e) => { setFilterCategory(e.target.value); setPage(1); }}
            className="hcl-select"
            data-testid="category-filter"
          >
            <option value="">All Categories</option>
            {categories.map(c => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          <select
            value={filterCity}
            onChange={(e) => { setFilterCity(e.target.value); setPage(1); }}
            className="hcl-select"
            data-testid="city-filter"
          >
            <option value="">All Cities</option>
            <option value="Delhi">Delhi</option>
            <option value="Noida">Noida</option>
            <option value="Gurgaon">Gurgaon</option>
            <option value="Faridabad">Faridabad</option>
            <option value="Ghaziabad">Ghaziabad</option>
          </select>
        </div>
      </div>

      {/* Results Table */}
      <div className="hcl-results" data-testid="leads-table">
        <div className="hcl-results-header">
          <h3><Phone size={16} /> Contacts ({totalLeads.toLocaleString()})</h3>
          {totalLeads > 100 && (
            <div className="hcl-pagination">
              <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="hcl-page-btn">&lt;</button>
              <span>Page {page}</span>
              <button disabled={leads.length < 100} onClick={() => setPage(page + 1)} className="hcl-page-btn">&gt;</button>
            </div>
          )}
        </div>
        {leads.length === 0 ? (
          <div className="ck-empty">
            <Globe size={32} />
            <p>{isRunning ? "Crawling... contacts will appear here" : "No contacts yet — start a crawl"}</p>
          </div>
        ) : (
          <div className="ck-results-table-container">
            <table className="dir-table">
              <thead>
                <tr>
                  <th style={{ width: 40 }}>#</th>
                  <th>Phone</th>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Category</th>
                  <th>City</th>
                </tr>
              </thead>
              <tbody>
                {leads.map((lead, idx) => (
                  <tr key={lead.phone} className="dir-row" data-testid={`lead-row-${idx}`}>
                    <td className="dir-cell-num">{(page - 1) * 100 + idx + 1}</td>
                    <td>
                      <span className="ck-email-success"><Phone size={12} /> {lead.phone}</span>
                    </td>
                    <td>{lead.name || <span style={{ color: "var(--text-muted)" }}>—</span>}</td>
                    <td>{lead.email || <span style={{ color: "var(--text-muted)" }}>—</span>}</td>
                    <td><span className="hcl-cat-badge">{lead.category_name || lead.category}</span></td>
                    <td>{lead.city || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default HearClearLeads;
