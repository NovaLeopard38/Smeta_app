export const money = (value) => new Intl.NumberFormat("ru-RU", {
  style: "currency",
  currency: "RUB",
  maximumFractionDigits: 2,
}).format(value || 0);

export const hasManualPrice = (item) =>
  item?.base_unit_price !== null &&
  item?.base_unit_price !== undefined &&
  Number(item?.unit_price || 0) !== Number(item?.base_unit_price || 0);

export const compactDetails = (text) => {
  const lines = String(text || "")
    .split(/\n|;|\. /)
    .map(line => line.trim())
    .filter(Boolean);
  return lines.slice(0, 1);
};

export const hasLongDetails = (item) => {
  const text = String(item.characteristics || "");
  return text.length > 90 || text.includes("\n") || text.includes(";") || text.includes(". ");
};

export const parentIdOf = (smeta) => Number(smeta?.parent_id || 0) || null;

export const isWorkMaterial = (material) => material?.item_type === "work";

export const wholeQuantityInput = (value) => {
  const digits = String(value || "").replace(/\D/g, "");
  return digits ? String(Math.max(1, Number(digits))) : "";
};

export const wholeQuantityValue = (value) => Math.max(1, parseInt(wholeQuantityInput(value) || "1", 10));

export const buildSmetaTree = (smetas, expandedSmetaIds, selectedSmetaId) => {
  const childrenByParent = smetas.reduce((acc, smeta) => {
    const parentId = parentIdOf(smeta);
    if (!parentId) return acc;
    return { ...acc, [parentId]: [...(acc[parentId] || []), smeta] };
  }, {});
  const roots = smetas
    .filter(smeta => !parentIdOf(smeta) || !smetas.some(parent => parent.id === parentIdOf(smeta)))
    .sort((a, b) => b.id - a.id);
  const walkSmetaTree = (node, depth = 0, visited = new Set()) => {
    if (visited.has(node.id)) return [];
    const nextVisited = new Set(visited);
    nextVisited.add(node.id);
    const children = (childrenByParent[node.id] || []).sort((a, b) => b.id - a.id);
    const hasChildren = children.length > 0;
    const isExpanded = Boolean(expandedSmetaIds[node.id]) || node.id === Number(selectedSmetaId);
    return [
      { smeta: node, depth, hasChildren, childCount: children.length, isExpanded },
      ...(isExpanded ? children.flatMap(child => walkSmetaTree(child, depth + 1, nextVisited)) : []),
    ];
  };
  return roots.flatMap(root => walkSmetaTree(root));
};

export const buildGroupedItems = (sections, previewSmeta) => {
  return (sections || []).map(section => ({
    section,
    items: previewSmeta?.items.filter(item => (item.section || "Оборудование") === section) || [],
  })).filter(group => group.items.length > 0 || ["Оборудование", "Монтажные работы", "Пусконаладочные работы"].includes(group.section));
};
