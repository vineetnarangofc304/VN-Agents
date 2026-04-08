import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import {
  Loader2, Send, RefreshCw, CheckCircle, AlertCircle,
  Link2, Unlink, Building2, Clock, Pencil, Copy, Zap,
  ChevronDown, ExternalLink, History, Settings
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const LinkedInAgent = () => {
  // State
  const [accounts, setAccounts] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [selectedAccount, setSelectedAccount] = useState(null);
  const [selectedCompany, setSelectedCompany] = useState("fundle");
  const [generatedPosts, setGeneratedPosts] = useState([]);
  const [editableContent, setEditableContent] = useState("");
  const [postHistory, setPostHistory] = useState([]);
  const [loading, setLoading] = useState({ accounts: true, generating: false, posting: false });
  const [view, setView] = useState("compose"); // compose | history | settings
  const [topic, setTopic] = useState("");
  const [scheduleEnabled, setScheduleEnabled] = useState(false);
  const [scheduleInterval, setScheduleInterval] = useState(4);
  const [statusMsg, setStatusMsg] = useState(null);

  const fetchAccounts = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/linkedin/accounts`);
      const accs = res.data.accounts || [];
      setAccounts(accs);
      if (accs.length > 0 && !selectedAccount) {
        setSelectedAccount(accs[0]);
        setScheduleEnabled(accs[0].schedule_enabled || false);
        setScheduleInterval(accs[0].schedule_interval_hours || 4);
      }
    } catch (err) {
      console.error("Error fetching accounts:", err);
    } finally {
      setLoading(prev => ({ ...prev, accounts: false }));
    }
  }, [selectedAccount]);

  const fetchCompanies = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/linkedin/companies`);
      setCompanies(res.data.companies || []);
    } catch (err) {
      console.error("Error fetching companies:", err);
    }
  }, []);

  const fetchPostHistory = useCallback(async () => {
    try {
      const params = {};
      if (selectedAccount) params.account_id = selectedAccount.account_id;
      const res = await axios.get(`${API}/linkedin/posts`, { params });
      setPostHistory(res.data.posts || []);
    } catch (err) {
      console.error("Error fetching post history:", err);
    }
  }, [selectedAccount]);

  useEffect(() => {
    fetchAccounts();
    fetchCompanies();
  }, [fetchAccounts, fetchCompanies]);

  useEffect(() => {
    if (view === "history") fetchPostHistory();
  }, [view, fetchPostHistory]);

  // Listen for OAuth popup messages
  useEffect(() => {
    const handler = (event) => {
      if (event.data?.type === "linkedin-auth-success") {
        setStatusMsg({ type: "success", text: `Connected: ${event.data.name}` });
        fetchAccounts();
      } else if (event.data?.type === "linkedin-auth-error") {
        setStatusMsg({ type: "error", text: `Failed: ${event.data.error}` });
      }
    };
    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, [fetchAccounts]);

  const handleConnect = async () => {
    try {
      const res = await axios.get(`${API}/linkedin/auth`);
      const authUrl = res.data.auth_url;
      window.open(authUrl, "linkedin-auth", "width=600,height=700,left=200,top=100");
    } catch (err) {
      setStatusMsg({ type: "error", text: "Failed to start LinkedIn auth" });
    }
  };

  const handleDisconnect = async (accountId) => {
    if (!window.confirm("Disconnect this LinkedIn account?")) return;
    try {
      await axios.delete(`${API}/linkedin/accounts/${accountId}`);
      setAccounts(prev => prev.filter(a => a.account_id !== accountId));
      if (selectedAccount?.account_id === accountId) setSelectedAccount(null);
      setStatusMsg({ type: "success", text: "Account disconnected" });
    } catch (err) {
      setStatusMsg({ type: "error", text: "Failed to disconnect" });
    }
  };

  const handleGenerate = async () => {
    setLoading(prev => ({ ...prev, generating: true }));
    setStatusMsg(null);
    try {
      const res = await axios.post(`${API}/linkedin/generate-content`, {
        company: selectedCompany,
        topic: topic || undefined,
        tone: "professional",
        post_count: 3
      });
      const posts = res.data.posts || [];
      setGeneratedPosts(posts);
      if (posts.length > 0 && !posts[0].error) {
        setEditableContent(posts[0].content);
      }
    } catch (err) {
      setStatusMsg({ type: "error", text: "Failed to generate content" });
    } finally {
      setLoading(prev => ({ ...prev, generating: false }));
    }
  };

  const handlePost = async () => {
    if (!selectedAccount) {
      setStatusMsg({ type: "error", text: "Connect a LinkedIn account first" });
      return;
    }
    if (!editableContent.trim()) {
      setStatusMsg({ type: "error", text: "Post content is empty" });
      return;
    }

    setLoading(prev => ({ ...prev, posting: true }));
    setStatusMsg(null);
    try {
      await axios.post(`${API}/linkedin/post`, {
        account_id: selectedAccount.account_id,
        company: selectedCompany,
        content: editableContent,
        post_type: "text"
      });
      setStatusMsg({ type: "success", text: "Post published to LinkedIn!" });
      setEditableContent("");
      fetchPostHistory();
    } catch (err) {
      const detail = err.response?.data?.detail || "Failed to publish post";
      setStatusMsg({ type: "error", text: detail });
    } finally {
      setLoading(prev => ({ ...prev, posting: false }));
    }
  };

  const handleScheduleToggle = async () => {
    if (!selectedAccount) return;
    try {
      const newEnabled = !scheduleEnabled;
      await axios.post(`${API}/linkedin/schedule`, {
        account_id: selectedAccount.account_id,
        company: selectedCompany,
        interval_hours: scheduleInterval,
        enabled: newEnabled
      });
      setScheduleEnabled(newEnabled);
      setStatusMsg({ type: "success", text: newEnabled ? `Auto-posting every ${scheduleInterval}h enabled` : "Auto-posting disabled" });
    } catch (err) {
      setStatusMsg({ type: "error", text: "Failed to update schedule" });
    }
  };

  return (
    <div className="linkedin-agent" data-testid="linkedin-agent">
      <header className="content-header">
        <div>
          <h1>LinkedIn Agent</h1>
          <p>Auto-generate and publish LinkedIn posts for your companies</p>
        </div>
        <div className="linkedin-header-actions">
          <button
            className={`view-tab ${view === "compose" ? "active" : ""}`}
            onClick={() => setView("compose")}
            data-testid="linkedin-tab-compose"
          >
            <Pencil size={16} /> Compose
          </button>
          <button
            className={`view-tab ${view === "history" ? "active" : ""}`}
            onClick={() => setView("history")}
            data-testid="linkedin-tab-history"
          >
            <History size={16} /> History
          </button>
          <button
            className={`view-tab ${view === "settings" ? "active" : ""}`}
            onClick={() => setView("settings")}
            data-testid="linkedin-tab-settings"
          >
            <Settings size={16} /> Settings
          </button>
        </div>
      </header>

      {/* Status Message */}
      {statusMsg && (
        <div className={`li-status-msg ${statusMsg.type}`} data-testid="linkedin-status-msg">
          {statusMsg.type === "success" ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
          <span>{statusMsg.text}</span>
          <button className="li-dismiss" onClick={() => setStatusMsg(null)}>&times;</button>
        </div>
      )}

      {/* ============ Settings View ============ */}
      {view === "settings" && (
        <div className="li-settings" data-testid="linkedin-settings">
          {/* Connected Accounts */}
          <div className="li-section">
            <h2><Link2 size={18} /> Connected Accounts</h2>
            <div className="li-accounts-list">
              {loading.accounts ? (
                <div className="li-loading"><Loader2 className="spin" size={24} /></div>
              ) : accounts.length === 0 ? (
                <div className="li-empty">
                  <p>No LinkedIn accounts connected</p>
                </div>
              ) : (
                accounts.map(acc => (
                  <div key={acc.account_id} className="li-account-card" data-testid={`li-account-${acc.account_id}`}>
                    <div className="li-account-info">
                      {acc.picture ? (
                        <img src={acc.picture} alt="" className="li-avatar" />
                      ) : (
                        <div className="li-avatar-placeholder">{acc.name?.[0] || "?"}</div>
                      )}
                      <div>
                        <span className="li-account-name">{acc.name}</span>
                        <span className="li-account-email">{acc.email || "Personal Profile"}</span>
                        <span className={`li-account-status ${acc.last_sync_status === "connected" || acc.last_sync_status === "post_published" ? "ok" : "warn"}`}>
                          {acc.last_sync_status}
                        </span>
                      </div>
                    </div>
                    <button
                      className="li-disconnect-btn"
                      onClick={() => handleDisconnect(acc.account_id)}
                      data-testid={`disconnect-${acc.account_id}`}
                    >
                      <Unlink size={14} /> Disconnect
                    </button>
                  </div>
                ))
              )}
              <button className="li-connect-btn" onClick={handleConnect} data-testid="linkedin-connect-btn">
                <Link2 size={16} /> Connect LinkedIn Account
              </button>
            </div>
          </div>

          {/* Schedule Settings */}
          <div className="li-section">
            <h2><Clock size={18} /> Auto-Post Schedule</h2>
            <div className="li-schedule-config">
              <div className="li-schedule-row">
                <label>Company:</label>
                <select
                  value={selectedCompany}
                  onChange={(e) => setSelectedCompany(e.target.value)}
                  data-testid="schedule-company-select"
                >
                  {companies.map(c => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>
              <div className="li-schedule-row">
                <label>Post every:</label>
                <select
                  value={scheduleInterval}
                  onChange={(e) => setScheduleInterval(parseInt(e.target.value))}
                  data-testid="schedule-interval-select"
                >
                  <option value={2}>2 hours</option>
                  <option value={4}>4 hours</option>
                  <option value={6}>6 hours</option>
                  <option value={8}>8 hours</option>
                  <option value={12}>12 hours</option>
                  <option value={24}>24 hours</option>
                </select>
              </div>
              <div className="li-schedule-row">
                <label>Account:</label>
                <select
                  value={selectedAccount?.account_id || ""}
                  onChange={(e) => {
                    const acc = accounts.find(a => a.account_id === e.target.value);
                    setSelectedAccount(acc || null);
                  }}
                  data-testid="schedule-account-select"
                >
                  <option value="">Select account...</option>
                  {accounts.map(a => (
                    <option key={a.account_id} value={a.account_id}>{a.name}</option>
                  ))}
                </select>
              </div>
              <button
                className={`li-schedule-toggle ${scheduleEnabled ? "active" : ""}`}
                onClick={handleScheduleToggle}
                disabled={!selectedAccount}
                data-testid="schedule-toggle-btn"
              >
                {scheduleEnabled ? (
                  <><CheckCircle size={16} /> Auto-Posting ON</>
                ) : (
                  <><Clock size={16} /> Enable Auto-Posting</>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ============ Compose View ============ */}
      {view === "compose" && (
        <div className="li-compose" data-testid="linkedin-compose">
          {/* Company & Account Selector */}
          <div className="li-toolbar">
            <div className="li-toolbar-group">
              <label>Post as:</label>
              <select
                value={selectedAccount?.account_id || ""}
                onChange={(e) => {
                  const acc = accounts.find(a => a.account_id === e.target.value);
                  setSelectedAccount(acc || null);
                }}
                className="li-select"
                data-testid="compose-account-select"
              >
                <option value="">
                  {accounts.length === 0 ? "Connect account first" : "Select account..."}
                </option>
                {accounts.map(a => (
                  <option key={a.account_id} value={a.account_id}>{a.name}</option>
                ))}
              </select>
            </div>
            <div className="li-toolbar-group">
              <label>Company:</label>
              <select
                value={selectedCompany}
                onChange={(e) => setSelectedCompany(e.target.value)}
                className="li-select"
                data-testid="compose-company-select"
              >
                {companies.map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Content Generation */}
          <div className="li-generate-section">
            <div className="li-generate-header">
              <h2><Zap size={18} /> Generate Content</h2>
            </div>
            <div className="li-generate-controls">
              <input
                type="text"
                placeholder="Topic (optional) - e.g., 'retail data trends' or leave blank for AI to choose"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                className="li-topic-input"
                data-testid="topic-input"
              />
              <button
                className="li-generate-btn"
                onClick={handleGenerate}
                disabled={loading.generating}
                data-testid="generate-posts-btn"
              >
                {loading.generating ? (
                  <><Loader2 className="spin" size={16} /> Generating 3 posts...</>
                ) : (
                  <><Zap size={16} /> Generate 3 Posts</>
                )}
              </button>
            </div>

            {/* Generated Post Options */}
            {generatedPosts.length > 0 && (
              <div className="li-generated-list">
                <h3>Pick a post to edit & publish:</h3>
                {generatedPosts.map((post, idx) => (
                  <div
                    key={idx}
                    className={`li-generated-card ${editableContent === post.content ? "selected" : ""}`}
                    onClick={() => !post.error && setEditableContent(post.content)}
                    data-testid={`generated-post-${idx}`}
                  >
                    <div className="li-generated-header-row">
                      <span className="li-post-num">Post {idx + 1}</span>
                      {editableContent === post.content && (
                        <span className="li-selected-badge"><CheckCircle size={12} /> Selected</span>
                      )}
                    </div>
                    <p className="li-generated-preview">
                      {post.error ? post.content : post.content.substring(0, 200) + (post.content.length > 200 ? "..." : "")}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Editor & Publish */}
          <div className="li-editor-section">
            <h2><Pencil size={18} /> Edit & Publish</h2>
            <textarea
              className="li-editor"
              value={editableContent}
              onChange={(e) => setEditableContent(e.target.value)}
              placeholder="Write your LinkedIn post here, or generate content above..."
              rows={12}
              data-testid="post-editor"
            />
            <div className="li-editor-footer">
              <span className="li-char-count">{editableContent.length} chars</span>
              <div className="li-editor-actions">
                <button
                  className="li-copy-btn"
                  onClick={() => {
                    navigator.clipboard.writeText(editableContent);
                    setStatusMsg({ type: "success", text: "Copied to clipboard!" });
                  }}
                  disabled={!editableContent}
                  data-testid="copy-post-btn"
                >
                  <Copy size={14} /> Copy
                </button>
                <button
                  className="li-publish-btn"
                  onClick={handlePost}
                  disabled={loading.posting || !editableContent.trim() || !selectedAccount}
                  data-testid="publish-post-btn"
                >
                  {loading.posting ? (
                    <><Loader2 className="spin" size={16} /> Publishing...</>
                  ) : (
                    <><Send size={16} /> Publish to LinkedIn</>
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* Quick Connect if no accounts */}
          {accounts.length === 0 && !loading.accounts && (
            <div className="li-no-account-banner" data-testid="no-account-banner">
              <AlertCircle size={20} />
              <span>Connect your LinkedIn account to start posting</span>
              <button className="li-connect-btn-sm" onClick={handleConnect} data-testid="quick-connect-btn">
                <Link2 size={14} /> Connect Now
              </button>
            </div>
          )}
        </div>
      )}

      {/* ============ History View ============ */}
      {view === "history" && (
        <div className="li-history" data-testid="linkedin-history">
          <h2><History size={18} /> Post History</h2>
          {postHistory.length === 0 ? (
            <div className="li-empty">
              <History size={48} />
              <p>No posts published yet</p>
              <span>Generate and publish your first post from the Compose tab</span>
            </div>
          ) : (
            <div className="li-history-list">
              {postHistory.map((post, idx) => (
                <div key={idx} className="li-history-card" data-testid={`history-post-${idx}`}>
                  <div className="li-history-meta">
                    <span className="li-history-company">{post.company}</span>
                    <span className="li-history-date">
                      {new Date(post.published_at).toLocaleString()}
                    </span>
                    <span className={`li-history-status ${post.status}`}>{post.status}</span>
                  </div>
                  <p className="li-history-content">{post.content}</p>
                  {post.post_id && (
                    <a
                      href={`https://www.linkedin.com/feed/update/${post.post_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="li-view-post-link"
                    >
                      <ExternalLink size={12} /> View on LinkedIn
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default LinkedInAgent;
