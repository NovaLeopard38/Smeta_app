/**
 * Custom hook for authentication state management.
 * Extracted from App.jsx to be reused across components.
 */
import { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API_URL = process.env.REACT_APP_API_URL || "/api";

export function useAuth() {
  const [authToken, setAuthToken] = useState(() => localStorage.getItem("smeta_token") || "");
  const [currentUser, setCurrentUser] = useState(null);

  useEffect(() => {
    if (authToken) {
      axios.defaults.headers.common.Authorization = `Bearer ${authToken}`;
      localStorage.setItem("smeta_token", authToken);
    } else {
      delete axios.defaults.headers.common.Authorization;
      localStorage.removeItem("smeta_token");
    }
  }, [authToken]);

  useEffect(() => {
    if (!authToken) return;
    axios.get(`${API_URL}/auth/me`)
      .then(res => setCurrentUser(res.data))
      .catch(() => {
        setAuthToken("");
        setCurrentUser(null);
      });
  }, [authToken]);

  const login = useCallback(async (email, password) => {
    const res = await axios.post(`${API_URL}/auth/login`, { email, password });
    setAuthToken(res.data.access_token);
    setCurrentUser(res.data.user);
    return res.data;
  }, []);

  const register = useCallback(async (email, password) => {
    const res = await axios.post(`${API_URL}/auth/register`, { email, password });
    setAuthToken(res.data.access_token);
    setCurrentUser(res.data.user);
    return res.data;
  }, []);

  const logout = useCallback(() => {
    setAuthToken("");
    setCurrentUser(null);
  }, []);

  return {
    authToken,
    currentUser,
    isAuthenticated: Boolean(authToken),
    isAdmin: Boolean(currentUser?.is_admin),
    login,
    register,
    logout,
  };
}
