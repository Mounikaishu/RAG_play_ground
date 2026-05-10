import React, { createContext, useState, useContext, useEffect } from "react";
import axios from "axios";

const API = process.env.REACT_APP_API_URL || "http://localhost:8000";
const AuthContext = createContext();

export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem("token") || "");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (token) {
      axios.get(`${API}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
        .then(r => { setUser(r.data.user); setLoading(false); })
        .catch(() => { setToken(""); localStorage.removeItem("token"); setLoading(false); });
    } else { setLoading(false); }
  }, [token]);

  const login = async (roll_no, password) => {
    const r = await axios.post(`${API}/auth/login`, { roll_no, password });
    setToken(r.data.token); setUser(r.data.user);
    localStorage.setItem("token", r.data.token);
    return r.data;
  };

  const register = async (data) => {
    const r = await axios.post(`${API}/auth/register`, data);
    setToken(r.data.token); setUser(r.data.user);
    localStorage.setItem("token", r.data.token);
    return r.data;
  };

  const logout = () => { setToken(""); setUser(null); localStorage.removeItem("token"); };

  const authHeaders = { headers: { Authorization: `Bearer ${token}` } };

  return (
    <AuthContext.Provider value={{ user, token, login, register, logout, loading, authHeaders, API }}>
      {children}
    </AuthContext.Provider>
  );
}
