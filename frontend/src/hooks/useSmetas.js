import { useState, useEffect } from "react";
import * as api from "../api";
import { emptyItem, emptySmetaDetails, API_URL } from "../constants";
import { formatError } from "./useAuth";

export function useSmetas(authToken, currentUser, setMessage, setError) {
  const [smetas, setSmetas] = useState([]);
  const [selectedSmetaId, setSelectedSmetaId] = useState("");
  const [smetaName, setSmetaName] = useState("");
  const [smetaDetails, setSmetaDetails] = useState(emptySmetaDetails);
  const [shareForm, setShareForm] = useState({ email: "", permission: "view" });
  const [expandedSmetaIds, setExpandedSmetaIds] = useState({});
  const [itemForm, setItemForm] = useState(emptyItem);
  const [itemDrafts, setItemDrafts] = useState({});
  const [itemSuggestions, setItemSuggestions] = useState([]);
  const [expandedItems, setExpandedItems] = useState({});
  const [quantityByMaterial, setQuantityByMaterial] = useState({});

  const selectedSmeta = smetas.find(smeta => smeta.id === Number(selectedSmetaId));

  useEffect(() => {
    if (!selectedSmetaId || smetas.length === 0) {
      return;
    }
    const byId = new Map(smetas.map(smeta => [smeta.id, smeta]));
    const nextExpanded = {};
    let current = byId.get(Number(selectedSmetaId));
    while (current?.parent_id) {
      nextExpanded[Number(current.parent_id)] = true;
      current = byId.get(Number(current.parent_id));
    }
    if (Object.keys(nextExpanded).length > 0) {
      setExpandedSmetaIds(currentExpanded => ({ ...currentExpanded, ...nextExpanded }));
    }
  }, [selectedSmetaId, smetas]);

  useEffect(() => {
    if (selectedSmeta) {
      setSmetaDetails({
        name: selectedSmeta.name || "",
        parent_id: selectedSmeta.parent_id || null,
        customer_name: selectedSmeta.customer_name || "",
        customer_details: selectedSmeta.customer_details || "",
        contractor_name: selectedSmeta.contractor_name || "",
        contractor_details: selectedSmeta.contractor_details || "",
        approver_name: selectedSmeta.approver_name || "",
        approver_details: selectedSmeta.approver_details || "",
        tax_mode: selectedSmeta.tax_mode || "none",
        tax_rate: selectedSmeta.tax_rate || 0,
        section_adjustments: selectedSmeta.section_adjustments || {},
      });
    } else {
      setSmetaDetails(emptySmetaDetails);
    }
    setItemDrafts({});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSmetaId]);

  useEffect(() => {
    if (!authToken || activePage() !== "smetas") {
      setItemSuggestions([]);
      return undefined;
    }
    const query = itemForm.name.trim();
    if (query.length < 2) {
      setItemSuggestions([]);
      return undefined;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await api.getMaterials(authToken, {
          q: query,
          item_type: "all",
          limit: 8,
        });
        setItemSuggestions(normalizeMaterialsResponse(res.data).items);
      } catch (err) {
        setItemSuggestions([]);
      }
    }, 180);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authToken, itemForm.name]);

  // This will be set by the parent
  let activePage = () => "smetas";
  const setActivePageGetter = (fn) => { activePage = fn; };

  const normalizeMaterialsResponse = (data) => {
    if (Array.isArray(data)) {
      return { items: data, total: data.length, has_more: false };
    }
    return {
      items: data?.items || [],
      total: data?.total ?? (data?.items || []).length,
      has_more: Boolean(data?.has_more),
    };
  };

  const updateSelectedSmeta = (updatedSmeta) => {
    setSmetas(current => current.map(smeta => smeta.id === updatedSmeta.id ? updatedSmeta : smeta));
  };

  const runAction = async (action, successText) => {
    setError("");
    setMessage("");
    try {
      const actionMessage = await action();
      setMessage(actionMessage || successText);
    } catch (err) {
      setError(formatError(err));
    }
  };

  const wholeQuantityInput = (value) => {
    const digits = String(value || "").replace(/\D/g, "");
    return digits ? String(Math.max(1, Number(digits))) : "";
  };

  const wholeQuantityValue = (value) => Math.max(1, parseInt(wholeQuantityInput(value) || "1", 10));

  const normalizeSmetaForSave = (details) => ({
    ...details,
    parent_id: details.parent_id || null,
    tax_rate: Number(details.tax_rate || 0),
    section_adjustments: Object.fromEntries(
      Object.entries(details.section_adjustments || {}).map(([section, percent]) => [
        section,
        Number(String(percent || 0).replace(",", ".")) || 0,
      ])
    ),
  });

  const calculatePreviewSmeta = (smeta, details) => {
    if (!smeta) {
      return { subtotal: 0, tax_amount: 0, total: 0, items: [] };
    }
    const adjustments = details.section_adjustments || {};
    const items = (smeta.items || []).map(item => {
      const section = item.section || "Оборудование";
      const percent = Number(String(adjustments[section] ?? 0).replace(",", ".")) || 0;
      const effectiveUnitPrice = Math.round((item.unit_price || 0) * (1 + percent / 100) * 100) / 100;
      const total = Math.round((item.quantity || 0) * effectiveUnitPrice * 100) / 100;
      return {
        ...item,
        effective_unit_price: effectiveUnitPrice,
        section_adjustment_percent: percent,
        total,
      };
    });
    const subtotal = Math.round(items.reduce((sum, item) => sum + item.total, 0) * 100) / 100;
    const taxRate = Number(details.tax_rate || 0);
    let taxAmount = 0;
    let total = subtotal;
    if (details.tax_mode === "vat_added" && taxRate > 0) {
      taxAmount = Math.round(subtotal * taxRate) / 100;
      total = Math.round((subtotal + taxAmount) * 100) / 100;
    } else if (details.tax_mode === "vat_included" && taxRate > 0) {
      taxAmount = Math.round((subtotal * taxRate / (100 + taxRate)) * 100) / 100;
    }
    return { ...smeta, ...details, items, subtotal, tax_amount: taxAmount, total };
  };

  const loadSmetas = async () => {
    const res = await api.getSmetas(authToken);
    setSmetas(res.data);
    if (!selectedSmetaId && res.data.length > 0) {
      setSelectedSmetaId(String(res.data[0].id));
    }
    return res.data;
  };

  const handleCreateSmeta = async () => {
    if (!smetaName.trim()) {
      setError("Введите название сметы");
      return;
    }
    await runAction(async () => {
      const res = await api.createSmeta(authToken, { name: smetaName });
      setSmetas(current => [res.data, ...current]);
      setSelectedSmetaId(String(res.data.id));
      setSmetaName("");
    }, "Смета создана");
  };

  const handleDeleteSmeta = async () => {
    if (!selectedSmeta) {
      setError("Смета не выбрана");
      return;
    }
    await runAction(async () => {
      await api.deleteSmeta(authToken, selectedSmeta.id);
      const next = smetas.filter(smeta => smeta.id !== selectedSmeta.id);
      setSmetas(next);
      setSelectedSmetaId(next.length > 0 ? String(next[0].id) : "");
    }, "Смета удалена");
  };

  const handleBranchSmeta = async () => {
    if (!selectedSmeta) {
      setError("Смета не выбрана");
      return;
    }
    await runAction(async () => {
      const res = await api.branchSmeta(authToken, selectedSmeta.id);
      setSmetas(current => [...current, res.data]);
      setSelectedSmetaId(String(res.data.id));
      return `Создана ветка «${res.data.name}»`;
    }, "Ветка сметы создана");
  };

  const handleSaveSmetaDetails = async () => {
    if (!selectedSmeta) {
      setError("Смета не выбрана");
      return;
    }
    if (!smetaDetails.name.trim()) {
      setError("Введите название сметы");
      return;
    }
    await runAction(async () => {
      const res = await api.updateSmeta(authToken, selectedSmeta.id, normalizeSmetaForSave(smetaDetails));
      updateSelectedSmeta(res.data);
    }, "Реквизиты сметы сохранены");
  };

  const handleShareSmeta = async (loadAdminData) => {
    if (!selectedSmeta) {
      setError("Смета не выбрана");
      return;
    }
    if (!shareForm.email.trim()) {
      setError("Введите email пользователя");
      return;
    }
    await runAction(async () => {
      const res = await api.shareSmeta(authToken, selectedSmeta.id, shareForm);
      setShareForm({ email: "", permission: "view" });
      if (loadAdminData) await loadAdminData();
      return `Доступ для ${res.data.email}: ${res.data.permission === "edit" ? "редактирование" : "просмотр"}`;
    }, "Доступ открыт");
  };

  const handleCheckSmeta = async (setAiResponse) => {
    if (!selectedSmeta) {
      setError("Смета не выбрана");
      return;
    }
    await runAction(async () => {
      const res = await api.checkSmeta(authToken, selectedSmeta.id);
      updateSelectedSmeta(res.data.smeta);
      const parts = [
        ...(res.data.results || []),
        ...(res.data.issues || []).map(issue => `Проверить: ${issue}`),
      ];
      setAiResponse(parts.join("\n"));
      return parts.length ? parts.join("\n") : "Смета проверена, замечаний нет";
    }, "Смета проверена");
  };

  const handleExportExcel = () => {
    if (!selectedSmeta) {
      setError("Смета не выбрана");
      return;
    }
    window.location.href = api.exportExcelUrl(selectedSmeta.id, authToken);
  };

  const handlePrintSmeta = () => {
    if (!selectedSmeta) {
      setError("Смета не выбрана");
      return;
    }
    window.open(api.printSmetaUrl(selectedSmeta.id, authToken), "_blank", "noopener,noreferrer");
  };

  const isWorkMaterial = (material) => material?.item_type === "work";

  const materialAddText = (material) =>
    isWorkMaterial(material) ? "Работа добавлена в смету" : "Оборудование добавлено, монтаж и пусконаладка проверены";

  const handleAddMaterialToSmeta = async (material) => {
    if (!selectedSmeta) {
      setError("Сначала создайте или выберите смету");
      return;
    }
    const quantity = wholeQuantityValue(quantityByMaterial[material.id]);
    await runAction(async () => {
      const res = await api.createItem(authToken, selectedSmeta.id, {
        name: material.name,
        characteristics: material.characteristics,
        section: material.item_type === "work" ? "Монтажные работы" : "Оборудование",
        unit: material.unit,
        quantity,
        unit_price: material.price,
        source: material.source,
      }, material.id);
      updateSelectedSmeta(res.data);
    }, materialAddText(material));
  };

  const handleAddSuggestedItem = async (material) => {
    if (!selectedSmeta) {
      setError("Сначала создайте или выберите смету");
      return;
    }
    const quantity = wholeQuantityValue(itemForm.quantity);
    await runAction(async () => {
      const res = await api.createItem(authToken, selectedSmeta.id, {
        name: material.name,
        characteristics: material.characteristics,
        section: material.item_type === "work" ? "Монтажные работы" : "Оборудование",
        unit: material.unit,
        quantity,
        unit_price: material.price,
        source: material.source,
      }, material.id);
      updateSelectedSmeta(res.data);
      setItemForm(emptyItem);
      setItemSuggestions([]);
    }, materialAddText(material));
  };

  const handleAddCustomItem = async () => {
    if (!selectedSmeta) {
      setError("Сначала создайте или выберите смету");
      return;
    }
    if (!itemForm.name.trim() || itemForm.unit_price === "") {
      setError("Заполните название и цену позиции");
      return;
    }
    await runAction(async () => {
      const res = await api.createItem(authToken, selectedSmeta.id, {
        ...itemForm,
        quantity: wholeQuantityValue(itemForm.quantity),
        unit_price: Number(itemForm.unit_price),
      });
      updateSelectedSmeta(res.data);
      setItemForm(emptyItem);
    }, "Позиция добавлена");
  };

  const handleDeleteItem = async (itemId) => {
    await runAction(async () => {
      const res = await api.deleteItem(authToken, selectedSmeta.id, itemId);
      updateSelectedSmeta(res.data);
    }, "Позиция удалена");
  };

  const handleUpdateItemNumber = async (item, field, value) => {
    const normalizedValue = String(value ?? "").replace(",", ".").trim();
    const numberValue = field === "quantity" ? wholeQuantityValue(normalizedValue) : Number(normalizedValue);
    if (!selectedSmeta || Number.isNaN(numberValue) || numberValue < 0) {
      return;
    }
    const payload = {
      item_type: item.item_type || "manual",
      section: item.section || "Прочее",
      name: item.name,
      characteristics: item.characteristics || "",
      unit: item.unit || "",
      quantity: field === "quantity" ? Math.max(1, numberValue) : item.quantity,
      unit_price: field === "unit_price" ? numberValue : item.unit_price,
      source: item.source || "",
    };
    await runAction(async () => {
      const res = await api.updateItem(authToken, selectedSmeta.id, item.id, payload);
      updateSelectedSmeta(res.data);
      return "Позиция обновлена";
    }, "Позиция обновлена");
  };

  const updateItemDraft = (item, field, value) => {
    setItemDrafts(current => ({
      ...current,
      [`${item.id}:${field}`]: value,
    }));
  };

  const getItemDraft = (item, field, fallback) => {
    const key = `${item.id}:${field}`;
    return Object.prototype.hasOwnProperty.call(itemDrafts, key) ? itemDrafts[key] : fallback;
  };

  const clearItemDraft = (item, field) => {
    const key = `${item.id}:${field}`;
    setItemDrafts(current => {
      if (!Object.prototype.hasOwnProperty.call(current, key)) {
        return current;
      }
      const next = { ...current };
      delete next[key];
      return next;
    });
  };

  const commitItemDraft = async (item, field) => {
    const key = `${item.id}:${field}`;
    if (!Object.prototype.hasOwnProperty.call(itemDrafts, key)) {
      return;
    }
    const value = itemDrafts[key];
    if (value === "") {
      clearItemDraft(item, field);
      return;
    }
    await handleUpdateItemNumber(item, field, value);
    clearItemDraft(item, field);
  };

  const updateSmetaDetails = (field, value) => {
    setSmetaDetails(current => ({ ...current, [field]: value }));
  };

  const updateSectionAdjustment = (section, value) => {
    const normalized = String(value || "").replace(",", ".");
    setSmetaDetails(current => ({
      ...current,
      section_adjustments: {
        ...(current.section_adjustments || {}),
        [section]: normalized,
      },
    }));
  };

  const updateItemForm = (field, value) => {
    setItemForm(current => ({ ...current, [field]: value }));
  };

  const toggleItem = (itemId) => {
    setExpandedItems(current => ({ ...current, [itemId]: !current[itemId] }));
  };

  const previewSmeta = calculatePreviewSmeta(selectedSmeta, smetaDetails);

  return {
    smetas,
    setSmetas,
    selectedSmetaId,
    setSelectedSmetaId,
    selectedSmeta,
    smetaName,
    setSmetaName,
    smetaDetails,
    setSmetaDetails,
    shareForm,
    setShareForm,
    expandedSmetaIds,
    setExpandedSmetaIds,
    itemForm,
    setItemForm,
    itemDrafts,
    itemSuggestions,
    setItemSuggestions,
    expandedItems,
    quantityByMaterial,
    setQuantityByMaterial,
    previewSmeta,
    loadSmetas,
    handleCreateSmeta,
    handleDeleteSmeta,
    handleBranchSmeta,
    handleSaveSmetaDetails,
    handleShareSmeta,
    handleCheckSmeta,
    handleExportExcel,
    handlePrintSmeta,
    handleAddMaterialToSmeta,
    handleAddSuggestedItem,
    handleAddCustomItem,
    handleDeleteItem,
    handleUpdateItemNumber,
    updateItemDraft,
    getItemDraft,
    clearItemDraft,
    commitItemDraft,
    updateSmetaDetails,
    updateSectionAdjustment,
    updateItemForm,
    toggleItem,
    wholeQuantityInput,
    wholeQuantityValue,
    isWorkMaterial,
    materialAddText,
    normalizeMaterialsResponse,
    calculatePreviewSmeta,
    updateSelectedSmeta,
    setActivePageGetter,
  };
}
