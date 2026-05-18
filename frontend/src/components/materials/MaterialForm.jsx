import React from "react";

function MaterialForm({
  materialForm,
  updateMaterialForm,
  handleCreateMaterial,
}) {
  return (
    <div className="material-form">
      <input
        type="text"
        placeholder="Название"
        value={materialForm.name}
        onChange={e => updateMaterialForm("name", e.target.value)}
      />
      <input
        type="text"
        placeholder="Характеристики"
        value={materialForm.characteristics}
        onChange={e => updateMaterialForm("characteristics", e.target.value)}
      />
      <input
        type="text"
        placeholder="Ед."
        value={materialForm.unit}
        onChange={e => updateMaterialForm("unit", e.target.value)}
      />
      <input
        type="number"
        min="0"
        step="0.01"
        placeholder="Цена"
        value={materialForm.price}
        onChange={e => updateMaterialForm("price", e.target.value)}
      />
      <input
        type="text"
        placeholder="Источник"
        value={materialForm.source}
        onChange={e => updateMaterialForm("source", e.target.value)}
      />
      <button onClick={handleCreateMaterial}>Сохранить</button>
    </div>
  );
}

export default MaterialForm;
