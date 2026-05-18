import { useState, useEffect } from "react";
import axios from "axios";
import * as api from "../api";

export const formatError = (err) => {
  const detail = err.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail.map(item => item.msg || JSON.stringify(item)).join("; ");
  }
  if (detail && typeof detail === "object") {
    return detail.message || JSON.stringify(detail);
  }
  return detail || "Не удалось выполнить действие";
};

export function useAuth() {
  const [authToken, setAuthToken] = useState(() => localStorage.getItem("smeta_token") || "");
  const [currentUser, setCurrentUser] = useState(null);
  const [loginForm, setLoginForm] = useState({ email: "", password: "" });
  const [authMode, setAuthMode] = useState("login");

  useEffect(() => {
    if (authToken) {
      axios.defaults.headers.common.Authorization = `Bearer ${authToken}`;
      localStorage.setItem("smeta_token", authToken);
    } else {
      delete axios.defaults.headers.common.Authorization;
      localStorage.removeItem("smeta_token");
    }
  }, [authToken]);

  const handleLogin = async (setError, setMessage) => {
    setError("");
    setMessage("");
    try {
      const res = await api.login(loginForm.email, loginForm.password);
      setAuthToken(res.data.access_token);
      setCurrentUser(res.data.user);
      setLoginForm({ email: "", password: "" });
    } catch (err) {
      setError(formatError(err));
    }
  };

  const handleRegister = async (setError, setMessage) => {
    setError("");
    setMessage("");
    try {
      const res = await api.register(loginForm.email, loginForm.password);
      setAuthToken(res.data.access_token);
      setCurrentUser(res.data.user);
      setLoginForm({ email: "", password: "" });
    } catch (err) {
      setError(formatError(err));
    }
  };

  const handleLogout = () => {
    setAuthToken("");
    setCurrentUser(null);
  };

  return {
    authToken,
    setAuthToken,
    currentUser,
    setCurrentUser,
    loginForm,
    setLoginForm,
    authMode,
    setAuthMode,
    handleLogin,
    handleRegister,
    handleLogout,
  };
}
