import React, { createContext, useState, useContext, useEffect } from "react";
import axios from "axios";

const API = process.env.REACT_APP_API_URL || (window.location.hostname === "localhost" ? "http://localhost:8000" : "https://rag-play-ground.onrender.com");
const AuthContext = createContext();

export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(sessionStorage.getItem("token") || "");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (token) {
      axios.get(`${API}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
        .then(r => { setUser(r.data.user); setLoading(false); })
        .catch(() => { setToken(""); sessionStorage.removeItem("token"); setLoading(false); });
    } else { setLoading(false); }
  }, [token]);

  const login = async (roll_no, password) => {
    const r = await axios.post(`${API}/auth/login`, { roll_no, password });
    setToken(r.data.token); setUser(r.data.user);
    sessionStorage.setItem("token", r.data.token);
    return r.data;
  };

  const bypassLogin = async (role) => {
    const randomId = Math.floor(Math.random() * 1000000);
    const fakeToken = role === "student" ? `dummy_student_${randomId}` : `dummy_admin_${randomId}`;
    setToken(fakeToken);
    sessionStorage.setItem("token", fakeToken);
    try {
      const r = await axios.get(`${API}/auth/me`, { headers: { Authorization: `Bearer ${fakeToken}` } });
      setUser(r.data.user);
    } catch (err) {
      console.error("Bypass login failed:", err);
    }
  };

  const register = async (data) => {
    const r = await axios.post(`${API}/auth/register`, data);
    setToken(r.data.token); setUser(r.data.user);
    sessionStorage.setItem("token", r.data.token);
    return r.data;
  };

  const logout = () => { setToken(""); setUser(null); sessionStorage.removeItem("token"); };

  const authHeaders = { headers: { Authorization: `Bearer ${token}` } };

  return (
    <AuthContext.Provider value={{ user, token, login, register, logout, bypassLogin, loading, authHeaders, API }}>
      {children}
    </AuthContext.Provider>
  );
}
