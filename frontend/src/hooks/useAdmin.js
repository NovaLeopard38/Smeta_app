import { useState, useEffect } from "react";
import * as api from "../api";
import { formatError } from "./useAuth";

export function useAdmin(authToken, currentUser, setCurrentUser, selectedSmeta, setMessage, setError, handleLogout) {
  const [adminUsers, setAdminUsers] = useState([]);
  const [adminAccess, setAdminAccess] = useState([]);
  const [adminUserSmetas, setAdminUserSmetas] = useState([]);
  const [adminSelectedUserId, setAdminSelectedUserId] = useState("");
  const [adminBusy, setAdminBusy] = useState(false);

  const selectedAdminUser = adminUsers.find(user => String(user.id) === String(adminSelectedUserId));

  useEffect(() => {
    if (!authToken || !currentUser?.is_admin) {
      setAdminUsers([]);
      setAdminAccess([]);
      setAdminUserSmetas([]);
      setAdminSelectedUserId("");
      return;
    }
    loadAdminData();
  }, [authToken, currentUser?.is_admin, selectedSmeta?.id]); // eslint-disable-line

  const loadAdminData = async () => {
    if (!currentUser?.is_admin) return;
    try {
      const [usersRes, accessRes] = await Promise.all([
        api.getUsers(authToken),
        selectedSmeta
          ? api.getSmetaAccess(authToken, selectedSmeta.id)
          : Promise.resolve({ data: { access: [] } }),
      ]);
      const users = usersRes.data || [];
      setAdminUsers(users);
      const selectedId = adminSelectedUserId && users.some(user => String(user.id) === String(adminSelectedUserId))
        ? adminSelectedUserId
        : (users[0] ? String(users[0].id) : "");
      if (selectedId !== adminSelectedUserId) {
        setAdminSelectedUserId(selectedId);
      }
      setAdminAccess(accessRes.data?.access || []);
      if (selectedId) {
        const userSmetasRes = await api.getUserSmetas(authToken, selectedId);
        setAdminUserSmetas(userSmetasRes.data?.smetas || []);
      } else {
        setAdminUserSmetas([]);
      }
    } catch (err) {
      setError(formatError(err));
    }
  };

  const loadAdminUserSmetas = async (userId) => {
    if (!currentUser?.is_admin || !userId) {
      setAdminUserSmetas([]);
      return;
    }
    try {
      const res = await api.getUserSmetas(authToken, userId);
      setAdminUserSmetas(res.data?.smetas || []);
    } catch (err) {
      setAdminUserSmetas([]);
      setError(formatError(err));
    }
  };

  const handleToggleAdmin = async (targetUser) => {
    if (!currentUser?.is_admin || adminBusy) return;
    setAdminBusy(true);
    setError(""); setMessage("");
    try {
      const res = await api.updateUser(authToken, targetUser.id, { is_admin: !targetUser.is_admin });
      setAdminUsers(current => current.map(user => (user.id === res.data.id ? res.data : user)));
      if (targetUser.id === currentUser.id) setCurrentUser(res.data);
      await loadAdminData();
      setMessage(`${res.data.email}: ${res.data.is_admin ? "админ" : "обычный пользователь"}`);
    } catch (err) {
      setError(formatError(err));
    }
    setAdminBusy(false);
  };

  const handleSelectAdminUser = async (userId) => {
    const normalizedId = String(userId || "");
    setAdminSelectedUserId(normalizedId);
    await loadAdminUserSmetas(normalizedId);
  };

  const handleDeleteUser = async (targetUser) => {
    if (!currentUser?.is_admin || adminBusy) return;
    if (!window.confirm(`Удалить пользователя ${targetUser.email}?`)) return;
    setAdminBusy(true);
    setError(""); setMessage("");
    try {
      await api.deleteUser(authToken, targetUser.id);
      if (targetUser.id === currentUser.id) {
        handleLogout();
      } else {
        if (String(adminSelectedUserId) === String(targetUser.id)) {
          setAdminSelectedUserId("");
          setAdminUserSmetas([]);
        }
        await loadAdminData();
      }
      setMessage(`Пользователь ${targetUser.email} удалён`);
    } catch (err) {
      setError(formatError(err));
    }
    setAdminBusy(false);
  };

  const handleRevokeAccess = async (userId) => {
    if (!selectedSmeta || !currentUser?.is_admin || adminBusy) return;
    setAdminBusy(true);
    setError(""); setMessage("");
    try {
      await api.revokeAccess(authToken, selectedSmeta.id, userId);
      await loadAdminData();
      setMessage("Доступ отозван");
    } catch (err) {
      setError(formatError(err));
    }
    setAdminBusy(false);
  };

  return {
    adminUsers,
    adminAccess,
    adminUserSmetas,
    adminSelectedUserId,
    adminBusy,
    selectedAdminUser,
    loadAdminData,
    handleToggleAdmin,
    handleSelectAdminUser,
    handleDeleteUser,
    handleRevokeAccess,
  };
}
