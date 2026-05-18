/**
 * Custom hook for API calls with error formatting.
 * Extracted from App.jsx.
 */
import { useState, useCallback } from "react";

export function useApi() {
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const formatError = (err) => {
    const detail = err.response?.data?.detail;
    if (Array.isArray(detail)) {
      return detail.map(item => item.msg || JSON.stringify(item)).join("; ");
    }
    if (detail && typeof detail === "object") {
      return detail.message || JSON.stringify(detail);
    }
    return detail || "Не удалось выполнить действие";
  };

  const runAction = useCallback(async (action, successText) => {
    setError("");
    setMessage("");
    try {
      const actionMessage = await action();
      setMessage(actionMessage || successText);
    } catch (err) {
      setError(formatError(err));
    }
  }, []);

  const clearMessages = useCallback(() => {
    setMessage("");
    setError("");
  }, []);

  return { message, error, setMessage, setError, runAction, clearMessages, formatError };
}
