import { useState, useEffect, createContext, useContext, useCallback, useRef } from "react";
import "@/App.css";
import axios from "axios";
import { FileText, Upload, Download, Trash2, LogOut, Menu, X, CheckCircle, AlertCircle, Loader2, Receipt } from "lucide-react";

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

  const agents = [
    { id: "invoicing", name: "Invoicing Agent", icon: Receipt }
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
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
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
