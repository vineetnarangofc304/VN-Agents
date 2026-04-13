import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import {
  Loader2, Play, Square, Download, CheckCircle, XCircle,
  AlertCircle, RefreshCw, FileSpreadsheet, Key, Mail, Shield, ExternalLink, Coins, Wheat
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
  const [farmStatus, setFarmStatus] = useState(null);
  const [farmStarting, setFarmStarting] = useState(false);
  const pollRef = useRef(null);

  const fetchRanges = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/checker/ranges`);
      setRanges(res.data.ranges || []);
      setTotalEmails(res.data.total || 0);
    } catch (err) { console.error(err); }
  }, []);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/checker/status`);
      setScanStatus(res.data);
      return res.data;
    } catch (err) { return null; }
  }, []);

  const fetchResults = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/checker/results?status_filter=success&sort_by=credits`);
      setResults(res.data.results || []);
      setTotalSuccess(res.data.total_success || 0);
      setTotalTested(res.data.total_tested || 0);
    } catch (err) { console.error(err); }
  }, []);

  const fetchCreditsStatus = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/checker/credits/status`);
      setCreditsStatus(res.data);
    } catch (err) {}
  }, []);

  const fetchFarmStatus = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/checker/farm/status`);
      setFarmStatus(res.data);
    } catch (err) {}
  }, []);

  useEffect(() => {
    fetchRanges(); fetchStatus(); fetchResults(); fetchCreditsStatus(); fetchFarmStatus();
  }, [fetchRanges, fetchStatus, fetchResults, fetchCreditsStatus, fetchFarmStatus]);

  useEffect(() => {
    const anyRunning = scanStatus?.status === "running" || creditsStatus?.status === "running" || farmStatus?.status === "running";
    if (anyRunning) {
      pollRef.current = setInterval(() => {
        fetchStatus(); fetchResults(); fetchCreditsStatus(); fetchFarmStatus();
      }, 5000);
      return () => clearInterval(pollRef.current);
    }
  }, [scanStatus?.status, creditsStatus?.status, farmStatus?.status, fetchStatus, fetchResults, fetchCreditsStatus, fetchFarmStatus]);

  const handleStart = async () => {
    setIsStarting(true);
    try {
      const res = await axios.post(`${API}/checker/start`, { batch_size: 3 });
      setStatusMsg({ type: "success", text: `Scan started! ${res.data.remaining || 0} remaining.` });
      fetchStatus();
    } catch (err) {
      setStatusMsg({ type: "error", text: err.response?.data?.detail || "Failed" });
    } finally { setIsStarting(false); }
  };

  const handleStop = async () => {
    await axios.post(`${API}/checker/stop`); fetchStatus();
  };

  const handleStartCredits = async () => {
    setCreditsStarting(true);
    try {
      const res = await axios.post(`${API}/checker/credits/start`);
      setStatusMsg({ type: "success", text: `Credits scan: ${res.data.pending_accounts} pending` });
      fetchCreditsStatus();
    } catch (err) {
      setStatusMsg({ type: "error", text: "Failed to start credits scan" });
    } finally { setCreditsStarting(false); }
  };

  const handleStopCredits = async () => {
    await axios.post(`${API}/checker/credits/stop`); fetchCreditsStatus();
  };

  const handleStartFarm = async () => {
    setFarmStarting(true);
    try {
      const res = await axios.post(`${API}/checker/farm/start`);
      setStatusMsg({ type: "success", text: `Chip Farm started for ${res.data.total_accounts} accounts` });
      fetchFarmStatus();
    } catch (err) {
      setStatusMsg({ type: "error", text: "Failed to start farm" });
    } finally { setFarmStarting(false); }
  };

  const handleStopFarm = async () => {
    await axios.post(`${API}/checker/farm/stop`); fetchFarmStatus();
  };

  const handleDownload = () => { window.open(`${API}/checker/download`, "_blank"); };

  const isRunning = scanStatus?.status === "running";
  const isCreditsRunning = creditsStatus?.status === "running";
  const isFarmRunning = farmStatus?.status === "running";
  const progress = scanStatus?.total > 0 ? ((scanStatus?.tested || 0) / scanStatus.total * 100).toFixed(1) : 0;

  const formatCredits = (c) => {
    if (!c || c === "LOGIN_OK_CREDITS_UNKNOWN") return null;
    try {
      return parseInt(c).toLocaleString("en-IN");
    } catch { return c; }
  };

  const formatDate = (d) => {
    if (!d) return null;
    try { return new Date(d).toLocaleString("en-IN", { dateStyle: "short", timeStyle: "short" }); }
    catch { return d.slice(0, 16); }
  };

  return (
    <div className="account-checker" data-testid="account-checker">
      <header className="content-header">
        <div>
          <h1>Account Checker</h1>
          <p>{totalEmails.toLocaleString()} emails to scan | {totalSuccess.toLocaleString()} active accounts found</p>
        </div>
        {totalSuccess > 0 && (
          <button className="dir-download-btn" onClick={handleDownload} data-testid="download-btn">
            <Download size={16} /> Download ({totalSuccess})
          </button>
        )}
      </header>

      {statusMsg && (
        <div className={`li-status-msg ${statusMsg.type}`}>
          <AlertCircle size={16} /><span>{statusMsg.text}</span>
          <button className="li-dismiss" onClick={() => setStatusMsg(null)}>&times;</button>
        </div>
      )}

      {/* Controls Row */}
      <div className="ck-controls" data-testid="scan-controls" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {/* Login Scan */}
        {!isRunning ? (
          <button className="ck-start-btn" onClick={handleStart} disabled={isStarting} data-testid="start-scan-btn">
            {isStarting ? <><Loader2 className="spin" size={16} /> Starting...</> :
              totalTested > 0 ? <><Play size={16} /> Resume Scan</> : <><Play size={16} /> Start Scan</>}
          </button>
        ) : (
          <button className="ck-stop-btn" onClick={handleStop} data-testid="stop-scan-btn"><Square size={16} /> Stop Scan</button>
        )}

        {/* Credits Scan */}
        {totalSuccess > 0 && (
          !isCreditsRunning ? (
            <button className="ck-start-btn" onClick={handleStartCredits} disabled={creditsStarting} data-testid="start-credits-btn" style={{ background: "#f59e0b" }}>
              {creditsStarting ? <><Loader2 className="spin" size={16} /> Starting...</> : <><Coins size={16} /> Scan Credits</>}
            </button>
          ) : (
            <button className="ck-stop-btn" onClick={handleStopCredits} data-testid="stop-credits-btn"><Square size={16} /> Stop Credits</button>
          )
        )}

        {/* Chip Farm */}
        {totalSuccess > 0 && (
          !isFarmRunning ? (
            <button className="ck-start-btn" onClick={handleStartFarm} disabled={farmStarting} data-testid="start-farm-btn" style={{ background: "#16a34a" }}>
              {farmStarting ? <><Loader2 className="spin" size={16} /> Starting...</> : <><Wheat size={16} /> Farm Chips</>}
            </button>
          ) : (
            <button className="ck-stop-btn" onClick={handleStopFarm} data-testid="stop-farm-btn"><Square size={16} /> Stop Farm</button>
          )
        )}
      </div>

      {/* Progress Bars */}
      {scanStatus && scanStatus.status !== "idle" && (
        <div className="ck-progress-section" data-testid="progress-section">
          <div className="ck-progress-header">
            <h2><Shield size={18} /> Login Scan</h2>
            <span className={`ck-status-badge ${scanStatus.status}`}>{scanStatus.status}</span>
          </div>
          <div className="ck-progress-bar-container">
            <div className="ck-progress-bar" style={{ width: `${progress}%` }} />
          </div>
          <div className="ck-progress-stats">
            <div className="ck-stat"><span className="ck-stat-num">{(scanStatus.tested || 0).toLocaleString()}</span><span className="ck-stat-label">Tested</span></div>
            <div className="ck-stat success"><span className="ck-stat-num">{(scanStatus.successful || 0).toLocaleString()}</span><span className="ck-stat-label">Success</span></div>
            <div className="ck-stat"><span className="ck-stat-num">{(scanStatus.remaining !== undefined ? scanStatus.remaining : 0).toLocaleString()}</span><span className="ck-stat-label">Remaining</span></div>
          </div>
          {scanStatus.current_email && isRunning && (
            <div className="ck-current-email"><Loader2 className="spin" size={14} /> {scanStatus.current_email}</div>
          )}
        </div>
      )}

      {creditsStatus && creditsStatus.status === "running" && (
        <div className="ck-progress-section" style={{ borderColor: "#f59e0b" }}>
          <div className="ck-progress-header"><h2><Coins size={18} /> Credits Scan</h2><span className="ck-status-badge running">running</span></div>
          <div className="ck-progress-bar-container"><div className="ck-progress-bar" style={{ width: `${creditsStatus.total > 0 ? (creditsStatus.processed / creditsStatus.total * 100).toFixed(1) : 0}%`, background: "#f59e0b" }} /></div>
          <div className="ck-progress-stats">
            <div className="ck-stat"><span className="ck-stat-num">{creditsStatus.processed || 0}</span><span className="ck-stat-label">Processed</span></div>
            <div className="ck-stat success"><span className="ck-stat-num">{creditsStatus.credits_found || 0}</span><span className="ck-stat-label">Found</span></div>
          </div>
          {creditsStatus.current_email && <div className="ck-current-email"><Loader2 className="spin" size={14} /> {creditsStatus.current_email}</div>}
        </div>
      )}

      {farmStatus && farmStatus.status === "running" && (
        <div className="ck-progress-section" style={{ borderColor: "#16a34a" }}>
          <div className="ck-progress-header"><h2><Wheat size={18} /> Chip Farm</h2><span className="ck-status-badge running">running</span></div>
          <div className="ck-progress-bar-container"><div className="ck-progress-bar" style={{ width: `${farmStatus.total > 0 ? (farmStatus.processed / farmStatus.total * 100).toFixed(1) : 0}%`, background: "#16a34a" }} /></div>
          <div className="ck-progress-stats">
            <div className="ck-stat"><span className="ck-stat-num">{farmStatus.processed || 0}/{farmStatus.total || 0}</span><span className="ck-stat-label">Accounts</span></div>
            <div className="ck-stat success"><span className="ck-stat-num">{(farmStatus.chips_gained || 0).toLocaleString()}</span><span className="ck-stat-label">Chips Gained</span></div>
            <div className="ck-stat"><span className="ck-stat-num">{farmStatus.promo_codes_found || 0}</span><span className="ck-stat-label">Promo Codes</span></div>
          </div>
          {farmStatus.current_email && <div className="ck-current-email"><Loader2 className="spin" size={14} /> Farming: {farmStatus.current_email}</div>}
        </div>
      )}

      {/* Results Table */}
      <div className="ck-results-section" data-testid="results-section">
        <div className="ck-results-header">
          <h2><CheckCircle size={18} /> Active Accounts ({totalSuccess}) — sorted by credits</h2>
        </div>

        {results.length === 0 ? (
          <div className="ck-empty"><Mail size={32} /><p>No active accounts found yet</p></div>
        ) : (
          <div className="ck-results-table-container" style={{ maxHeight: "70vh", overflowY: "auto" }}>
            <table className="dir-table">
              <thead style={{ position: "sticky", top: 0, zIndex: 1 }}>
                <tr>
                  <th style={{ width: 40 }}>#</th>
                  <th>Email</th>
                  <th style={{ width: 110 }}>Credits</th>
                  <th style={{ width: 140 }}>Last Farmed</th>
                  <th style={{ width: 80 }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r, idx) => (
                  <tr key={r.email} className="dir-row" data-testid={`result-row-${idx}`}>
                    <td className="dir-cell-num">{idx + 1}</td>
                    <td><span className="ck-email-success"><CheckCircle size={14} /> {r.email}</span></td>
                    <td>
                      {formatCredits(r.credits) ? (
                        <span style={{ color: "#f59e0b", fontWeight: 700, fontSize: "0.9rem" }}>{formatCredits(r.credits)}</span>
                      ) : (
                        <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>pending</span>
                      )}
                    </td>
                    <td>
                      {r.last_farmed_at ? (
                        <span style={{ fontSize: "0.75rem", color: "#16a34a" }}>{formatDate(r.last_farmed_at)}</span>
                      ) : (
                        <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>never</span>
                      )}
                    </td>
                    <td>
                      <button className="ck-login-btn" onClick={() => window.open(`${API}/checker/autologin?email=${encodeURIComponent(r.email)}`, '_blank')} data-testid={`login-btn-${idx}`}>
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
