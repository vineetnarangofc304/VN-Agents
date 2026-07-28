import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Area, AreaChart
} from "recharts";
import {
  Upload, Loader2, TrendingDown, TrendingUp, Wallet, Search,
  Filter, ChevronDown, ChevronUp, ArrowUpDown, X, CreditCard,
  Building2, Calendar, IndianRupee, FileText, Trash2, Eye
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const CATEGORY_COLORS = {
  "Gaming": "#ef4444",
  "Food & Groceries": "#f97316",
  "Food & Dining": "#fb923c",
  "Person Transfer": "#8b5cf6",
  "Self Transfer": "#a78bfa",
  "Bank Transfer": "#6366f1",
  "Shopping": "#ec4899",
  "Transport": "#14b8a6",
  "Bills & Utilities": "#0ea5e9",
  "Subscriptions": "#6366f1",
  "Subscriptions & Services": "#818cf8",
  "Loan EMI": "#dc2626",
  "Health": "#22c55e",
  "Insurance & Finance": "#0d9488",
  "Education": "#8b5cf6",
  "Fuel": "#d97706",
  "Services": "#64748b",
  "Refund": "#10b981",
  "Interest Income": "#059669",
  "Uncategorized": "#94a3b8",
  "POS/Card": "#e879f9",
  "E-commerce": "#f472b6",
};

const INR = (n) => {
  if (n === undefined || n === null) return "₹0";
  const abs = Math.abs(n);
  if (abs >= 10000000) return `₹${(n / 10000000).toFixed(2)}Cr`;
  if (abs >= 100000) return `₹${(n / 100000).toFixed(2)}L`;
  if (abs >= 1000) return `₹${(n / 1000).toFixed(1)}K`;
  return `₹${n.toFixed(0)}`;
};

const INR_FULL = (n) => `₹${(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;

const BankingAgent = () => {
  const [view, setView] = useState("upload"); // upload | dashboard | transactions
  const [statements, setStatements] = useState([]);
  const [activeStmt, setActiveStmt] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [txnTotal, setTxnTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);

  // Filters
  const [filters, setFilters] = useState({
    category: "", merchant: "", txn_type: "", date_from: "", date_to: "",
    debit_only: false, credit_only: false, search: "",
  });
  const [showFilters, setShowFilters] = useState(false);
  const [txnPage, setTxnPage] = useState(0);
  const [sortField, setSortField] = useState("date");
  const [sortDir, setSortDir] = useState(-1);
  const [dashTab, setDashTab] = useState("overview"); // overview | categories | merchants | trends
  const fileRef = useRef(null);

  const fetchStatements = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/banking/statements`);
      setStatements(res.data.statements || []);
    } catch (e) { console.error(e); }
  }, []);

  useEffect(() => { fetchStatements(); }, [fetchStatements]);

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("password", password);
      const res = await axios.post(`${API}/banking/upload`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 120000,
      });
      if (res.data.success) {
        setActiveStmt(res.data.stmt_id);
        await fetchStatements();
        loadDashboard(res.data.stmt_id);
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Upload failed. Check password.");
    } finally { setUploading(false); }
  };

  const loadDashboard = async (stmtId) => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get(`${API}/banking/dashboard/${stmtId}`);
      setDashboard(res.data);
      setActiveStmt(stmtId);
      setView("dashboard");
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load dashboard");
    } finally { setLoading(false); }
  };

  const loadTransactions = useCallback(async (stmtId, page = 0) => {
    setLoading(true);
    try {
      const params = { skip: page * 100, limit: 100, sort: sortField, sort_dir: sortDir };
      if (filters.category) params.category = filters.category;
      if (filters.merchant) params.merchant = filters.merchant;
      if (filters.txn_type) params.txn_type = filters.txn_type;
      if (filters.date_from) params.date_from = filters.date_from;
      if (filters.date_to) params.date_to = filters.date_to;
      if (filters.debit_only) params.debit_only = true;
      if (filters.credit_only) params.credit_only = true;
      if (filters.search) params.search = filters.search;
      const res = await axios.get(`${API}/banking/transactions/${stmtId}`, { params });
      setTransactions(res.data.transactions || []);
      setTxnTotal(res.data.total || 0);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  }, [filters, sortField, sortDir]);

  const handleDeleteStmt = async (stmtId) => {
    if (!window.confirm("Delete this statement and all transactions?")) return;
    try {
      await axios.delete(`${API}/banking/statements/${stmtId}`);
      fetchStatements();
      if (activeStmt === stmtId) { setView("upload"); setDashboard(null); }
    } catch (e) { console.error(e); }
  };

  const handleFilterMerchant = (merchant) => {
    setFilters(f => ({ ...f, merchant, category: "" }));
    setTxnPage(0);
    setView("transactions");
  };

  const handleFilterCategory = (category) => {
    setFilters(f => ({ ...f, category, merchant: "" }));
    setTxnPage(0);
    setView("transactions");
  };

  useEffect(() => {
    if (activeStmt && view === "transactions") loadTransactions(activeStmt, txnPage);
  }, [activeStmt, view, txnPage, loadTransactions]);

  const s = dashboard?.summary;
  const monthly = dashboard?.monthly || [];
  const categories = dashboard?.categories || [];
  const merchants = dashboard?.merchants || [];
  const balanceTrend = dashboard?.balance_trend || [];
  const txnTypes = dashboard?.txn_types || [];

  // Pie chart data for categories (debits only, top 8 + others)
  const debitCats = categories.filter(c => c.debit > 0).sort((a, b) => b.debit - a.debit);
  const pieData = debitCats.slice(0, 8);
  const othersDebit = debitCats.slice(8).reduce((sum, c) => sum + c.debit, 0);
  if (othersDebit > 0) pieData.push({ category: "Others", debit: othersDebit });

  return (
    <div className="banking-container" data-testid="banking-agent">
      {/* Top Nav */}
      <div className="banking-nav" data-testid="banking-nav">
        <button className={`banking-nav-btn ${view === "upload" ? "active" : ""}`}
          onClick={() => setView("upload")} data-testid="nav-upload">
          <Upload size={15} /> Statements
        </button>
        {dashboard && (
          <>
            <button className={`banking-nav-btn ${view === "dashboard" ? "active" : ""}`}
              onClick={() => setView("dashboard")} data-testid="nav-dashboard">
              <Wallet size={15} /> Dashboard
            </button>
            <button className={`banking-nav-btn ${view === "transactions" ? "active" : ""}`}
              onClick={() => { setView("transactions"); loadTransactions(activeStmt, 0); }}
              data-testid="nav-transactions">
              <FileText size={15} /> Transactions
            </button>
          </>
        )}
      </div>

      {error && <div className="banking-error" data-testid="error-msg"><X size={14} /> {error}</div>}

      {/* ===== UPLOAD VIEW ===== */}
      {view === "upload" && (
        <div className="banking-upload-view">
          <div className="banking-upload-card" data-testid="upload-card">
            <div className="banking-upload-icon"><CreditCard size={40} /></div>
            <h2>Upload Bank Statement</h2>
            <p>Upload your bank statement PDF to analyze spending, merchants, and cash flow.</p>
            <div className="banking-upload-form">
              <input type="password" className="banking-input" placeholder="PDF Password (if encrypted)"
                value={password} onChange={e => setPassword(e.target.value)} data-testid="pdf-password-input" />
              <input ref={fileRef} type="file" accept=".pdf" onChange={handleUpload}
                style={{ display: "none" }} data-testid="file-input" />
              <button className="banking-btn banking-btn-primary" data-testid="upload-btn"
                onClick={() => fileRef.current?.click()} disabled={uploading}>
                {uploading ? <><Loader2 size={16} className="spin" /> Parsing...</> : <><Upload size={16} /> Choose PDF</>}
              </button>
            </div>
          </div>

          {statements.length > 0 && (
            <div className="banking-stmt-list" data-testid="stmt-list">
              <h3>Previous Statements</h3>
              {statements.map(st => (
                <div key={st.stmt_id} className="banking-stmt-item" data-testid={`stmt-${st.stmt_id}`}>
                  <div className="banking-stmt-info">
                    <strong>{st.bank_name || "Bank Statement"}</strong>
                    <span>{st.account_holder} — {st.statement_period}</span>
                    <span className="banking-stmt-meta">{st.total_transactions} transactions</span>
                  </div>
                  <div className="banking-stmt-actions">
                    <button className="banking-btn banking-btn-sm" data-testid={`view-stmt-${st.stmt_id}`}
                      onClick={() => loadDashboard(st.stmt_id)}>
                      <Eye size={14} /> View
                    </button>
                    <button className="banking-btn banking-btn-sm banking-btn-danger"
                      onClick={() => handleDeleteStmt(st.stmt_id)}>
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ===== DASHBOARD VIEW ===== */}
      {view === "dashboard" && dashboard && (
        <div className="banking-dashboard" data-testid="banking-dashboard">
          {/* Summary Cards */}
          <div className="banking-summary-row" data-testid="summary-cards">
            <div className="banking-card banking-card-accent">
              <span className="banking-card-label">Opening Balance</span>
              <span className="banking-card-value">{INR_FULL(s.opening_balance)}</span>
            </div>
            <div className="banking-card" style={{ borderTop: "3px solid #ef4444" }}>
              <TrendingDown size={18} color="#ef4444" />
              <span className="banking-card-label">Total Debits</span>
              <span className="banking-card-value" style={{ color: "#ef4444" }}>{INR_FULL(s.total_debit)}</span>
            </div>
            <div className="banking-card" style={{ borderTop: "3px solid #22c55e" }}>
              <TrendingUp size={18} color="#22c55e" />
              <span className="banking-card-label">Total Credits</span>
              <span className="banking-card-value" style={{ color: "#22c55e" }}>{INR_FULL(s.total_credit)}</span>
            </div>
            <div className="banking-card" style={{ borderTop: `3px solid ${s.net_flow >= 0 ? "#22c55e" : "#ef4444"}` }}>
              <IndianRupee size={18} />
              <span className="banking-card-label">Net Flow</span>
              <span className="banking-card-value" style={{ color: s.net_flow >= 0 ? "#22c55e" : "#ef4444" }}>
                {s.net_flow >= 0 ? "+" : ""}{INR_FULL(s.net_flow)}
              </span>
            </div>
            <div className="banking-card banking-card-accent">
              <span className="banking-card-label">Closing Balance</span>
              <span className="banking-card-value">{INR_FULL(s.closing_balance)}</span>
            </div>
          </div>

          <div className="banking-info-bar">
            <Building2 size={14} /> {s.bank_name} — {s.account_holder} — A/C: {s.account_number?.slice(-6)} — {s.statement_period} — {s.total_transactions} txns
          </div>

          {/* Dashboard Sub-tabs */}
          <div className="banking-tabs" data-testid="dash-tabs">
            {[
              ["overview", "Overview"], ["categories", "Categories"], ["merchants", "Top Merchants"], ["trends", "Trends"]
            ].map(([key, label]) => (
              <button key={key} className={`banking-tab ${dashTab === key ? "active" : ""}`}
                onClick={() => setDashTab(key)} data-testid={`tab-${key}`}>{label}</button>
            ))}
          </div>

          {/* OVERVIEW TAB */}
          {dashTab === "overview" && (
            <div className="banking-charts">
              {/* Monthly Debits vs Credits */}
              <div className="banking-chart-card" data-testid="monthly-chart">
                <h3>Monthly Debits vs Credits</h3>
                <ResponsiveContainer width="100%" height={320}>
                  <BarChart data={monthly} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="month" tick={{ fill: "#94a3b8", fontSize: 12 }}
                      tickFormatter={v => { const [y, m] = v.split("-"); return ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][parseInt(m)-1] + " " + y.slice(2); }} />
                    <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} tickFormatter={v => INR(v)} />
                    <Tooltip formatter={v => INR_FULL(v)} labelFormatter={v => v}
                      contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, color: "#e2e8f0" }} />
                    <Legend />
                    <Bar dataKey="debit" name="Debits" fill="#ef4444" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="credit" name="Credits" fill="#22c55e" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Category Pie */}
              <div className="banking-chart-card" data-testid="category-pie">
                <h3>Spending by Category</h3>
                <ResponsiveContainer width="100%" height={320}>
                  <PieChart>
                    <Pie data={pieData} dataKey="debit" nameKey="category" cx="50%" cy="50%"
                      innerRadius={60} outerRadius={120} paddingAngle={2} label={({ category, percent }) =>
                        percent > 0.04 ? `${category} ${(percent * 100).toFixed(0)}%` : ""
                      } labelLine={false}>
                      {pieData.map((entry, i) => (
                        <Cell key={i} fill={CATEGORY_COLORS[entry.category] || "#64748b"} cursor="pointer" />
                      ))}
                    </Pie>
                    <Tooltip formatter={v => INR_FULL(v)}
                      contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, color: "#e2e8f0" }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              {/* Transaction Type Breakdown */}
              <div className="banking-chart-card" data-testid="txn-type-chart">
                <h3>Transaction Types</h3>
                <div className="banking-type-list">
                  {txnTypes.map(tt => (
                    <div key={tt.type} className="banking-type-item">
                      <span className="banking-type-name">{tt.type}</span>
                      <span className="banking-type-count">{tt.count} txns</span>
                      <span className="banking-type-debit">{tt.debit > 0 ? `−${INR(tt.debit)}` : ""}</span>
                      <span className="banking-type-credit">{tt.credit > 0 ? `+${INR(tt.credit)}` : ""}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* CATEGORIES TAB */}
          {dashTab === "categories" && (
            <div className="banking-detail-grid" data-testid="categories-view">
              <div className="banking-chart-card wide">
                <h3>Category-wise Spending</h3>
                <ResponsiveContainer width="100%" height={Math.max(300, categories.length * 32)}>
                  <BarChart data={categories.filter(c => c.debit > 0)} layout="vertical"
                    margin={{ top: 5, right: 30, left: 120, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis type="number" tick={{ fill: "#94a3b8", fontSize: 11 }} tickFormatter={v => INR(v)} />
                    <YAxis type="category" dataKey="category" tick={{ fill: "#e2e8f0", fontSize: 12 }} width={110} />
                    <Tooltip formatter={v => INR_FULL(v)}
                      contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, color: "#e2e8f0" }} />
                    <Bar dataKey="debit" name="Total Spent" radius={[0, 4, 4, 0]}>
                      {categories.filter(c => c.debit > 0).map((entry, i) => (
                        <Cell key={i} fill={CATEGORY_COLORS[entry.category] || "#64748b"} cursor="pointer" />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="banking-cat-table" data-testid="cat-table">
                <table>
                  <thead>
                    <tr><th>Category</th><th>Txns</th><th>Debits</th><th>Credits</th></tr>
                  </thead>
                  <tbody>
                    {categories.map(c => (
                      <tr key={c.category} className="banking-clickable"
                        onClick={() => handleFilterCategory(c.category)} data-testid={`cat-row-${c.category}`}>
                        <td>
                          <span className="banking-cat-dot" style={{ background: CATEGORY_COLORS[c.category] || "#64748b" }} />
                          {c.category}
                        </td>
                        <td>{c.count}</td>
                        <td className="banking-amt-debit">{c.debit > 0 ? INR_FULL(c.debit) : "—"}</td>
                        <td className="banking-amt-credit">{c.credit > 0 ? INR_FULL(c.credit) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* MERCHANTS TAB */}
          {dashTab === "merchants" && (
            <div className="banking-detail-grid" data-testid="merchants-view">
              <div className="banking-chart-card wide">
                <h3>Top 15 Merchants by Spending</h3>
                <ResponsiveContainer width="100%" height={500}>
                  <BarChart data={merchants.filter(m => m.debit > 0).slice(0, 15)} layout="vertical"
                    margin={{ top: 5, right: 30, left: 140, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis type="number" tick={{ fill: "#94a3b8", fontSize: 11 }} tickFormatter={v => INR(v)} />
                    <YAxis type="category" dataKey="merchant" tick={{ fill: "#e2e8f0", fontSize: 11 }} width={130} />
                    <Tooltip formatter={v => INR_FULL(v)}
                      contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, color: "#e2e8f0" }} />
                    <Bar dataKey="debit" name="Total Spent" fill="#8b5cf6" radius={[0, 4, 4, 0]}>
                      {merchants.filter(m => m.debit > 0).slice(0, 15).map((m, i) => (
                        <Cell key={i} fill={CATEGORY_COLORS[m.category] || "#8b5cf6"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="banking-cat-table" data-testid="merchant-table">
                <table>
                  <thead>
                    <tr><th>Merchant</th><th>Category</th><th>Txns</th><th>Debits</th><th>Credits</th></tr>
                  </thead>
                  <tbody>
                    {merchants.map(m => (
                      <tr key={m.merchant} className="banking-clickable"
                        onClick={() => handleFilterMerchant(m.merchant)} data-testid={`merchant-row-${m.merchant}`}>
                        <td>{m.merchant}</td>
                        <td><span className="banking-cat-badge" style={{ background: (CATEGORY_COLORS[m.category] || "#64748b") + "22", color: CATEGORY_COLORS[m.category] || "#64748b" }}>{m.category}</span></td>
                        <td>{m.count}</td>
                        <td className="banking-amt-debit">{m.debit > 0 ? INR_FULL(m.debit) : "—"}</td>
                        <td className="banking-amt-credit">{m.credit > 0 ? INR_FULL(m.credit) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TRENDS TAB */}
          {dashTab === "trends" && (
            <div className="banking-charts">
              <div className="banking-chart-card wide" data-testid="balance-trend">
                <h3>Daily Balance Trend</h3>
                <ResponsiveContainer width="100%" height={350}>
                  <AreaChart data={balanceTrend} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="balGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="date" tick={{ fill: "#94a3b8", fontSize: 10 }}
                      tickFormatter={v => { const d = new Date(v); return `${d.getDate()}/${d.getMonth()+1}`; }}
                      interval={Math.floor(balanceTrend.length / 15)} />
                    <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} tickFormatter={v => INR(v)} />
                    <Tooltip formatter={v => INR_FULL(v)}
                      contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, color: "#e2e8f0" }} />
                    <Area type="monotone" dataKey="balance" stroke="#3b82f6" fill="url(#balGrad)" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              <div className="banking-chart-card" data-testid="monthly-net">
                <h3>Monthly Net Cash Flow</h3>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={monthly.map(m => ({ ...m, net: m.credit - m.debit }))}
                    margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="month" tick={{ fill: "#94a3b8", fontSize: 12 }}
                      tickFormatter={v => { const [y, m] = v.split("-"); return ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][parseInt(m)-1]; }} />
                    <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} tickFormatter={v => INR(v)} />
                    <Tooltip formatter={v => INR_FULL(v)}
                      contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, color: "#e2e8f0" }} />
                    <Bar dataKey="net" name="Net Flow" radius={[4, 4, 0, 0]}>
                      {monthly.map((m, i) => (
                        <Cell key={i} fill={m.credit - m.debit >= 0 ? "#22c55e" : "#ef4444"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ===== TRANSACTIONS VIEW ===== */}
      {view === "transactions" && activeStmt && (
        <div className="banking-txn-view" data-testid="transactions-view">
          {/* Filters */}
          <div className="banking-txn-toolbar">
            <div className="banking-txn-search">
              <Search size={14} />
              <input placeholder="Search transactions..." value={filters.search}
                onChange={e => { setFilters(f => ({ ...f, search: e.target.value })); setTxnPage(0); }}
                data-testid="txn-search" />
            </div>
            <button className="banking-btn banking-btn-sm" onClick={() => setShowFilters(!showFilters)}
              data-testid="toggle-filters">
              <Filter size={14} /> Filters {showFilters ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>
            <span className="banking-txn-count">{txnTotal} transactions</span>
            {(filters.category || filters.merchant || filters.txn_type || filters.debit_only || filters.credit_only) && (
              <button className="banking-btn banking-btn-sm banking-btn-danger"
                onClick={() => { setFilters({ category: "", merchant: "", txn_type: "", date_from: "", date_to: "", debit_only: false, credit_only: false, search: "" }); setTxnPage(0); }}
                data-testid="clear-filters">
                <X size={12} /> Clear
              </button>
            )}
          </div>

          {showFilters && (
            <div className="banking-filter-grid" data-testid="filter-grid">
              <div className="banking-filter-item">
                <label>Category</label>
                <select value={filters.category} onChange={e => { setFilters(f => ({ ...f, category: e.target.value })); setTxnPage(0); }}
                  className="banking-select" data-testid="filter-category">
                  <option value="">All Categories</option>
                  {categories.map(c => <option key={c.category} value={c.category}>{c.category} ({c.count})</option>)}
                </select>
              </div>
              <div className="banking-filter-item">
                <label>Txn Type</label>
                <select value={filters.txn_type} onChange={e => { setFilters(f => ({ ...f, txn_type: e.target.value })); setTxnPage(0); }}
                  className="banking-select" data-testid="filter-txn-type">
                  <option value="">All Types</option>
                  {txnTypes.map(t => <option key={t.type} value={t.type}>{t.type} ({t.count})</option>)}
                </select>
              </div>
              <div className="banking-filter-item">
                <label>From</label>
                <input type="date" className="banking-input-sm" value={filters.date_from}
                  onChange={e => { setFilters(f => ({ ...f, date_from: e.target.value })); setTxnPage(0); }}
                  data-testid="filter-date-from" />
              </div>
              <div className="banking-filter-item">
                <label>To</label>
                <input type="date" className="banking-input-sm" value={filters.date_to}
                  onChange={e => { setFilters(f => ({ ...f, date_to: e.target.value })); setTxnPage(0); }}
                  data-testid="filter-date-to" />
              </div>
              <div className="banking-filter-item banking-filter-toggles">
                <label>
                  <input type="checkbox" checked={filters.debit_only}
                    onChange={e => { setFilters(f => ({ ...f, debit_only: e.target.checked, credit_only: false })); setTxnPage(0); }} />
                  Debits Only
                </label>
                <label>
                  <input type="checkbox" checked={filters.credit_only}
                    onChange={e => { setFilters(f => ({ ...f, credit_only: e.target.checked, debit_only: false })); setTxnPage(0); }} />
                  Credits Only
                </label>
              </div>
            </div>
          )}

          {/* Active filter badges */}
          {(filters.category || filters.merchant) && (
            <div className="banking-active-filters">
              {filters.category && (
                <span className="banking-filter-badge">
                  Category: {filters.category}
                  <button onClick={() => setFilters(f => ({ ...f, category: "" }))}><X size={10} /></button>
                </span>
              )}
              {filters.merchant && (
                <span className="banking-filter-badge">
                  Merchant: {filters.merchant}
                  <button onClick={() => setFilters(f => ({ ...f, merchant: "" }))}><X size={10} /></button>
                </span>
              )}
            </div>
          )}

          {/* Transactions Table */}
          {loading ? (
            <div className="banking-loading"><Loader2 size={24} className="spin" /> Loading...</div>
          ) : (
            <div className="banking-txn-table-wrap" data-testid="txn-table">
              <table className="banking-txn-table">
                <thead>
                  <tr>
                    <th className="banking-clickable" onClick={() => { setSortField("date"); setSortDir(d => d * -1); }}>
                      Date <ArrowUpDown size={10} />
                    </th>
                    <th>Particulars</th>
                    <th>Merchant</th>
                    <th>Category</th>
                    <th className="banking-clickable" onClick={() => { setSortField("debit"); setSortDir(d => d * -1); }}>
                      Debit <ArrowUpDown size={10} />
                    </th>
                    <th className="banking-clickable" onClick={() => { setSortField("credit"); setSortDir(d => d * -1); }}>
                      Credit <ArrowUpDown size={10} />
                    </th>
                    <th>Balance</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((t, i) => (
                    <tr key={t._id || i} data-testid={`txn-row-${i}`}>
                      <td className="banking-txn-date">{t.date}</td>
                      <td className="banking-txn-part" title={t.particulars}>
                        {t.particulars.length > 60 ? t.particulars.substring(0, 60) + "..." : t.particulars}
                      </td>
                      <td className="banking-txn-merchant banking-clickable"
                        onClick={() => handleFilterMerchant(t.merchant)}>{t.merchant}</td>
                      <td>
                        <span className="banking-cat-badge" onClick={() => handleFilterCategory(t.category)}
                          style={{ background: (CATEGORY_COLORS[t.category] || "#64748b") + "22", color: CATEGORY_COLORS[t.category] || "#64748b", cursor: "pointer" }}>
                          {t.category}
                        </span>
                      </td>
                      <td className="banking-amt-debit">{t.debit > 0 ? INR_FULL(t.debit) : ""}</td>
                      <td className="banking-amt-credit">{t.credit > 0 ? INR_FULL(t.credit) : ""}</td>
                      <td className="banking-txn-bal">{INR_FULL(t.balance)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          <div className="banking-pagination">
            <button className="banking-btn banking-btn-sm" disabled={txnPage === 0}
              onClick={() => setTxnPage(p => p - 1)}>Prev</button>
            <span>Page {txnPage + 1} of {Math.ceil(txnTotal / 100) || 1}</span>
            <button className="banking-btn banking-btn-sm" disabled={(txnPage + 1) * 100 >= txnTotal}
              onClick={() => setTxnPage(p => p + 1)}>Next</button>
          </div>
        </div>
      )}

      {loading && view !== "transactions" && (
        <div className="banking-loading"><Loader2 size={24} className="spin" /> Loading dashboard...</div>
      )}
    </div>
  );
};

export default BankingAgent;
