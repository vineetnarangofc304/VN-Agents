import { useState } from "react";
import { useAuth } from "./AuthContext";
import { Loader2, LogIn } from "lucide-react";

export default function LoginPage() {
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
      const detail = err.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: "#09090b" }}>
      <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-5 p-8 rounded-lg border" style={{ background: "#18181b", borderColor: "#27272a" }}>
        <div className="text-center">
          <h1 className="text-2xl font-bold text-white tracking-tight" style={{ fontFamily: "'Manrope', sans-serif" }}>
            LinkedIn CRM
          </h1>
          <p className="text-sm mt-1" style={{ color: "#71717a" }}>Sign in to your account</p>
        </div>

        {error && (
          <div className="rounded-md px-3 py-2 text-sm" style={{ background: "#ef444420", color: "#ef4444" }} data-testid="login-error">
            {error}
          </div>
        )}

        <div className="space-y-3">
          <input
            data-testid="login-email"
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="w-full px-3 py-2.5 rounded-md border text-sm text-white placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-blue-600"
            style={{ background: "#09090b", borderColor: "#27272a" }}
          />
          <input
            data-testid="login-password"
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="w-full px-3 py-2.5 rounded-md border text-sm text-white placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-blue-600"
            style={{ background: "#09090b", borderColor: "#27272a" }}
          />
        </div>

        <button
          data-testid="login-submit"
          type="submit"
          disabled={loading}
          className="w-full py-2.5 rounded-md text-sm font-semibold text-white flex items-center justify-center gap-2 disabled:opacity-50 transition-colors"
          style={{ background: "#2563eb" }}
        >
          {loading ? <Loader2 size={16} className="animate-spin" /> : <LogIn size={16} />}
          Sign In
        </button>
      </form>
    </div>
  );
}
