import { Fragment } from "react";
import SmetaDetails from "./SmetaDetails";

function SmetaEditor({
  selectedSmeta,
  previewSmeta,
  groupedItems,
  sections,
  smetaDetails,
  updateSmetaDetails,
  updateSectionAdjustment,
  handleSaveSmetaDetails,
  shareForm,
  setShareForm,
  handleShareSmeta,
  handleBranchSmeta,
  handleCheckSmeta,
  handleExportExcel,
  handlePrintSmeta,
  handleDeleteSmeta,
  itemForm,
  updateItemForm,
  itemSuggestions,
  handleAddCustomItem,
  handleAddSuggestedItem,
  handleDeleteItem,
  updateItemDraft,
  getItemDraft,
  commitItemDraft,
  expandedItems,
  toggleItem,
  aiPrompt,
  setAiPrompt,
  handleAiRequest,
  adminAccess,
  adminBusy,
  handleRevokeAccess,
  currentUser,
  money,
  isWorkMaterial,
  wholeQuantityInput,
  hasManualPrice,
  compactDetails,
  hasLongDetails,
}) {
  return (
    <section className="panel estimate-panel">
      <div className="section-title">
        <div>
          <h2>{selectedSmeta?.name || "Смета не выбрана"}</h2>
          <p>{selectedSmeta ? `${selectedSmeta.items.length} позиций` : "Выберите смету слева"}</p>
        </div>
        <div className="title-actions">
          <strong>{money(previewSmeta?.total || 0)}</strong>
          {selectedSmeta && (
            <>
              <button className="ghost" onClick={handleBranchSmeta}>Сделать ветку</button>
              <button className="ghost" onClick={handleCheckSmeta}>Проверить смету</button>
              <button className="ghost" onClick={handleExportExcel}>Excel</button>
              <button className="ghost" onClick={handlePrintSmeta}>PDF</button>
              <button className="ghost danger" onClick={handleDeleteSmeta}>Удалить смету</button>
            </>
          )}
        </div>
      </div>

      {selectedSmeta && (
        <div className="estimate-commandbar">
          <nav className="estimate-section-tabs" aria-label="Разделы сметы">
            {groupedItems.map(group => (
              <button
                key={group.section}
                className={itemForm.section === group.section ? "estimate-section-tab active" : "estimate-section-tab"}
                onClick={() => updateItemForm("section", group.section)}
                title={`Добавлять новые позиции в раздел \u00AB${group.section}\u00BB`}
              >
                <span>{group.section}</span>
                <strong>{money(group.items.reduce((sum, item) => sum + item.total, 0))}</strong>
              </button>
            ))}
          </nav>
          <div className="estimate-ai-bar">
            <span>AI</span>
            <input
              type="text"
              placeholder="Например: добавь 2 камеры или проверь монтаж"
              value={aiPrompt}
              onChange={e => setAiPrompt(e.target.value)}
              onKeyDown={e => {
                if (e.key === "Enter") {
                  handleAiRequest();
                }
              }}
            />
            <button className="ghost" onClick={handleAiRequest}>Выполнить</button>
          </div>
        </div>
      )}

      <SmetaDetails
        selectedSmeta={selectedSmeta}
        smetaDetails={smetaDetails}
        updateSmetaDetails={updateSmetaDetails}
        handleSaveSmetaDetails={handleSaveSmetaDetails}
        shareForm={shareForm}
        setShareForm={setShareForm}
        handleShareSmeta={handleShareSmeta}
        previewSmeta={previewSmeta}
        money={money}
      />

      {selectedSmeta && currentUser?.is_admin && (
        <div className="revision-panel">
          <div className="section-title compact">
            <div>
              <h2>Доступ к смете</h2>
              <p>{selectedSmeta.name}</p>
            </div>
          </div>
          {adminAccess.length > 0 ? (
            <>
              <p className="muted">К этой смете есть доступ у {adminAccess.length} пользователей.</p>
              <div className="admin-access-list">
                {adminAccess.map(access => (
                  <div key={access.id} className="admin-access-row">
                    <div>
                      <strong>{access.email}</strong>
                      <span>{access.permission === "edit" ? "редактирование" : "просмотр"}</span>
                    </div>
                    <button className="ghost danger" disabled={adminBusy} onClick={() => handleRevokeAccess(access.user_id)}>
                      Отозвать
                    </button>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="muted">У этой сметы пока нет расшаренных доступов.</p>
          )}
        </div>
      )}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Позиция</th>
              <th>Кол-во</th>
              <th>Цена</th>
              <th>Сумма</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {groupedItems.map(group => (
              <Fragment key={group.section}>
                <tr className="section-row">
                  <td colSpan="5">
                    <strong>{group.section}</strong>
                    <label className="section-percent">
                      <input
                        type="number"
                        step="1"
                        value={(smetaDetails.section_adjustments || {})[group.section] ?? 0}
                        onChange={e => updateSectionAdjustment(group.section, e.target.value)}
                      />
                      %
                    </label>
                    <span>{money(group.items.reduce((sum, item) => sum + item.total, 0))}</span>
                  </td>
                </tr>
                {group.items.map(item => (
                  <tr key={item.id}>
                    <td>
                      <div className="item-cardline">
                        <strong>{item.name}</strong>
                        {hasLongDetails(item) && (
                          <button className="icon-button" onClick={() => toggleItem(item.id)}>
                            {expandedItems[item.id] ? "Свернуть" : "Детали"}
                          </button>
                        )}
                      </div>
                      <div className={expandedItems[item.id] ? "item-details expanded" : "item-details"}>
                        {!expandedItems[item.id] && compactDetails(item.characteristics).map((line, index) => (
                          <span key={index}>{line}</span>
                        ))}
                        {expandedItems[item.id] && <small>{item.characteristics || "Описание не заполнено"}</small>}
                        <em>{item.unit || "ед."} {"\u00B7"} {item.source || "без источника"}</em>
                        {hasManualPrice(item) && (
                          <span
                            className="price-badge"
                            title={`Цена из базы: ${money(item.base_unit_price)}`}
                          >
                            ручная цена
                          </span>
                        )}
                        {item.section_adjustment_percent !== 0 && (
                          <em>Цена с корректировкой раздела: {money(item.effective_unit_price)}</em>
                        )}
                      </div>
                    </td>
                    <td>
                      <input
                        className="table-number"
                        type="text"
                        inputMode="numeric"
                        pattern="[0-9]*"
                        value={getItemDraft(item, "quantity", String(Math.round(item.quantity || 1)))}
                        onChange={e => updateItemDraft(item, "quantity", e.target.value)}
                        onBlur={() => commitItemDraft(item, "quantity")}
                      />
                    </td>
                    <td>
                      <input
                        className="table-number price"
                        type="text"
                        inputMode="decimal"
                        value={getItemDraft(item, "unit_price", String(item.unit_price ?? 0))}
                        onChange={e => updateItemDraft(item, "unit_price", e.target.value)}
                        onBlur={() => commitItemDraft(item, "unit_price")}
                      />
                    </td>
                    <td>{money(item.total)}</td>
                    <td>
                      <button className="ghost danger" onClick={() => handleDeleteItem(item.id)}>
                        Удалить
                      </button>
                    </td>
                  </tr>
                ))}
              </Fragment>
            ))}
            {(!selectedSmeta || selectedSmeta.items.length === 0) && (
              <tr>
                <td colSpan="5" className="empty">Добавьте материалы или ручную позицию.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="custom-item">
        <select
          value={itemForm.section}
          onChange={e => updateItemForm("section", e.target.value)}
        >
          {sections.map(section => <option key={section} value={section}>{section}</option>)}
        </select>
        <input
          type="text"
          placeholder="Ручная позиция"
          value={itemForm.name}
          onChange={e => updateItemForm("name", e.target.value)}
        />
      </div>
      <input
        type="text"
        placeholder="Характеристики"
        value={itemForm.characteristics}
        onChange={e => updateItemForm("characteristics", e.target.value)}
      />
      <input
        type="text"
        placeholder="Ед."
        value={itemForm.unit}
        onChange={e => updateItemForm("unit", e.target.value)}
      />
      <input
        type="number"
        min="1"
        step="1"
        inputMode="numeric"
        pattern="[0-9]*"
        placeholder="Кол-во"
        value={itemForm.quantity}
        onChange={e => updateItemForm("quantity", wholeQuantityInput(e.target.value))}
      />
      <input
        type="number"
        min="0"
        step="0.01"
        placeholder="Цена"
        value={itemForm.unit_price}
        onChange={e => updateItemForm("unit_price", e.target.value)}
      />
      <button onClick={handleAddCustomItem}>Добавить</button>
      {itemSuggestions.length > 0 && itemForm.name.trim().length >= 2 && (
        <div className="inline-suggestions form-suggestions">
          <div className="suggestions-header">
            <strong>Найдено в базе</strong>
            <span>Можно вставить готовую позицию без перехода в прайсы</span>
          </div>
          {itemSuggestions.map(material => (
            <div key={material.id} className="suggestion-row">
              <div>
                <div className="suggestion-title">
                  <strong>{material.name}</strong>
                  <em>{isWorkMaterial(material) ? "работа" : "оборудование"}</em>
                </div>
                <span>
                  {material.characteristics ? `${material.characteristics} \u00B7 ` : ""}
                  {material.unit || "ед."} {"\u00B7"} {material.source || "без источника"}
                </span>
              </div>
              <strong>{money(material.price)}</strong>
              <button className="ghost" onClick={() => handleAddSuggestedItem(material)}>
                {isWorkMaterial(material) ? "Вставить" : "Вставить + работы"}
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export default SmetaEditor;
