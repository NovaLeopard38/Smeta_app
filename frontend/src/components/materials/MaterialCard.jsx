import React from "react";

function MaterialCard({
  material,
  quantityByMaterial,
  setQuantityByMaterial,
  handleAddMaterialToSmeta,
  money,
  isWorkMaterial,
  wholeQuantityInput,
}) {
  return (
    <div className="material-row">
      <div>
        <strong>{material.name}</strong>
        <span>
          {material.characteristics ? `${material.characteristics} \u00B7 ` : ""}
          {material.unit || "ед."} {"\u00B7"} {material.source || "без источника"}
        </span>
      </div>
      <strong>{money(material.price)}</strong>
      <input
        type="number"
        min="1"
        step="1"
        inputMode="numeric"
        pattern="[0-9]*"
        value={quantityByMaterial[material.id] || 1}
        onChange={e => setQuantityByMaterial(current => ({
          ...current,
          [material.id]: wholeQuantityInput(e.target.value),
        }))}
      />
      <button className="ghost" onClick={() => handleAddMaterialToSmeta(material)}>
        {isWorkMaterial(material) ? "В смету" : "В смету + работы"}
      </button>
    </div>
  );
}

export default MaterialCard;
