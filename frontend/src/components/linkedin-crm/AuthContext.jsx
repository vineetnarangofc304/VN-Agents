import { useState, useEffect, createContext, useContext, useCallback } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const ax = axios.create({ baseURL: API, withCredentials: true });

const AuthCtx = createContext(null);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null=checking, false=not auth
  const [loading, setLoading] = useState(true);

  const checkAuth = useCallback(async () => {
    // Restore token from localStorage
    const savedToken = localStorage.getItem("crm_token");
    if (savedToken) {
      ax.defaults.headers.common["Authorization"] = `Bearer ${savedToken}`;
    }
    try {
      const { data } = await ax.get("/api/crm-auth/me");
      setUser(data);
    } catch {
      localStorage.removeItem("crm_token");
      delete ax.defaults.headers.common["Authorization"];
      setUser(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { checkAuth(); }, [checkAuth]);

  const login = async (email, password) => {
    const { data } = await ax.post("/api/crm-auth/login", { email, password });
    // Store token in localStorage for file uploads and cross-domain requests
    if (data.token) {
      localStorage.setItem("crm_token", data.token);
      ax.defaults.headers.common["Authorization"] = `Bearer ${data.token}`;
    }
    setUser(data);
    return data;
  };

  const logout = async () => {
    await ax.post("/api/crm-auth/logout");
    localStorage.removeItem("crm_token");
    delete ax.defaults.headers.common["Authorization"];
    setUser(false);
  };

  return (
    <AuthCtx.Provider value={{ user, loading, login, logout, refresh: checkAuth, ax }}>
      {children}
    </AuthCtx.Provider>
  );
}
