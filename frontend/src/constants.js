export const API_URL = process.env.REACT_APP_API_URL || "/api";

export const DEFAULT_SECTIONS = [
  "Оборудование",
  "Монтажные работы",
  "Пусконаладочные работы",
  "Кабельные линии",
  "Материалы и расходники",
  "Доставка и логистика",
  "Проектирование",
  "Прочее",
];

export const EQUIPMENT_CATEGORY_FILTERS = [
  { id: "", label: "Все категории" },
  { id: "camera", label: "Камеры" },
  { id: "recorder", label: "Регистраторы" },
  { id: "cable", label: "Кабель" },
  { id: "network", label: "Сеть / PoE" },
  { id: "power", label: "Питание / ИБП" },
  { id: "access", label: "СКУД" },
  { id: "storage", label: "HDD" },
];

export const emptyMaterial = { name: "", characteristics: "", unit: "", price: "", source: "" };

export const emptyItem = {
  section: "Оборудование",
  name: "",
  characteristics: "",
  unit: "",
  quantity: 1,
  unit_price: "",
  source: "",
};

export const emptySmetaDetails = {
  parent_id: null,
  name: "",
  customer_name: "",
  customer_details: "",
  contractor_name: "",
  contractor_details: "",
  approver_name: "",
  approver_details: "",
  tax_mode: "none",
  tax_rate: 0,
  section_adjustments: {},
};

export const MATERIALS_PAGE_SIZE = 500;
