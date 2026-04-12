import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import { FileText, Upload, Download, Trash2, CheckCircle, AlertCircle, Loader2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const InvoicingAgent = () => {
  const [invoices, setInvoices] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [loadingInvoices, setLoadingInvoices] = useState(true);
  const [dateFilter, setDateFilter] = useState("all");
  const [authReady, setAuthReady] = useState(false);
  const fileInputRef = useRef(null);

  // Auto-login with JWT cookie on mount
  useEffect(() => {
    const ensureAuth = async () => {
      try {
        // Check if already authenticated
        const meRes = await axios.get(`${API}/auth/me`, { withCredentials: true });
        if (meRes.data?.id) {
          setAuthReady(true);
          return;
        }
      } catch {
        // Not authenticated, login
      }
      try {
        await axios.post(`${API}/auth/login`, {
          email: "vineetnarangofc@gmail.com",
          password: "InvoiceAgent@2024!"
        }, { withCredentials: true });
        setAuthReady(true);
      } catch (err) {
        console.error("JWT login failed:", err);
        setAuthReady(true); // Continue anyway, will show errors on API calls
      }
    };
    ensureAuth();
  }, []);

  const fetchInvoices = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/invoices`, { withCredentials: true });
      setInvoices(response.data.invoices || []);
    } catch (err) {
      console.error("Error fetching invoices:", err);
    } finally {
      setLoadingInvoices(false);
    }
  }, []);

  const filteredInvoices = invoices.filter(invoice => {
    if (dateFilter === "all") return true;
    const invoiceDate = new Date(invoice.upload_date);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    if (dateFilter === "today") {
      const d = new Date(invoiceDate);
      d.setHours(0, 0, 0, 0);
      return d.getTime() === today.getTime();
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

  const groupedInvoices = filteredInvoices.reduce((groups, invoice) => {
    const date = new Date(invoice.upload_date).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
    if (!groups[date]) groups[date] = [];
    groups[date].push(invoice);
    return groups;
  }, {});

  useEffect(() => { if (authReady) fetchInvoices(); }, [authReady, fetchInvoices]);

  const handleFileUpload = async (e) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setUploading(true);
    const formData = new FormData();
    for (let i = 0; i < files.length; i++) formData.append("files", files[i]);
    try {
      await axios.post(`${API}/invoices/upload`, formData, { headers: { "Content-Type": "multipart/form-data" }, withCredentials: true });
      await fetchInvoices();
    } catch (err) {
      alert(err.response?.data?.detail || "Upload failed");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const handleDownload = async (invoice, type) => {
    try {
      const response = await axios.get(`${API}/invoices/${invoice.id}/${type}`, { responseType: "blob", withCredentials: true });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.download = invoice.original_filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert("Download failed");
    }
  };

  const handleDownloadAll = async () => {
    try {
      const response = await axios.get(`${API}/invoices/download-all?filter=${dateFilter}`, { responseType: "blob", withCredentials: true });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.download = `invoices_${dateFilter}_${new Date().toISOString().split("T")[0]}.zip`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert("Download failed");
    }
  };

  const handleDelete = async (invoice) => {
    if (!window.confirm(`Delete "${invoice.original_filename}"?`)) return;
    try {
      await axios.delete(`${API}/invoices/${invoice.id}`, { withCredentials: true });
      await fetchInvoices();
    } catch (err) {
      alert("Delete failed");
    }
  };

  return (
    <div className="invoicing-agent" data-testid="invoicing-agent">
      <header className="content-header">
        <div>
          <h1>Invoicing Agent</h1>
          <p>Upload Google invoices to process and edit them automatically</p>
        </div>
        {filteredInvoices.length > 0 && (
          <button className="download-all-btn" onClick={handleDownloadAll} data-testid="download-all-btn">
            <Download size={18} />
            Download {dateFilter === "all" ? "All" : filteredInvoices.length} Edited
          </button>
        )}
      </header>

      <div className="upload-section">
        <div className="upload-area" data-testid="upload-area" onClick={() => fileInputRef.current?.click()}>
          <input ref={fileInputRef} type="file" accept=".pdf" multiple onChange={handleFileUpload} disabled={uploading} data-testid="file-input" style={{ display: 'none' }} />
          {uploading ? (
            <div className="upload-content"><Loader2 className="spin" size={48} /><span>Processing invoices...</span></div>
          ) : (
            <div className="upload-content"><Upload size={48} /><span>Drop PDF invoices here or click to upload</span><small>Multiple files supported</small></div>
          )}
        </div>
      </div>

      <div className="invoice-section">
        <div className="invoice-header">
          <h2><FileText size={20} /> Invoices ({filteredInvoices.length}{dateFilter !== "all" ? ` of ${invoices.length}` : ""})</h2>
          <div className="filter-tabs" data-testid="date-filter">
            {["all", "today", "week", "month"].map(f => (
              <button key={f} className={`filter-tab ${dateFilter === f ? "active" : ""}`} onClick={() => setDateFilter(f)}>
                {f === "all" ? "All" : f === "today" ? "Today" : f === "week" ? "This Week" : "This Month"}
              </button>
            ))}
          </div>
        </div>

        {loadingInvoices ? (
          <div className="loading-state"><Loader2 className="spin" size={32} /><span>Loading invoices...</span></div>
        ) : filteredInvoices.length === 0 ? (
          <div className="empty-state" data-testid="empty-state">
            <FileText size={64} />
            <p>{invoices.length === 0 ? "No invoices uploaded yet" : "No invoices match this filter"}</p>
          </div>
        ) : (
          <div className="invoice-list" data-testid="invoice-list">
            {Object.entries(groupedInvoices).map(([date, dateInvoices]) => (
              <div key={date} className="invoice-group">
                <div className="date-header"><span>{date}</span><span className="date-count">{dateInvoices.length} invoice{dateInvoices.length > 1 ? 's' : ''}</span></div>
                {dateInvoices.map((invoice) => (
                  <div key={invoice.id} className="invoice-card" data-testid={`invoice-${invoice.id}`}>
                    <div className="invoice-info">
                      <FileText size={24} />
                      <div className="invoice-details">
                        <span className="invoice-name">{invoice.original_filename}</span>
                        <span className="invoice-date">{new Date(invoice.upload_date).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
                      </div>
                      <span className={`invoice-status ${invoice.status}`}>
                        {invoice.status === "processed" ? <><CheckCircle size={14} /> Processed</> : <><AlertCircle size={14} /> Failed</>}
                      </span>
                    </div>
                    <div className="invoice-actions">
                      <button className="action-btn original" onClick={() => handleDownload(invoice, "original")} data-testid={`download-original-${invoice.id}`}><Download size={16} /> Original</button>
                      {invoice.status === "processed" && (
                        <button className="action-btn edited" onClick={() => handleDownload(invoice, "edited")} data-testid={`download-edited-${invoice.id}`}><Download size={16} /> Edited</button>
                      )}
                      <button className="action-btn delete" onClick={() => handleDelete(invoice)} data-testid={`delete-${invoice.id}`}><Trash2 size={16} /></button>
                    </div>
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default InvoicingAgent;
