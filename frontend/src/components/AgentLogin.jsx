import { useState, useEffect } from "react";
import { Eye, EyeOff, Loader2, AlertCircle, LogOut } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AgentLogin = ({ agentName, agentIcon: Icon, agentColor, children }) => {
  const [authenticated, setAuthenticated] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  // Check if already authenticated in sessionStorage
  useEffect(() => {
    const stored = sessionStorage.getItem(`agent_auth_${agentName}`);
    if (stored === "true") setAuthenticated(true);
  }, [agentName]);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const resp = await fetch(`${API}/auth/agent-login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent: agentName, password })
      });
      const data = await resp.json();
      if (resp.ok && data.success) {
        setAuthenticated(true);
        sessionStorage.setItem(`agent_auth_${agentName}`, "true");
      } else {
        setError(data.detail || "Invalid password");
      }
    } catch (err) {
      setError("Connection error");
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    setAuthenticated(false);
    sessionStorage.removeItem(`agent_auth_${agentName}`);
  };

  if (authenticated) {
    return (
      <div className="agent-standalone">
        <div className="agent-topbar">
          <div className="agent-topbar-title" style={{ color: agentColor || "var(--accent)" }}>
            {Icon && <Icon size={20} />}
            <span>{agentName}</span>
          </div>
          <button className="agent-logout-btn" onClick={handleLogout} data-testid="agent-logout-btn">
            <LogOut size={16} /> Logout
          </button>
        </div>
        <div className="agent-content-area">
          {children}
        </div>
      </div>
    );
  }

  return (
    <div className="agent-login-container" data-testid={`login-${agentName}`}>
      <div className="agent-login-card">
        <div className="agent-login-icon" style={{ background: agentColor || "var(--accent)" }}>
          {Icon && <Icon size={32} color="#fff" />}
        </div>
        <h1>{agentName}</h1>
        <p>Enter password to access</p>

        <form onSubmit={handleLogin} className="agent-login-form">
          {error && (
            <div className="error-message" data-testid="login-error">
              <AlertCircle size={16} /> {error}
            </div>
          )}
          <div className="password-input-wrapper">
            <input
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              required
              autoFocus
              data-testid="agent-password-input"
            />
            <button
              type="button"
              className="password-toggle-btn"
              onClick={() => setShowPassword(!showPassword)}
              data-testid="password-toggle-btn"
            >
              {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>
          <button type="submit" className="login-btn" disabled={loading} data-testid="agent-login-btn">
            {loading ? <Loader2 className="spin" size={20} /> : "Access"}
          </button>
        </form>
      </div>
    </div>
  );
};

export default AgentLogin;
