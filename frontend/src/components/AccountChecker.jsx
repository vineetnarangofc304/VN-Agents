import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import {
  Loader2, Play, Square, Download, CheckCircle, XCircle,
  AlertCircle, RefreshCw, FileSpreadsheet, Key, Mail, Shield
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
      const res = await axios.get(`${API}/checker/results?status_filter=success&limit=500`);
      setResults(res.data.results || []);
      setTotalSuccess(res.data.total_success || 0);
      setTotalTested(res.data.total_tested || 0);
    } catch (err) {
      console.error("Results fetch error:", err);
    }
  }, []);

  useEffect(() => {
    fetchRanges();
    fetchStatus();
    fetchResults();
  }, [fetchRanges, fetchStatus, fetchResults]);

  // Poll when scan is running
  useEffect(() => {
    if (scanStatus?.status === "running") {
      pollRef.current = setInterval(async () => {
        const s = await fetchStatus();
        await fetchResults();
        if (s && s.status !== "running") {
          clearInterval(pollRef.current);
        }
      }, 3000);
      return () => clearInterval(pollRef.current);
    }
  }, [scanStatus?.status, fetchStatus, fetchResults]);

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

  const isRunning = scanStatus?.status === "running";
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
      </div>

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
          {totalTested > 0 && (
            <span className="ck-tested-info">{totalTested} tested so far</span>
          )}
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
                  <th>Tested At</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r, idx) => (
                  <tr key={r.email} className="dir-row" data-testid={`result-row-${idx}`}>
                    <td className="dir-cell-num">{idx + 1}</td>
                    <td>
                      <span className="ck-email-success">
                        <CheckCircle size={14} /> {r.email}
                      </span>
                    </td>
                    <td>{r.prefix}</td>
                    <td>{r.num}</td>
                    <td className="dir-cell-phone">
                      {r.tested_at ? new Date(r.tested_at).toLocaleString() : "-"}
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
