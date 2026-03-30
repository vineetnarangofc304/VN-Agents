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
        responseType: "blob"
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.download = `original_${invoice.original_filename}`;
      link.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert(formatApiError(err));
    }
  };

  const handleDownloadEdited = async (invoice) => {
    try {
      const response = await axios.get(`${API}/invoices/${invoice.id}/edited`, {
        responseType: "blob"
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.download = `edited_${invoice.original_filename}`;
      link.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert(formatApiError(err));
    }
  };

  const handleDownloadAll = async () => {
    try {
      const response = await axios.get(`${API}/invoices/download-all`, {
        responseType: "blob"
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.download = `edited_invoices_${new Date().toISOString().split("T")[0]}.zip`;
      link.click();
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
              {invoices.length > 0 && (
                <button
                  className="download-all-btn"
                  onClick={handleDownloadAll}
                  data-testid="download-all-btn"
                >
                  <Download size={18} />
                  Download All Edited
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
              <h2>
                <FileText size={20} />
                Invoices ({invoices.length})
              </h2>

              {loadingInvoices ? (
                <div className="loading-state">
                  <Loader2 className="spin" size={32} />
                  <span>Loading invoices...</span>
                </div>
              ) : invoices.length === 0 ? (
                <div className="empty-state" data-testid="empty-state">
                  <FileText size={64} />
                  <p>No invoices uploaded yet</p>
                  <span>Upload your Google invoices to get started</span>
                </div>
              ) : (
                <div className="invoice-list" data-testid="invoice-list">
                  {invoices.map((invoice) => (
                    <div key={invoice.id} className="invoice-card" data-testid={`invoice-${invoice.id}`}>
                      <div className="invoice-info">
                        <FileText size={24} />
                        <div className="invoice-details">
                          <span className="invoice-name">{invoice.original_filename}</span>
                          <span className="invoice-date">
                            {new Date(invoice.upload_date).toLocaleDateString()}
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
