import { useState, useEffect, createContext, useContext, useCallback, useRef } from "react";
import "@/App.css";
import axios from "axios";
import { FileText, Upload, Download, Trash2, LogOut, Menu, X, CheckCircle, AlertCircle, Loader2, Receipt, RefreshCw, Mail, Copy, ExternalLink, Calendar, TrendingUp, Bell, DollarSign, Target, Plus, Search, ArrowUp, ArrowDown, Linkedin } from "lucide-react";
import LinkedInAgent from "./components/LinkedInAgent";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Configure axios defaults
axios.defaults.withCredentials = true;

// ============== Auth Context ==============
const AuthContext = createContext(null);

const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
};

const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const checkAuth = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/auth/me`);
      setUser(response.data);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const login = async (email, password) => {
    const response = await axios.post(`${API}/auth/login`, { email, password });
    setUser(response.data);
    return response.data;
  };

  const logout = async () => {
    await axios.post(`${API}/auth/logout`);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, checkAuth }}>
      {children}
    </AuthContext.Provider>
  );
};

// ============== Helper Functions ==============
const formatApiError = (error) => {
  const detail = error.response?.data?.detail;
  if (!detail) return error.message || "Something went wrong";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map(e => e?.msg || JSON.stringify(e)).join(" ");
  }
  return String(detail);
};

// ============== Login Page ==============
const LoginPage = () => {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container" data-testid="login-page">
      <div className="login-card">
        <div className="login-header">
          <div className="login-icon">
            <Receipt size={32} />
          </div>
          <h1>Agent Builder</h1>
          <p>Personal Assistant Agents Platform</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          {error && (
            <div className="error-message" data-testid="login-error">
              <AlertCircle size={16} />
              {error}
            </div>
          )}

          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Enter your email"
              required
              data-testid="login-email-input"
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              required
              data-testid="login-password-input"
            />
          </div>

          <button
            type="submit"
            className="login-btn"
            disabled={loading}
            data-testid="login-submit-btn"
          >
            {loading ? <Loader2 className="spin" size={20} /> : "Sign In"}
          </button>
        </form>
      </div>
    </div>
  );
};

// ============== Dashboard ==============
const Dashboard = () => {
  const { user, logout } = useAuth();
  const [activeAgent, setActiveAgent] = useState("invoicing");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [invoices, setInvoices] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [loadingInvoices, setLoadingInvoices] = useState(true);
  const [dateFilter, setDateFilter] = useState("all");
  const fileInputRef = useRef(null);
  
  // Refund Agent state
  const [gmailConnected, setGmailConnected] = useState(false);
  const [transactions, setTransactions] = useState([]);
  const [selectedTransaction, setSelectedTransaction] = useState(null);
  const [refundRequest, setRefundRequest] = useState("");
  const [generatingRefund, setGeneratingRefund] = useState(false);
  const [transactionInput, setTransactionInput] = useState("");
  const [refundHistory, setRefundHistory] = useState([]);

  // Stock Agent state
  const [stocks, setStocks] = useState([]);
  const [stockAlerts, setStockAlerts] = useState([]);
  const [portfolio, setPortfolio] = useState([]);
  const [loadingStocks, setLoadingStocks] = useState(false);
  const [selectedStock, setSelectedStock] = useState(null);
  const [stockDetails, setStockDetails] = useState(null);
  const [showAddPosition, setShowAddPosition] = useState(false);
  const [newPosition, setNewPosition] = useState({ symbol: "", buy_price: "", quantity: "", target_pct: "30" });

  const agents = [
    { id: "invoicing", name: "Invoicing Agent", icon: Receipt },
    { id: "refund", name: "Refund Agent", icon: RefreshCw },
    { id: "stocks", name: "Stock Investor", icon: TrendingUp },
    { id: "linkedin", name: "LinkedIn Agent", icon: Linkedin }
  ];

  const fetchInvoices = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/invoices`);
      setInvoices(response.data.invoices || []);
    } catch (err) {
      console.error("Error fetching invoices:", err);
    } finally {
      setLoadingInvoices(false);
    }
  }, []);

  // Filter invoices by date
  const filteredInvoices = invoices.filter(invoice => {
    if (dateFilter === "all") return true;
    const invoiceDate = new Date(invoice.upload_date);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    if (dateFilter === "today") {
      const invoiceDateOnly = new Date(invoiceDate);
      invoiceDateOnly.setHours(0, 0, 0, 0);
      return invoiceDateOnly.getTime() === today.getTime();
    }
    if (dateFilter === "week") {
      const weekAgo = new Date(today);
      weekAgo.setDate(weekAgo.getDate() - 7);
      return invoiceDate >= weekAgo;
    }
    if (dateFilter === "month") {
      const monthAgo = new Date(today);
      monthAgo.setMonth(monthAgo.getMonth() - 1);
      return invoiceDate >= monthAgo;
    }
    return true;
  });

  // Group invoices by date
  const groupedInvoices = filteredInvoices.reduce((groups, invoice) => {
    const date = new Date(invoice.upload_date).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
    if (!groups[date]) {
      groups[date] = [];
    }
    groups[date].push(invoice);
    return groups;
  }, {});

  useEffect(() => {
    fetchInvoices();
  }, [fetchInvoices]);

  // Fetch stocks data when stocks tab is active
  const fetchStocks = useCallback(async () => {
    setLoadingStocks(true);
    try {
      const response = await axios.get(`${API}/stocks/scanner`);
      setStocks(response.data.stocks || []);
    } catch (err) {
      console.error("Error fetching stocks:", err);
    } finally {
      setLoadingStocks(false);
    }
  }, []);

  const fetchPortfolio = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/stocks/portfolio`);
      setPortfolio(response.data.portfolio || []);
      setStockAlerts(response.data.alerts || []);
    } catch (err) {
      console.error("Error fetching portfolio:", err);
    }
  }, []);

  const fetchStockDetails = async (symbol) => {
    try {
      const response = await axios.get(`${API}/stocks/${symbol}/details`);
      setStockDetails(response.data);
      setSelectedStock(symbol);
    } catch (err) {
      alert("Failed to fetch stock details");
    }
  };

  const addToPortfolio = async () => {
    if (!newPosition.symbol || !newPosition.buy_price || !newPosition.quantity) {
      alert("Please fill all fields");
      return;
    }
    try {
      await axios.post(`${API}/stocks/portfolio/add`, {
        symbol: newPosition.symbol,
        buy_price: parseFloat(newPosition.buy_price),
        quantity: parseInt(newPosition.quantity),
        target_pct: parseFloat(newPosition.target_pct)
      });
      setNewPosition({ symbol: "", buy_price: "", quantity: "", target_pct: "30" });
      setShowAddPosition(false);
      fetchPortfolio();
    } catch (err) {
      alert("Failed to add position");
    }
  };

  const sellPosition = async (entryId, currentPrice) => {
    const sellPrice = prompt("Enter sell price:", currentPrice);
    if (!sellPrice) return;
    try {
      await axios.post(`${API}/stocks/portfolio/${entryId}/sell?sell_price=${parseFloat(sellPrice)}`);
      fetchPortfolio();
    } catch (err) {
      alert("Failed to sell position");
    }
  };

  const deletePosition = async (entryId) => {
    if (!window.confirm("Delete this position?")) return;
    try {
      await axios.delete(`${API}/stocks/portfolio/${entryId}`);
      fetchPortfolio();
    } catch (err) {
      alert("Failed to delete");
    }
  };

  useEffect(() => {
    if (activeAgent === "stocks") {
      fetchStocks();
      fetchPortfolio();
    }
  }, [activeAgent, fetchStocks, fetchPortfolio]);

  const handleFileUpload = async (e) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setUploading(true);
    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
      formData.append("files", files[i]);
    }

    try {
      await axios.post(`${API}/invoices/upload`, formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      await fetchInvoices();
    } catch (err) {
      console.error("Upload error:", err);
      alert(formatApiError(err));
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const handleDownloadOriginal = async (invoice) => {
    try {
      const response = await axios.get(`${API}/invoices/${invoice.id}/original`, {
        responseType: "blob",
        withCredentials: true
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.download = invoice.original_filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert(formatApiError(err));
    }
  };

  const handleDownloadEdited = async (invoice) => {
    try {
      const response = await axios.get(`${API}/invoices/${invoice.id}/edited`, {
        responseType: "blob",
        withCredentials: true
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.download = invoice.original_filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert(formatApiError(err));
    }
  };

  const handleDownloadAll = async () => {
    try {
      const response = await axios.get(`${API}/invoices/download-all?filter=${dateFilter}`, {
        responseType: "blob",
        withCredentials: true
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      const filterLabel = dateFilter === "all" ? "" : `_${dateFilter}`;
      link.download = `invoices${filterLabel}_${new Date().toISOString().split("T")[0]}.zip`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert(formatApiError(err));
    }
  };

  const handleDelete = async (invoice) => {
    if (!window.confirm(`Delete "${invoice.original_filename}"?`)) return;
    try {
      await axios.delete(`${API}/invoices/${invoice.id}`);
      await fetchInvoices();
    } catch (err) {
      alert(formatApiError(err));
    }
  };

  const handleLogout = async () => {
    try {
      await logout();
    } catch (err) {
      console.error("Logout error:", err);
    }
  };

  return (
    <div className="dashboard" data-testid="dashboard">
      {/* Sidebar */}
      <aside className={`sidebar ${sidebarOpen ? "open" : "closed"}`} data-testid="sidebar">
        <div className="sidebar-header">
          <div className="logo">
            <Receipt size={24} />
            {sidebarOpen && <span>Agent Builder</span>}
          </div>
          <button
            className="sidebar-toggle"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            data-testid="sidebar-toggle"
          >
            {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-section">
            {sidebarOpen && <span className="nav-label">Agents</span>}
            {agents.map((agent) => (
              <button
                key={agent.id}
                className={`nav-item ${activeAgent === agent.id ? "active" : ""}`}
                onClick={() => setActiveAgent(agent.id)}
                data-testid={`nav-${agent.id}`}
              >
                <agent.icon size={20} />
                {sidebarOpen && <span>{agent.name}</span>}
              </button>
            ))}
          </div>
        </nav>

        <div className="sidebar-footer">
          <div className="user-info">
            <div className="avatar">{user?.name?.[0] || "U"}</div>
            {sidebarOpen && (
              <div className="user-details">
                <span className="user-name">{user?.name}</span>
                <span className="user-email">{user?.email}</span>
              </div>
            )}
          </div>
          <button className="logout-btn" onClick={handleLogout} data-testid="logout-btn">
            <LogOut size={18} />
            {sidebarOpen && <span>Logout</span>}
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        {activeAgent === "invoicing" && (
          <div className="invoicing-agent" data-testid="invoicing-agent">
            <header className="content-header">
              <div>
                <h1>Invoicing Agent</h1>
                <p>Upload Google invoices to process and edit them automatically</p>
              </div>
              {filteredInvoices.length > 0 && (
                <button
                  className="download-all-btn"
                  onClick={handleDownloadAll}
                  data-testid="download-all-btn"
                >
                  <Download size={18} />
                  Download {dateFilter === "all" ? "All" : filteredInvoices.length} Edited
                </button>
              )}
            </header>

            {/* Upload Area */}
            <div className="upload-section">
              <div 
                className="upload-area" 
                data-testid="upload-area"
                onClick={() => fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf"
                  multiple
                  onChange={handleFileUpload}
                  disabled={uploading}
                  data-testid="file-input"
                  style={{ display: 'none' }}
                />
                {uploading ? (
                  <div className="upload-content">
                    <Loader2 className="spin" size={48} />
                    <span>Processing invoices...</span>
                  </div>
                ) : (
                  <div className="upload-content">
                    <Upload size={48} />
                    <span>Drop PDF invoices here or click to upload</span>
                    <small>Multiple files supported</small>
                  </div>
                )}
              </div>
            </div>

            {/* Invoice List */}
            <div className="invoice-section">
              <div className="invoice-header">
                <h2>
                  <FileText size={20} />
                  Invoices ({filteredInvoices.length}{dateFilter !== "all" ? ` of ${invoices.length}` : ""})
                </h2>
                <div className="filter-tabs" data-testid="date-filter">
                  <button 
                    className={`filter-tab ${dateFilter === "all" ? "active" : ""}`}
                    onClick={() => setDateFilter("all")}
                  >
                    All
                  </button>
                  <button 
                    className={`filter-tab ${dateFilter === "today" ? "active" : ""}`}
                    onClick={() => setDateFilter("today")}
                  >
                    Today
                  </button>
                  <button 
                    className={`filter-tab ${dateFilter === "week" ? "active" : ""}`}
                    onClick={() => setDateFilter("week")}
                  >
                    This Week
                  </button>
                  <button 
                    className={`filter-tab ${dateFilter === "month" ? "active" : ""}`}
                    onClick={() => setDateFilter("month")}
                  >
                    This Month
                  </button>
                </div>
              </div>

              {loadingInvoices ? (
                <div className="loading-state">
                  <Loader2 className="spin" size={32} />
                  <span>Loading invoices...</span>
                </div>
              ) : filteredInvoices.length === 0 ? (
                <div className="empty-state" data-testid="empty-state">
                  <FileText size={64} />
                  <p>{invoices.length === 0 ? "No invoices uploaded yet" : "No invoices match this filter"}</p>
                  <span>{invoices.length === 0 ? "Upload your Google invoices to get started" : "Try a different date range"}</span>
                </div>
              ) : (
                <div className="invoice-list" data-testid="invoice-list">
                  {Object.entries(groupedInvoices).map(([date, dateInvoices]) => (
                    <div key={date} className="invoice-group">
                      <div className="date-header">
                        <span>{date}</span>
                        <span className="date-count">{dateInvoices.length} invoice{dateInvoices.length > 1 ? 's' : ''}</span>
                      </div>
                      {dateInvoices.map((invoice) => (
                    <div key={invoice.id} className="invoice-card" data-testid={`invoice-${invoice.id}`}>
                      <div className="invoice-info">
                        <FileText size={24} />
                        <div className="invoice-details">
                          <span className="invoice-name">{invoice.original_filename}</span>
                          <span className="invoice-date">
                            {new Date(invoice.upload_date).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                          </span>
                        </div>
                        <span className={`invoice-status ${invoice.status}`}>
                          {invoice.status === "processed" ? (
                            <><CheckCircle size={14} /> Processed</>
                          ) : (
                            <><AlertCircle size={14} /> Failed</>
                          )}
                        </span>
                      </div>
                      <div className="invoice-actions">
                        <button
                          className="action-btn original"
                          onClick={() => handleDownloadOriginal(invoice)}
                          title="Download Original"
                          data-testid={`download-original-${invoice.id}`}
                        >
                          <Download size={16} />
                          Original
                        </button>
                        {invoice.status === "processed" && (
                          <button
                            className="action-btn edited"
                            onClick={() => handleDownloadEdited(invoice)}
                            title="Download Edited"
                            data-testid={`download-edited-${invoice.id}`}
                          >
                            <Download size={16} />
                            Edited
                          </button>
                        )}
                        <button
                          className="action-btn delete"
                          onClick={() => handleDelete(invoice)}
                          title="Delete"
                          data-testid={`delete-${invoice.id}`}
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </div>
                      ))}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Refund Agent */}
        {activeAgent === "refund" && (
          <div className="refund-agent" data-testid="refund-agent">
            <header className="content-header">
              <div>
                <h1>Refund Agent</h1>
                <p>Generate compelling refund requests for failed Google Play transactions</p>
              </div>
            </header>

            {/* Gmail Connection Status */}
            <div className="gmail-section">
              <div className="gmail-status">
                <Mail size={24} />
                <div className="gmail-info">
                  <span className="gmail-title">Gmail Connection</span>
                  <span className="gmail-subtitle">
                    {gmailConnected ? "Connected - Ready to fetch receipts" : "Connect to auto-fetch Google Play receipts"}
                  </span>
                </div>
                <button 
                  className={`gmail-btn ${gmailConnected ? "connected" : ""}`}
                  onClick={() => {
                    if (!gmailConnected) {
                      alert("Gmail integration requires OAuth setup. For now, paste transaction details manually below.");
                    }
                  }}
                  data-testid="gmail-connect-btn"
                >
                  {gmailConnected ? (
                    <><CheckCircle size={16} /> Connected</>
                  ) : (
                    <><Mail size={16} /> Connect Gmail</>
                  )}
                </button>
              </div>
            </div>

            {/* Transaction Input */}
            <div className="transaction-input-section">
              <h2>
                <FileText size={20} />
                Paste Transaction Details
              </h2>
              <p className="section-desc">Copy transaction details from Google Play and paste below</p>
              <textarea
                className="transaction-textarea"
                placeholder="Paste transaction details here...&#10;&#10;Example:&#10;Order ID: GPA.1234-5678-9012&#10;Date: March 30, 2026&#10;Item: Game Currency Pack&#10;Amount: ₹990.00&#10;What went wrong: Payment was charged but items were never received in the game"
                value={transactionInput}
                onChange={(e) => setTransactionInput(e.target.value)}
                data-testid="transaction-input"
              />
              <button
                className="generate-btn"
                onClick={async () => {
                  if (!transactionInput.trim()) {
                    alert("Please paste transaction details first");
                    return;
                  }
                  setGeneratingRefund(true);
                  try {
                    const response = await axios.post(`${API}/refund/generate`, {
                      transaction_details: transactionInput
                    });
                    setRefundRequest(response.data.refund_request);
                    setSelectedTransaction({
                      details: transactionInput,
                      generated_at: new Date().toISOString()
                    });
                  } catch (err) {
                    alert("Failed to generate refund request");
                  } finally {
                    setGeneratingRefund(false);
                  }
                }}
                disabled={generatingRefund || !transactionInput.trim()}
                data-testid="generate-refund-btn"
              >
                {generatingRefund ? (
                  <><Loader2 className="spin" size={18} /> Generating...</>
                ) : (
                  <><RefreshCw size={18} /> Generate Refund Request</>
                )}
              </button>
            </div>

            {/* Generated Refund Request */}
            {refundRequest && (
              <div className="refund-output-section">
                <h2>
                  <CheckCircle size={20} />
                  Your Refund Request
                </h2>
                <div className="refund-output">
                  <pre>{refundRequest}</pre>
                </div>
                <div className="refund-actions">
                  <button
                    className="action-btn copy"
                    onClick={() => {
                      navigator.clipboard.writeText(refundRequest);
                      alert("Copied to clipboard!");
                    }}
                    data-testid="copy-refund-btn"
                  >
                    <Copy size={16} />
                    Copy to Clipboard
                  </button>
                  <a
                    href="https://play.google.com/store/account/orderhistory"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="action-btn submit-link"
                    data-testid="submit-refund-link"
                  >
                    <ExternalLink size={16} />
                    Open Google Play Refunds
                  </a>
                </div>
              </div>
            )}

            {/* Refund History */}
            {refundHistory.length > 0 && (
              <div className="refund-history-section">
                <h2>
                  <Calendar size={20} />
                  Recent Refund Requests ({refundHistory.length})
                </h2>
                <div className="history-list">
                  {refundHistory.map((item, index) => (
                    <div key={index} className="history-item">
                      <span className="history-date">{new Date(item.created_at).toLocaleDateString()}</span>
                      <span className="history-preview">{item.details.substring(0, 50)}...</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Stock Investor Agent */}
        {activeAgent === "stocks" && (
          <div className="stock-agent" data-testid="stock-agent">
            <header className="content-header">
              <div>
                <h1>Stock Investor Agent</h1>
                <p>Track high-volume undervalued NSE stocks with buy/sell alerts</p>
              </div>
              <button className="refresh-btn" onClick={() => { fetchStocks(); fetchPortfolio(); }} disabled={loadingStocks}>
                <RefreshCw size={18} className={loadingStocks ? "spin" : ""} />
                Refresh Data
              </button>
            </header>

            {/* Alerts Section */}
            {stockAlerts.length > 0 && (
              <div className="alerts-section">
                <h2><Bell size={20} /> Active Alerts</h2>
                {stockAlerts.map((alert, idx) => (
                  <div key={idx} className={`alert-card ${alert.type}`}>
                    <Target size={20} />
                    <span>{alert.message}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Portfolio Section */}
            <div className="portfolio-section">
              <div className="section-header">
                <h2><DollarSign size={20} /> Your Portfolio</h2>
                <button className="add-btn" onClick={() => setShowAddPosition(true)}>
                  <Plus size={16} /> Add Position
                </button>
              </div>

              {showAddPosition && (
                <div className="add-position-form">
                  <input 
                    placeholder="Symbol (e.g., RELIANCE)" 
                    value={newPosition.symbol}
                    onChange={(e) => setNewPosition({...newPosition, symbol: e.target.value.toUpperCase()})}
                  />
                  <input 
                    placeholder="Buy Price" 
                    type="number"
                    value={newPosition.buy_price}
                    onChange={(e) => setNewPosition({...newPosition, buy_price: e.target.value})}
                  />
                  <input 
                    placeholder="Quantity" 
                    type="number"
                    value={newPosition.quantity}
                    onChange={(e) => setNewPosition({...newPosition, quantity: e.target.value})}
                  />
                  <input 
                    placeholder="Target %" 
                    type="number"
                    value={newPosition.target_pct}
                    onChange={(e) => setNewPosition({...newPosition, target_pct: e.target.value})}
                  />
                  <button className="save-btn" onClick={addToPortfolio}>Add</button>
                  <button className="cancel-btn" onClick={() => setShowAddPosition(false)}>Cancel</button>
                </div>
              )}

              {portfolio.length === 0 ? (
                <div className="empty-portfolio">
                  <DollarSign size={48} />
                  <p>No positions yet. Add stocks to track.</p>
                </div>
              ) : (
                <div className="portfolio-list">
                  {portfolio.filter(p => p.status === "holding").map((pos) => (
                    <div key={pos.id} className="portfolio-card">
                      <div className="portfolio-info">
                        <span className="portfolio-symbol">{pos.symbol}</span>
                        <span className="portfolio-qty">{pos.quantity} shares</span>
                      </div>
                      <div className="portfolio-prices">
                        <div className="price-row">
                          <span className="label">Buy:</span>
                          <span>₹{pos.buy_price}</span>
                        </div>
                        <div className="price-row">
                          <span className="label">Current:</span>
                          <span>₹{pos.current_price || "..."}</span>
                        </div>
                        <div className="price-row">
                          <span className="label">Target:</span>
                          <span>₹{pos.target_price}</span>
                        </div>
                      </div>
                      <div className={`portfolio-pnl ${(pos.profit_loss_pct || 0) >= 0 ? "profit" : "loss"}`}>
                        {(pos.profit_loss_pct || 0) >= 0 ? <ArrowUp size={16} /> : <ArrowDown size={16} />}
                        {pos.profit_loss_pct?.toFixed(1) || 0}%
                      </div>
                      <div className="portfolio-actions">
                        <button className="sell-btn" onClick={() => sellPosition(pos.id, pos.current_price)}>Sell</button>
                        <button className="delete-btn" onClick={() => deletePosition(pos.id)}><Trash2 size={14} /></button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Stock Scanner Section */}
            <div className="scanner-section">
              <h2><Search size={20} /> Top Volume Movers (Under ₹100)</h2>
              <p className="criteria-info">
                NSE stocks under ₹100 sorted by shares traded today | Top 50 | Highlights: Price &lt; 60% of 52W high
              </p>

              {loadingStocks ? (
                <div className="loading-state">
                  <Loader2 className="spin" size={32} />
                  <span>Scanning stocks...</span>
                </div>
              ) : (
                <div className="stock-list">
                  <div className="stock-header">
                    <span>Symbol</span>
                    <span>Price</span>
                    <span>Today's Volume</span>
                    <span>7D Avg Vol</span>
                    <span>% of 52W</span>
                    <span>Status</span>
                  </div>
                  {stocks.map((stock) => (
                    <div 
                      key={stock.symbol} 
                      className={`stock-row ${stock.meets_criteria ? "highlight" : ""}`}
                      onClick={() => fetchStockDetails(stock.symbol)}
                    >
                      <span className="stock-symbol">{stock.symbol}</span>
                      <span>₹{stock.current_price}</span>
                      <span className={stock.high_volume_day ? "high-volume" : ""}>
                        {stock.today_volume_formatted}
                      </span>
                      <span>{stock.avg_volume_7d_formatted}</span>
                      <span className={stock.price_vs_52w_pct < 60 ? "undervalued" : ""}>
                        {stock.price_vs_52w_pct}%
                      </span>
                      <span>
                        {stock.meets_criteria && stock.high_volume_day && (
                          <span className="buy-signal">BUY SIGNAL</span>
                        )}
                        {stock.high_volume_day && !stock.meets_criteria && (
                          <span className="watch">HIGH VOL</span>
                        )}
                        {stock.meets_criteria && !stock.high_volume_day && (
                          <span className="undervalued-tag">UNDERVALUED</span>
                        )}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Stock Details Modal */}
            {stockDetails && (
              <div className="stock-modal" onClick={() => setStockDetails(null)}>
                <div className="stock-modal-content" onClick={(e) => e.stopPropagation()}>
                  <button className="close-modal" onClick={() => setStockDetails(null)}><X size={20} /></button>
                  <h2>{stockDetails.symbol} - {stockDetails.name}</h2>
                  <div className="stock-detail-grid">
                    <div className="detail-item">
                      <span className="label">Current Price</span>
                      <span className="value">₹{stockDetails.current_price}</span>
                    </div>
                    <div className="detail-item">
                      <span className="label">52W High</span>
                      <span className="value">₹{stockDetails.week_52_high}</span>
                    </div>
                    <div className="detail-item">
                      <span className="label">52W Low</span>
                      <span className="value">₹{stockDetails.week_52_low}</span>
                    </div>
                    <div className="detail-item">
                      <span className="label">% of 52W High</span>
                      <span className="value">{stockDetails.price_vs_52w_pct}%</span>
                    </div>
                    <div className="detail-item">
                      <span className="label">Sector</span>
                      <span className="value">{stockDetails.sector}</span>
                    </div>
                    <div className="detail-item">
                      <span className="label">P/E Ratio</span>
                      <span className="value">{stockDetails.pe_ratio?.toFixed(2) || "N/A"}</span>
                    </div>
                  </div>
                  
                  <h3>Recent News</h3>
                  <div className="news-list">
                    {stockDetails.news?.length > 0 ? stockDetails.news.map((n, i) => (
                      <a key={i} href={n.link} target="_blank" rel="noopener noreferrer" className="news-item">
                        <span className="news-title">{n.title}</span>
                        <span className="news-date">{n.date}</span>
                      </a>
                    )) : <p>No recent news found</p>}
                  </div>

                  <button 
                    className="add-to-portfolio-btn"
                    onClick={() => {
                      setNewPosition({...newPosition, symbol: stockDetails.symbol, buy_price: stockDetails.current_price.toString()});
                      setShowAddPosition(true);
                      setStockDetails(null);
                    }}
                  >
                    <Plus size={16} /> Add to Portfolio
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* LinkedIn Agent */}
        {activeAgent === "linkedin" && <LinkedInAgent />}
      </main>
    </div>
  );
};

// ============== Main App ==============
function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

const AppContent = () => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="loading-screen" data-testid="loading-screen">
        <Loader2 className="spin" size={48} />
        <span>Loading...</span>
      </div>
    );
  }

  return user ? <Dashboard /> : <LoginPage />;
};

export default App;
