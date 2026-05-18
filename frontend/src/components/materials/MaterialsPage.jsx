import React from "react";
import MaterialImport from "./MaterialImport";
import MaterialForm from "./MaterialForm";
import MaterialCard from "./MaterialCard";
import { EQUIPMENT_CATEGORY_FILTERS, MATERIALS_PAGE_SIZE } from "../../constants";

function MaterialsPage({
  materials,
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
  updateMaterialForm,
  handleUpload,
  handleCreateMaterial,
  loadMoreMaterials,
  loadAllMaterials,
  quantityByMaterial,
  setQuantityByMaterial,
  handleAddMaterialToSmeta,
  money,
  isWorkMaterial,
  wholeQuantityInput,
}) {
  return (
    <section className="page-content prices-page">
      <section className="panel">
        <div className="section-title">
          <div>
            <h2>Материалы</h2>
            <p>Показано {materials.length} из {materialsTotal || materials.length} релевантных позиций</p>
          </div>
        </div>

        <MaterialImport
          file={file}
          setFile={setFile}
          importMode={importMode}
          setImportMode={setImportMode}
          supplierUrl={supplierUrl}
          setSupplierUrl={setSupplierUrl}
          handleUpload={handleUpload}
        />

        <div className="catalog-tools">
          <div className="segmented">
            <button
              className={materialType === "equipment" ? "active" : ""}
              onClick={() => setMaterialType("equipment")}
            >
              Оборудование
            </button>
            <button
              className={materialType === "work" ? "active" : ""}
              onClick={() => setMaterialType("work")}
            >
              Работы
            </button>
            <button
              className={materialType === "all" ? "active" : ""}
              onClick={() => setMaterialType("all")}
            >
              Всё
            </button>
          </div>
          <input
            type="search"
            placeholder="Поиск: камера, кабель, монтаж, Optimus..."
            value={materialQuery}
            onChange={e => setMaterialQuery(e.target.value)}
          />
        </div>

        <div className="smart-filters">
          <select value={technologyFilter} onChange={e => setTechnologyFilter(e.target.value)}>
            <option value="">Любая технология</option>
            <option value="ip">IP</option>
            <option value="ahd">AHD</option>
            <option value="poe">PoE</option>
          </select>
          <select value={megapixelsFilter} onChange={e => setMegapixelsFilter(e.target.value)}>
            <option value="">Любое разрешение</option>
            <option value="2">2 Мп</option>
            <option value="4">4 Мп</option>
            <option value="5">5 Мп</option>
            <option value="8">8 Мп</option>
          </select>
          <input
            type="number"
            min="0"
            step="100"
            placeholder="Цена до"
            value={priceToFilter}
            onChange={e => setPriceToFilter(e.target.value)}
          />
          <button
            className="ghost"
            onClick={() => {
              setTechnologyFilter("");
              setMegapixelsFilter("");
              setPriceToFilter("");
              setEquipmentCategoryFilter("");
            }}
          >
            Сбросить
          </button>
        </div>

        {materialType !== "work" && (
          <div className="equipment-filters" aria-label="Фильтры оборудования">
            {EQUIPMENT_CATEGORY_FILTERS.map(category => (
              <button
                key={category.id || "all"}
                className={equipmentCategoryFilter === category.id ? "active" : ""}
                onClick={() => setEquipmentCategoryFilter(category.id)}
              >
                {category.label}
              </button>
            ))}
          </div>
        )}

        <MaterialForm
          materialForm={materialForm}
          updateMaterialForm={updateMaterialForm}
          handleCreateMaterial={handleCreateMaterial}
        />

        <div className="materials-list">
          {materials.map(material => (
            <MaterialCard
              key={material.id}
              material={material}
              quantityByMaterial={quantityByMaterial}
              setQuantityByMaterial={setQuantityByMaterial}
              handleAddMaterialToSmeta={handleAddMaterialToSmeta}
              money={money}
              isWorkMaterial={isWorkMaterial}
              wholeQuantityInput={wholeQuantityInput}
            />
          ))}
        </div>
        {materialsHasMore && (
          <div className="load-more-row">
            <button className="ghost load-more" disabled={materialsLoadingMore} onClick={loadMoreMaterials}>
              {materialsLoadingMore ? "Загружаю..." : `Показать ещё ${Math.min(MATERIALS_PAGE_SIZE, Math.max(0, materialsTotal - materials.length))}`}
            </button>
            <button className="ghost load-more" disabled={materialsLoadingMore} onClick={loadAllMaterials}>
              Показать все {Math.max(0, materialsTotal - materials.length)}
            </button>
          </div>
        )}
      </section>
    </section>
  );
}

export default MaterialsPage;
