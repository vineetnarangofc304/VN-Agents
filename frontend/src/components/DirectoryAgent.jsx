import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import {
  Loader2, Download, Search, Upload, FileSpreadsheet,
  Building2, Phone, Mail, Globe, User, MapPin, ChevronDown, ChevronUp,
  CheckCircle, AlertCircle, FileText, ExternalLink
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const DirectoryAgent = () => {
  const [companies, setCompanies] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedRow, setExpandedRow] = useState(null);
  const [stats, setStats] = useState(null);
  const [statusMsg, setStatusMsg] = useState(null);
  const [uploading, setUploading] = useState(false);

  const PDF_URL = "https://customer-assets.emergentagent.com/job_agent-builder-133/artifacts/jsm5p6sy_G20_DIA_SUMMIT_2023_Exhibitor_Directory_v3.pdf";

  const fetchStats = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/directory/stats`);
      setStats(res.data);
      return res.data;
    } catch (err) {
      console.error("Stats error:", err);
      return null;
    }
  }, []);

  const fetchCompanies = useCallback(async (search = "") => {
    setLoading(true);
    try {
      const params = { per_page: 200 };
      if (search) params.search = search;
      const res = await axios.get(`${API}/directory/companies`, { params });
      setCompanies(res.data.companies || []);
      setTotal(res.data.total || 0);
    } catch (err) {
      console.error("Fetch error:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const init = async () => {
      const s = await fetchStats();
      if (s && s.extracted) {
        fetchCompanies();
      }
    };
    init();
  }, [fetchStats, fetchCompanies]);

  const handleExtract = async () => {
    setExtracting(true);
    setStatusMsg(null);
    try {
      const res = await axios.post(`${API}/directory/extract-from-url`, {
        pdf_url: PDF_URL
      });
      const jobId = res.data.job_id;
      setStatusMsg({ type: "success", text: "Extraction started... processing 129 pages" });

      // Poll for completion
      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await axios.get(`${API}/directory/extract-status/${jobId}`);
          const job = statusRes.data;
          if (job.status === "completed") {
            clearInterval(pollInterval);
            setStatusMsg({ type: "success", text: `Extracted ${job.count} companies!` });
            setExtracting(false);
            await fetchStats();
            await fetchCompanies();
          } else if (job.status === "failed") {
            clearInterval(pollInterval);
            setStatusMsg({ type: "error", text: job.error || "Extraction failed" });
            setExtracting(false);
          }
        } catch (pollErr) {
          console.error("Poll error:", pollErr);
        }
      }, 2000);

      // Safety timeout after 3 minutes
      setTimeout(() => {
        clearInterval(pollInterval);
        if (extracting) {
          setExtracting(false);
          setStatusMsg({ type: "error", text: "Extraction timed out. Try again." });
        }
      }, 180000);
    } catch (err) {
      const detail = err.response?.data?.detail || "Extraction failed";
      setStatusMsg({ type: "error", text: detail });
      setExtracting(false);
    }
  };

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setStatusMsg(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await axios.post(`${API}/directory/extract-upload`, formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      const jobId = res.data.job_id;
      setStatusMsg({ type: "success", text: `Upload complete. Processing ${file.name}...` });

      // Poll for completion
      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await axios.get(`${API}/directory/extract-status/${jobId}`);
          const job = statusRes.data;
          if (job.status === "completed") {
            clearInterval(pollInterval);
            setStatusMsg({ type: "success", text: `Extracted ${job.count} companies from ${file.name}` });
            setUploading(false);
            await fetchStats();
            await fetchCompanies();
          } else if (job.status === "failed") {
            clearInterval(pollInterval);
            setStatusMsg({ type: "error", text: job.error || "Extraction failed" });
            setUploading(false);
          }
        } catch (pollErr) {
          console.error("Poll error:", pollErr);
        }
      }, 2000);
    } catch (err) {
      const detail = err.response?.data?.detail || "Upload failed";
      setStatusMsg({ type: "error", text: detail });
      setUploading(false);
    } finally {
      e.target.value = "";
    }
  };

  const handleSearch = (e) => {
    const val = e.target.value;
    setSearchQuery(val);
    // Debounced search
    clearTimeout(window._dirSearchTimer);
    window._dirSearchTimer = setTimeout(() => fetchCompanies(val), 400);
  };

  const handleDownloadExcel = async () => {
    try {
      const params = searchQuery ? `?search=${encodeURIComponent(searchQuery)}` : "";
      const res = await axios.get(`${API}/directory/download-excel${params}`, {
        responseType: "blob"
      });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement("a");
      link.href = url;
      link.download = `G20_DIA_Exhibitors_${new Date().toISOString().split("T")[0]}.xlsx`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setStatusMsg({ type: "error", text: "Download failed" });
    }
  };

  const isExtracted = stats?.extracted;

  return (
    <div className="directory-agent" data-testid="directory-agent">
      <header className="content-header">
        <div>
          <h1>PDF Directory Extractor</h1>
          <p>Extract company details from PDF directories into a searchable table & Excel</p>
        </div>
        {isExtracted && (
          <button
            className="dir-download-btn"
            onClick={handleDownloadExcel}
            data-testid="download-excel-btn"
          >
            <FileSpreadsheet size={18} /> Download Excel
          </button>
        )}
      </header>

      {/* Status Message */}
      {statusMsg && (
        <div className={`li-status-msg ${statusMsg.type}`} data-testid="directory-status-msg">
          {statusMsg.type === "success" ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
          <span>{statusMsg.text}</span>
          <button className="li-dismiss" onClick={() => setStatusMsg(null)}>&times;</button>
        </div>
      )}

      {/* Extract Section */}
      {!isExtracted && (
        <div className="dir-extract-section" data-testid="extract-section">
          <div className="dir-extract-card">
            <FileText size={48} />
            <h2>Extract Company Data from PDF</h2>
            <p>Upload or process the G20 DIA Summit Exhibitor Directory to extract all company details</p>
            <div className="dir-extract-actions">
              <button
                className="dir-extract-btn"
                onClick={handleExtract}
                disabled={extracting}
                data-testid="extract-btn"
              >
                {extracting ? (
                  <><Loader2 className="spin" size={18} /> Extracting 125+ companies...</>
                ) : (
                  <><FileText size={18} /> Extract from G20 PDF</>
                )}
              </button>
              <span className="dir-or">or</span>
              <label className="dir-upload-btn" data-testid="upload-pdf-btn">
                <input type="file" accept=".pdf" onChange={handleUpload} hidden />
                {uploading ? (
                  <><Loader2 className="spin" size={16} /> Uploading...</>
                ) : (
                  <><Upload size={16} /> Upload PDF</>
                )}
              </label>
            </div>
          </div>
        </div>
      )}

      {/* Company Table */}
      {isExtracted && (
        <>
          {/* Search & Stats Bar */}
          <div className="dir-toolbar" data-testid="directory-toolbar">
            <div className="dir-search-box">
              <Search size={16} />
              <input
                type="text"
                placeholder="Search companies, contacts, emails..."
                value={searchQuery}
                onChange={handleSearch}
                data-testid="directory-search-input"
              />
            </div>
            <div className="dir-stats">
              <span className="dir-stat-badge">{total} companies</span>
              <button
                className="dir-re-extract-btn"
                onClick={handleExtract}
                disabled={extracting}
                title="Re-extract from PDF"
                data-testid="re-extract-btn"
              >
                {extracting ? <Loader2 className="spin" size={14} /> : <FileText size={14} />}
                Re-extract
              </button>
            </div>
          </div>

          {/* Table */}
          {loading ? (
            <div className="dir-loading">
              <Loader2 className="spin" size={32} />
              <span>Loading companies...</span>
            </div>
          ) : companies.length === 0 ? (
            <div className="dir-empty">
              <Search size={48} />
              <p>No companies match "{searchQuery}"</p>
            </div>
          ) : (
            <div className="dir-table-container" data-testid="companies-table">
              <table className="dir-table">
                <thead>
                  <tr>
                    <th className="dir-th-num">#</th>
                    <th className="dir-th-name">Company</th>
                    <th className="dir-th-contact">Contact Person</th>
                    <th className="dir-th-phone">Phone / Mobile</th>
                    <th className="dir-th-email">Email</th>
                    <th className="dir-th-website">Website</th>
                    <th className="dir-th-expand"></th>
                  </tr>
                </thead>
                <tbody>
                  {companies.map((company, idx) => (
                    <React.Fragment key={company.id}>
                      <tr
                        className={`dir-row ${expandedRow === company.id ? "expanded" : ""}`}
                        onClick={() => setExpandedRow(expandedRow === company.id ? null : company.id)}
                        data-testid={`company-row-${idx}`}
                      >
                        <td className="dir-cell-num">{idx + 1}</td>
                        <td className="dir-cell-name">
                          <span className="dir-company-name">{company.name}</span>
                          {company.designation && (
                            <span className="dir-designation">{company.designation}</span>
                          )}
                        </td>
                        <td className="dir-cell-contact">
                          <User size={13} />
                          {company.contact_person || "-"}
                        </td>
                        <td className="dir-cell-phone">
                          {company.mobile || company.phone || "-"}
                        </td>
                        <td className="dir-cell-email">
                          {company.email ? (
                            <a href={`mailto:${company.email}`} onClick={e => e.stopPropagation()}>
                              {company.email}
                            </a>
                          ) : "-"}
                        </td>
                        <td className="dir-cell-website">
                          {company.website ? (
                            <a href={company.website} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()}>
                              <Globe size={13} /> Visit
                            </a>
                          ) : "-"}
                        </td>
                        <td className="dir-cell-expand">
                          {expandedRow === company.id ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                        </td>
                      </tr>
                      {expandedRow === company.id && (
                        <tr className="dir-detail-row">
                          <td colSpan={7}>
                            <div className="dir-detail-content">
                              <div className="dir-detail-grid">
                                <div className="dir-detail-item">
                                  <MapPin size={14} />
                                  <div>
                                    <span className="dir-detail-label">Address</span>
                                    <span className="dir-detail-value">{company.address || "-"}</span>
                                  </div>
                                </div>
                                <div className="dir-detail-item">
                                  <Phone size={14} />
                                  <div>
                                    <span className="dir-detail-label">Phone</span>
                                    <span className="dir-detail-value">{company.phone || "-"}</span>
                                  </div>
                                </div>
                                <div className="dir-detail-item">
                                  <Phone size={14} />
                                  <div>
                                    <span className="dir-detail-label">Mobile</span>
                                    <span className="dir-detail-value">{company.mobile || "-"}</span>
                                  </div>
                                </div>
                                <div className="dir-detail-item">
                                  <Mail size={14} />
                                  <div>
                                    <span className="dir-detail-label">Email</span>
                                    <span className="dir-detail-value">{company.email || "-"}</span>
                                  </div>
                                </div>
                              </div>
                              {company.profile && (
                                <div className="dir-detail-profile">
                                  <span className="dir-detail-label">Company Profile</span>
                                  <p>{company.profile}</p>
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default DirectoryAgent;
