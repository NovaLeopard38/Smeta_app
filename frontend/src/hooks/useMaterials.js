import { useState, useEffect } from "react";
import * as api from "../api";
import { DEFAULT_SECTIONS, emptyMaterial, MATERIALS_PAGE_SIZE } from "../constants";
import { formatError } from "./useAuth";

export function useMaterials(authToken, setMessage, setError) {
  const [materials, setMaterials] = useState([]);
  const [materialsTotal, setMaterialsTotal] = useState(0);
  const [materialsHasMore, setMaterialsHasMore] = useState(false);
  const [materialsLoadingMore, setMaterialsLoadingMore] = useState(false);
  const [materialQuery, setMaterialQuery] = useState("");
  const [materialType, setMaterialType] = useState("equipment");
  const [equipmentCategoryFilter, setEquipmentCategoryFilter] = useState("");
  const [technologyFilter, setTechnologyFilter] = useState("");
  const [megapixelsFilter, setMegapixelsFilter] = useState("");
  const [priceToFilter, setPriceToFilter] = useState("");
  const [file, setFile] = useState(null);
  const [importMode, setImportMode] = useState("standard");
  const [supplierUrl, setSupplierUrl] = useState("");
  const [materialForm, setMaterialForm] = useState(emptyMaterial);
  const [sections, setSections] = useState(DEFAULT_SECTIONS);

  useEffect(() => {
    if (materialType === "work" && equipmentCategoryFilter) {
      setEquipmentCategoryFilter("");
    }
  }, [materialType, equipmentCategoryFilter]);

  useEffect(() => {
    if (!authToken) {
      return undefined;
    }
    const timer = setTimeout(() => {
      loadMaterials();
    }, 220);
    return () => clearTimeout(timer);
  }, [authToken, materialQuery, materialType, equipmentCategoryFilter, technologyFilter, megapixelsFilter, priceToFilter]); // eslint-disable-line

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

  const loadMaterials = async (q = materialQuery, type = materialType, offset = 0, append = false) => {
    const res = await api.getMaterials(authToken, {
      q,
      item_type: type,
      category: equipmentCategoryFilter || undefined,
      technology: technologyFilter,
      megapixels: megapixelsFilter,
      price_to: priceToFilter || undefined,
      limit: MATERIALS_PAGE_SIZE,
      offset,
    });
    const payload = normalizeMaterialsResponse(res.data);
    setMaterials(current => append ? [...current, ...payload.items] : payload.items);
    setMaterialsTotal(payload.total);
    setMaterialsHasMore(payload.has_more);
    return payload.items;
  };

  const loadMoreMaterials = async () => {
    if (materialsLoadingMore || !materialsHasMore) {
      return;
    }
    setMaterialsLoadingMore(true);
    try {
      await loadMaterials(materialQuery, materialType, materials.length, true);
    } finally {
      setMaterialsLoadingMore(false);
    }
  };

  const loadAllMaterials = async () => {
    if (materialsLoadingMore || !materialsHasMore) {
      return;
    }
    setMaterialsLoadingMore(true);
    try {
      let loaded = materials.length;
      let hasMore = materialsHasMore;
      while (hasMore) {
        const res = await api.getMaterials(authToken, {
          q: materialQuery,
          item_type: materialType,
          category: equipmentCategoryFilter || undefined,
          technology: technologyFilter,
          megapixels: megapixelsFilter,
          price_to: priceToFilter || undefined,
          limit: MATERIALS_PAGE_SIZE,
          offset: loaded,
        });
        const payload = normalizeMaterialsResponse(res.data);
        setMaterials(current => [...current, ...payload.items]);
        setMaterialsTotal(payload.total);
        setMaterialsHasMore(payload.has_more);
        loaded += payload.items.length;
        hasMore = payload.has_more && payload.items.length > 0;
      }
    } finally {
      setMaterialsLoadingMore(false);
    }
  };

  const loadSections = async () => {
    try {
      const res = await api.getSections(authToken);
      setSections(res.data.sections || DEFAULT_SECTIONS);
    } catch (err) {
      setSections(DEFAULT_SECTIONS);
    }
  };

  const handleUpload = async (refreshData) => {
    if (!file && (importMode === "standard" || !supplierUrl.trim())) {
      setError("Выберите файл или укажите URL поставщика");
      return;
    }
    setError("");
    setMessage("");
    try {
      const formData = new FormData();
      if (file) {
        formData.append("file", file);
      }
      let res;
      if (importMode === "ai") {
        formData.append("url", supplierUrl);
        res = await api.importMaterialsAI(authToken, formData);
      } else {
        res = await api.importMaterials(authToken, formData);
      }
      await refreshData();
      setFile(null);
      setSupplierUrl("");
      const msg = importMode === "ai"
        ? `AI импортировал: ${res.data.imported}, пропущено: ${res.data.skipped}`
        : `Импортировано строк: ${res.data.imported}`;
      setMessage(msg);
    } catch (err) {
      setError(formatError(err));
    }
  };

  const handleCreateMaterial = async (refreshData) => {
    if (!materialForm.name.trim() || materialForm.price === "") {
      setError("Заполните название и цену материала");
      return;
    }
    setError("");
    setMessage("");
    try {
      await api.createMaterial(authToken, {
        ...materialForm,
        item_type: materialType === "work" ? "work" : "equipment",
        price: Number(materialForm.price),
      });
      setMaterialForm(emptyMaterial);
      await refreshData();
      setMessage("Материал добавлен");
    } catch (err) {
      setError(formatError(err));
    }
  };

  const updateMaterialForm = (field, value) => {
    setMaterialForm(current => ({ ...current, [field]: value }));
  };

  return {
    materials,
    setMaterials,
    materialsTotal,
    materialsHasMore,
    materialsLoadingMore,
    materialQuery,
    setMaterialQuery,
    materialType,
    setMaterialType,
    equipmentCategoryFilter,
    setEquipmentCategoryFilter,
    technologyFilter,
    setTechnologyFilter,
    megapixelsFilter,
    setMegapixelsFilter,
    priceToFilter,
    setPriceToFilter,
    file,
    setFile,
    importMode,
    setImportMode,
    supplierUrl,
    setSupplierUrl,
    materialForm,
    setMaterialForm,
    sections,
    setSections,
    loadMaterials,
    loadMoreMaterials,
    loadAllMaterials,
    loadSections,
    handleUpload,
    handleCreateMaterial,
    updateMaterialForm,
    normalizeMaterialsResponse,
  };
}
