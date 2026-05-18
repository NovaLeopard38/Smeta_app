import axios from "axios";
import { API_URL, MATERIALS_PAGE_SIZE } from "./constants";

const authHeader = (token) => ({ headers: { Authorization: `Bearer ${token}` } });

export const login = (email, password) =>
  axios.post(`${API_URL}/auth/login`, { email, password });

export const register = (email, password) =>
  axios.post(`${API_URL}/auth/register`, { email, password });

export const getMe = (token) =>
  axios.get(`${API_URL}/auth/me`, authHeader(token));

export const getSmetas = (token) =>
  axios.get(`${API_URL}/smetas`, authHeader(token));

export const createSmeta = (token, data) =>
  axios.post(`${API_URL}/smetas`, data, authHeader(token));

export const updateSmeta = (token, smetaId, data) =>
  axios.patch(`${API_URL}/smetas/${smetaId}`, data, authHeader(token));

export const deleteSmeta = (token, smetaId) =>
  axios.delete(`${API_URL}/smetas/${smetaId}`, authHeader(token));

export const shareSmeta = (token, smetaId, data) =>
  axios.post(`${API_URL}/smetas/${smetaId}/share`, data, authHeader(token));

export const branchSmeta = (token, smetaId) =>
  axios.post(`${API_URL}/smetas/${smetaId}/branch`, {}, authHeader(token));

export const checkSmeta = (token, smetaId) =>
  axios.post(`${API_URL}/smetas/${smetaId}/check`, {}, authHeader(token));

export const createItem = (token, smetaId, data, materialId) =>
  axios.post(`${API_URL}/smetas/${smetaId}/items`, data, {
    ...authHeader(token),
    params: materialId ? { material_id: materialId } : undefined,
  });

export const updateItem = (token, smetaId, itemId, data) =>
  axios.patch(`${API_URL}/smetas/${smetaId}/items/${itemId}`, data, authHeader(token));

export const deleteItem = (token, smetaId, itemId) =>
  axios.delete(`${API_URL}/smetas/${smetaId}/items/${itemId}`, authHeader(token));

export const getMaterials = (token, params) =>
  axios.get(`${API_URL}/materials`, { ...authHeader(token), params });

export const createMaterial = (token, data) =>
  axios.post(`${API_URL}/materials`, data, authHeader(token));

export const importMaterials = (token, formData) =>
  axios.post(`${API_URL}/materials/import`, formData, authHeader(token));

export const importMaterialsAI = (token, formData) =>
  axios.post(`${API_URL}/materials/import-ai`, formData, authHeader(token));

export const getSections = (token) =>
  axios.get(`${API_URL}/sections`, authHeader(token));

export const getAISettings = (token) =>
  axios.get(`${API_URL}/settings/ai`, authHeader(token));

export const saveAISettings = (token, data) =>
  axios.post(`${API_URL}/settings/ai`, data, authHeader(token));

export const getModels = (token) =>
  axios.get(`${API_URL}/settings/ai/models`, authHeader(token));

export const sendAICommand = (token, data) =>
  axios.post(`${API_URL}/ai/command`, data, authHeader(token));

export const getUsers = (token) =>
  axios.get(`${API_URL}/admin/users`, authHeader(token));

export const updateUser = (token, userId, data) =>
  axios.patch(`${API_URL}/admin/users/${userId}`, data, authHeader(token));

export const deleteUser = (token, userId) =>
  axios.delete(`${API_URL}/admin/users/${userId}`, authHeader(token));

export const getUserSmetas = (token, userId) =>
  axios.get(`${API_URL}/admin/users/${userId}/smetas`, authHeader(token));

export const getSmetaAccess = (token, smetaId) =>
  axios.get(`${API_URL}/admin/smetas/${smetaId}/access`, authHeader(token));

export const revokeAccess = (token, smetaId, userId) =>
  axios.delete(`${API_URL}/admin/smetas/${smetaId}/access/${userId}`, authHeader(token));

export const exportExcelUrl = (smetaId, token) =>
  `${API_URL}/smetas/${smetaId}/export.xlsx?token=${encodeURIComponent(token)}`;

export const printSmetaUrl = (smetaId, token) =>
  `${API_URL}/smetas/${smetaId}/print?token=${encodeURIComponent(token)}`;
