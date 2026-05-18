import React from "react";

function MaterialImport({
  file,
  setFile,
  importMode,
  setImportMode,
  supplierUrl,
  setSupplierUrl,
  handleUpload,
}) {
  return (
    <div className="import-box">
      <div className="segmented">
        <button
          className={importMode === "standard" ? "active" : ""}
          onClick={() => setImportMode("standard")}
        >
          Excel как таблица
        </button>
        <button
          className={importMode === "ai" ? "active" : ""}
          onClick={() => setImportMode("ai")}
        >
          AI: Excel/PDF/сайт
        </button>
      </div>
      <input
        type="file"
        accept={importMode === "ai" ? ".xlsx,.xls,.pdf" : ".xlsx,.xls"}
        onChange={e => setFile(e.target.files[0] || null)}
      />
      {importMode === "ai" && (
        <input
          type="url"
          placeholder="Или URL сайта поставщика"
          value={supplierUrl}
          onChange={e => setSupplierUrl(e.target.value)}
        />
      )}
      <button onClick={handleUpload}>
        {importMode === "ai" ? "Распарсить и добавить" : "Импорт Excel"}
      </button>
    </div>
  );
}

export default MaterialImport;
