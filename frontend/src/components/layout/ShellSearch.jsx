import React from "react";

function ShellSearch({
  shellSearch,
  setShellSearch,
  shellSearchFocused,
  setShellSearchFocused,
  shellHasResults,
  smetaSearchResults,
  shellSearchSuggestions,
  handleShellSearchKeyDown,
  handleShellSmetaOpen,
  handleShellSuggestionOpen,
  handleShellSuggestionAdd,
  parentIdOf,
  isWorkMaterial,
  money,
}) {
  return (
    <div className="topbar-search-wrap">
      <label className="topbar-search">
        <span className="search-icon" aria-hidden="true">{"\u2315"}</span>
        <input
          type="text"
          placeholder="Поиск оборудования, работ, кабеля..."
          value={shellSearch}
          onChange={e => setShellSearch(e.target.value)}
          onFocus={() => setShellSearchFocused(true)}
          onBlur={() => setTimeout(() => setShellSearchFocused(false), 120)}
          onKeyDown={handleShellSearchKeyDown}
        />
        <kbd>Enter</kbd>
      </label>
      {shellSearchFocused && shellSearch.trim().length >= 2 && shellHasResults && (
        <div className="inline-suggestions shell-search-dropdown" onMouseDown={e => e.preventDefault()}>
          {smetaSearchResults.length > 0 && (
            <div className="shell-result-group">
              <div className="suggestions-header">
                <strong>Сметы</strong>
                <span>По названию, реквизитам и позициям</span>
              </div>
              {smetaSearchResults.map(smeta => (
                <button key={smeta.id} className="shell-smeta-row" onClick={() => handleShellSmetaOpen(smeta)}>
                  <span>{smeta.name}</span>
                  <em>{parentIdOf(smeta) ? `ветка от #${parentIdOf(smeta)}` : `${smeta.items?.length || 0} позиций`}</em>
                  <strong>{money(smeta.total)}</strong>
                </button>
              ))}
            </div>
          )}
          {shellSearchSuggestions.length > 0 && (
            <div className="shell-result-group">
              <div className="suggestions-header">
                <strong>Позиции базы</strong>
                <span>Enter откроет весь список в прайсах</span>
              </div>
              {shellSearchSuggestions.map(material => (
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
                  <div className="suggestion-actions">
                    <button className="ghost" onClick={() => handleShellSuggestionOpen(material)}>В прайсы</button>
                    <button className="ghost" onClick={() => handleShellSuggestionAdd(material)}>
                      {isWorkMaterial(material) ? "В смету" : "В смету + работы"}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default ShellSearch;
