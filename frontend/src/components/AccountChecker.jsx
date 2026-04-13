import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import {
  Loader2, Play, Square, Download, CheckCircle, XCircle,
  AlertCircle, RefreshCw, FileSpreadsheet, Key, Mail, Shield, ExternalLink, Coins
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AccountChecker = () => {
  const [ranges, setRanges] = useState([]);
  const [totalEmails, setTotalEmails] = useState(0);
  const [scanStatus, setScanStatus] = useState(null);
  const [results, setResults] = useState([]);
  const [totalSuccess, setTotalSuccess] = useState(0);
  const [totalTested, setTotalTested] = useState(0);
  const [statusMsg, setStatusMsg] = useState(null);
  const [isStarting, setIsStarting] = useState(false);
  const [creditsStatus, setCreditsStatus] = useState(null);
  const [creditsStarting, setCreditsStarting] = useState(false);
  const [page, setPage] = useState(1);
  const [totalMatching, setTotalMatching] = useState(0);
  const perPage = 50;
  const pollRef = useRef(null);

  const fetchRanges = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/checker/ranges`);
      setRanges(res.data.ranges || []);
      setTotalEmails(res.data.total || 0);
    } catch (err) {
      console.error("Ranges fetch error:", err);
    }
  }, []);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/checker/status`);
      setScanStatus(res.data);
      return res.data;
    } catch (err) {
      return null;
    }
  }, []);

  const fetchResults = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/checker/results?status_filter=success&limit=${perPage}&page=${page}`);
      setResults(res.data.results || []);
      setTotalSuccess(res.data.total_success || 0);
      setTotalTested(res.data.total_tested || 0);
      setTotalMatching(res.data.total_matching || 0);
    } catch (err) {
      console.error("Results fetch error:", err);
    }
  }, [page]);

  const fetchCreditsStatus = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/checker/credits/status`);
      setCreditsStatus(res.data);
      return res.data;
    } catch (err) { return null; }
  }, []);

  useEffect(() => {
    fetchRanges();
    fetchStatus();
    fetchResults();
    fetchCreditsStatus();
  }, [fetchRanges, fetchStatus, fetchResults, fetchCreditsStatus]);

  // Poll when scan is running
  useEffect(() => {
    if (scanStatus?.status === "running" || creditsStatus?.status === "running") {
      pollRef.current = setInterval(async () => {
        const s = await fetchStatus();
        await fetchResults();
        await fetchCreditsStatus();
        if (s && s.status !== "running" && creditsStatus?.status !== "running") {
          clearInterval(pollRef.current);
        }
      }, 3000);
      return () => clearInterval(pollRef.current);
    }
  }, [scanStatus?.status, creditsStatus?.status, fetchStatus, fetchResults, fetchCreditsStatus]);

  const handleStart = async () => {
    setIsStarting(true);
    setStatusMsg(null);
    try {
      const res = await axios.post(`${API}/checker/start`, { batch_size: 3 });
      const remaining = res.data.remaining || 0;
      const already = res.data.already_tested || 0;
      const msg = already > 0
        ? `Resuming scan! ${already.toLocaleString()} already tested, ${remaining.toLocaleString()} remaining...`
        : `Scan started! Testing ${res.data.total_emails.toLocaleString()} emails...`;
      setStatusMsg({ type: "success", text: msg });
      setScanStatus({ status: "running", total: res.data.total_emails, tested: already, successful: totalSuccess, remaining });
    } catch (err) {
      setStatusMsg({ type: "error", text: err.response?.data?.detail || "Failed to start scan" });
    } finally {
      setIsStarting(false);
    }
  };

  const handleStop = async () => {
    try {
      await axios.post(`${API}/checker/stop`);
      setStatusMsg({ type: "success", text: "Scan stopped" });
    } catch (err) {
      setStatusMsg({ type: "error", text: "Failed to stop scan" });
    }
  };

  const handleDownload = () => {
    window.open(`${API}/checker/download`, "_blank");
  };

  const handleStartCredits = async () => {
    setCreditsStarting(true);
    try {
      const res = await axios.post(`${API}/checker/credits/start`);
      setStatusMsg({ type: "success", text: `Credits scan started — ${res.data.pending_accounts} accounts to process` });
      fetchCreditsStatus();
    } catch (err) {
      setStatusMsg({ type: "error", text: "Failed to start credits scan" });
    } finally {
      setCreditsStarting(false);
    }
  };

  const handleStopCredits = async () => {
    try {
      await axios.post(`${API}/checker/credits/stop`);
      setStatusMsg({ type: "success", text: "Credits scan stopped" });
      fetchCreditsStatus();
    } catch (err) {
      setStatusMsg({ type: "error", text: "Failed to stop credits scan" });
    }
  };

  const isRunning = scanStatus?.status === "running";
  const isCreditsRunning = creditsStatus?.status === "running";
  const progress = scanStatus?.total > 0 ? ((scanStatus?.tested || 0) / scanStatus.total * 100).toFixed(1) : 0;

  return (
    <div className="checker-agent" data-testid="checker-agent">
      <header className="content-header">
        <div>
          <h1>Account Checker</h1>
          <p>Test DoubleDownCasino email logins and find active accounts</p>
        </div>
        {totalSuccess > 0 && (
          <button className="dir-download-btn" onClick={handleDownload} data-testid="download-results-btn">
            <FileSpreadsheet size={18} /> Download Active ({totalSuccess})
          </button>
        )}
      </header>

      {statusMsg && (
        <div className={`li-status-msg ${statusMsg.type}`} data-testid="checker-status-msg">
          {statusMsg.type === "success" ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
          <span>{statusMsg.text}</span>
          <button className="li-dismiss" onClick={() => setStatusMsg(null)}>&times;</button>
        </div>
      )}

      {/* Email Ranges Overview */}
      <div className="ck-ranges-section" data-testid="ranges-section">
        <div className="ck-ranges-header">
          <h2><Mail size={18} /> Email Ranges</h2>
          <span className="dir-stat-badge">{totalEmails.toLocaleString()} total combinations</span>
        </div>
        <div className="ck-ranges-grid">
          {ranges.map((r, idx) => (
            <div key={idx} className="ck-range-card" data-testid={`range-${r.prefix}`}>
              <div className="ck-range-prefix">{r.prefix}</div>
              <div className="ck-range-detail">
                <span>{r.sample_start}</span>
                <span className="ck-range-arrow">to</span>
                <span>{r.sample_end}</span>
              </div>
              <div className="ck-range-count">{r.count.toLocaleString()} emails</div>
            </div>
          ))}
        </div>
        <div className="ck-password-row">
          <Key size={14} /> Password: <code>c304i109</code> (same for all)
        </div>
      </div>

      {/* Scan Controls */}
      <div className="ck-controls" data-testid="scan-controls">
        {!isRunning ? (
          <button
            className="ck-start-btn"
            onClick={handleStart}
            disabled={isStarting}
            data-testid="start-scan-btn"
          >
            {isStarting ? (
              <><Loader2 className="spin" size={18} /> Starting...</>
            ) : totalTested > 0 ? (
              <><Play size={18} /> Resume Scan ({(totalEmails - totalTested).toLocaleString()} remaining)</>
            ) : (
              <><Play size={18} /> Start Scan</>
            )}
          </button>
        ) : (
          <button className="ck-stop-btn" onClick={handleStop} data-testid="stop-scan-btn">
            <Square size={18} /> Stop Scan
          </button>
        )}

        {/* Credits Scan Button */}
        {totalSuccess > 0 && (
          !isCreditsRunning ? (
            <button
              className="ck-start-btn"
              onClick={handleStartCredits}
              disabled={creditsStarting}
              data-testid="start-credits-btn"
              style={{ marginLeft: 8, background: "#f59e0b" }}
            >
              {creditsStarting ? (
                <><Loader2 className="spin" size={18} /> Starting Credits...</>
              ) : (
                <><Coins size={18} /> Scan Credits ({creditsStatus?.pending || "?"} pending)</>
              )}
            </button>
          ) : (
            <button className="ck-stop-btn" onClick={handleStopCredits} data-testid="stop-credits-btn" style={{ marginLeft: 8 }}>
              <Square size={18} /> Stop Credits
            </button>
          )
        )}
      </div>

      {/* Credits Progress */}
      {creditsStatus && creditsStatus.status === "running" && (
        <div className="ck-progress-section" data-testid="credits-progress" style={{ borderColor: "#f59e0b" }}>
          <div className="ck-progress-header">
            <h2><Coins size={18} /> Credits Scan</h2>
            <span className="ck-status-badge running">running</span>
          </div>
          <div className="ck-progress-bar-container">
            <div className="ck-progress-bar" style={{ width: `${creditsStatus.total > 0 ? (creditsStatus.processed / creditsStatus.total * 100).toFixed(1) : 0}%`, background: "#f59e0b" }} />
          </div>
          <div className="ck-progress-stats">
            <div className="ck-stat">
              <span className="ck-stat-num">{creditsStatus.processed || 0}</span>
              <span className="ck-stat-label">Processed</span>
            </div>
            <div className="ck-stat">
              <span className="ck-stat-num">{creditsStatus.total || 0}</span>
              <span className="ck-stat-label">Total</span>
            </div>
            <div className="ck-stat success">
              <span className="ck-stat-num">{creditsStatus.credits_found || 0}</span>
              <span className="ck-stat-label">Credits Found</span>
            </div>
          </div>
          {creditsStatus.current_email && (
            <div className="ck-current-email">
              <Loader2 className="spin" size={14} /> Scraping: {creditsStatus.current_email}
            </div>
          )}
        </div>
      )}

      {/* Progress */}
      {scanStatus && scanStatus.status !== "idle" && (
        <div className="ck-progress-section" data-testid="progress-section">
          <div className="ck-progress-header">
            <h2><Shield size={18} /> Scan Progress</h2>
            <span className={`ck-status-badge ${scanStatus.status}`}>
              {scanStatus.status === "resumable" ? "paused — ready to resume" : scanStatus.status}
            </span>
          </div>
          <div className="ck-progress-bar-container">
            <div className="ck-progress-bar" style={{ width: `${progress}%` }} />
          </div>
          <div className="ck-progress-stats">
            <div className="ck-stat">
              <span className="ck-stat-num">{(scanStatus.tested || 0).toLocaleString()}</span>
              <span className="ck-stat-label">Tested</span>
            </div>
            <div className="ck-stat">
              <span className="ck-stat-num">{(scanStatus.total || 0).toLocaleString()}</span>
              <span className="ck-stat-label">Total</span>
            </div>
            <div className="ck-stat success">
              <span className="ck-stat-num">{(scanStatus.successful || 0).toLocaleString()}</span>
              <span className="ck-stat-label">Successful</span>
            </div>
            <div className="ck-stat">
              <span className="ck-stat-num">{(scanStatus.failed || 0).toLocaleString()}</span>
              <span className="ck-stat-label">Failed</span>
            </div>
            <div className="ck-stat">
              <span className="ck-stat-num">{(scanStatus.remaining !== undefined ? scanStatus.remaining : scanStatus.total - (scanStatus.tested || 0)).toLocaleString()}</span>
              <span className="ck-stat-label">Remaining</span>
            </div>
            <div className="ck-stat">
              <span className="ck-stat-num">{progress}%</span>
              <span className="ck-stat-label">Complete</span>
            </div>
          </div>
          {scanStatus.current_email && isRunning && (
            <div className="ck-current-email">
              <Loader2 className="spin" size={14} /> Testing: {scanStatus.current_email}
            </div>
          )}
        </div>
      )}

      {/* Successful Logins */}
      <div className="ck-results-section" data-testid="results-section">
        <div className="ck-results-header">
          <h2><CheckCircle size={18} /> Active Accounts ({totalSuccess})</h2>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            {totalTested > 0 && (
              <span className="ck-tested-info">{totalTested} tested so far</span>
            )}
            {totalMatching > perPage && (
              <div className="hcl-pagination" data-testid="pagination">
                <button className="hcl-page-btn" disabled={page <= 1} onClick={() => setPage(page - 1)}>&lt;</button>
                <span>Page {page} of {Math.ceil(totalMatching / perPage)}</span>
                <button className="hcl-page-btn" disabled={page * perPage >= totalMatching} onClick={() => setPage(page + 1)}>&gt;</button>
              </div>
            )}
          </div>
        </div>
        {results.length === 0 ? (
          <div className="ck-empty">
            {isRunning ? (
              <><Loader2 className="spin" size={32} /><p>Scanning... successful logins will appear here</p></>
            ) : (
              <><Shield size={32} /><p>No successful logins found yet</p><span>Start a scan to test accounts</span></>
            )}
          </div>
        ) : (
          <div className="ck-results-table-container">
            <table className="dir-table">
              <thead>
                <tr>
                  <th style={{ width: 40 }}>#</th>
                  <th>Email</th>
                  <th>Prefix</th>
                  <th>Number</th>
                  <th>Credits</th>
                  <th>Tested At</th>
                  <th style={{ width: 90 }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r, idx) => (
                  <tr key={r.email} className="dir-row" data-testid={`result-row-${idx}`}>
                    <td className="dir-cell-num">{(page - 1) * perPage + idx + 1}</td>
                    <td>
                      <span className="ck-email-success">
                        <CheckCircle size={14} /> {r.email}
                      </span>
                    </td>
                    <td>{r.prefix}</td>
                    <td>{r.num}</td>
                    <td>
                      {r.credits ? (
                        <span style={{ color: "#f59e0b", fontWeight: 600 }}>{r.credits}</span>
                      ) : (
                        <span style={{ color: "var(--text-muted)" }}>—</span>
                      )}
                    </td>
                    <td className="dir-cell-phone">
                      {r.tested_at ? new Date(r.tested_at).toLocaleString() : "-"}
                    </td>
                    <td>
                      <button
                        className="ck-login-btn"
                        onClick={() => window.open(`${API}/checker/autologin?email=${encodeURIComponent(r.email)}`, '_blank')}
                        data-testid={`login-btn-${idx}`}
                      >
                        <ExternalLink size={12} /> Login
                      </button>
                    </td>
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

export default AccountChecker;
