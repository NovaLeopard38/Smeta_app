import React from "react";

function SmetaList({
  smetas,
  smetaTree,
  selectedSmetaId,
  setSelectedSmetaId,
  expandedSmetaIds,
  setExpandedSmetaIds,
  smetaName,
  setSmetaName,
  handleCreateSmeta,
  money,
  parentIdOf,
}) {
  return (
    <aside className="panel smeta-sidebar">
      <h2>Сметы</h2>
      <div className="inline-form">
        <input
          type="text"
          placeholder="Новая смета"
          value={smetaName}
          onChange={e => setSmetaName(e.target.value)}
        />
        <button onClick={handleCreateSmeta}>Создать</button>
      </div>

      <div className="smeta-list">
        {smetaTree.map(({ smeta, depth, hasChildren, childCount, isExpanded }) => (
          <div
            key={smeta.id}
            className={`${smeta.id === Number(selectedSmetaId) ? "smeta-card active" : "smeta-card"} ${depth > 0 ? "branch" : ""} ${hasChildren ? "has-branches" : ""}`}
            style={{ marginLeft: depth ? `${Math.min(depth, 5) * 22}px` : undefined }}
          >
            <button
              className="smeta-card-main"
              onClick={() => {
                setSelectedSmetaId(String(smeta.id));
                if (hasChildren) {
                  setExpandedSmetaIds(current => ({ ...current, [smeta.id]: true }));
                }
              }}
            >
              <span>{depth > 0 ? `\u21B3 ${smeta.name}` : smeta.name}</span>
              {parentIdOf(smeta) && <em>Ветка от сметы #{parentIdOf(smeta)}</em>}
              {hasChildren && <em>{childCount} ветк{childCount === 1 ? "а" : childCount < 5 ? "и" : "ок"} {isExpanded ? "открыто" : "свернуто"}</em>}
              <strong>{money(smeta.total)}</strong>
            </button>
            {hasChildren && (
              <button
                className="branch-toggle"
                title={isExpanded ? "Свернуть ветки" : "Показать ветки"}
                onClick={() => setExpandedSmetaIds(current => ({ ...current, [smeta.id]: !isExpanded }))}
              >
                {isExpanded ? "-" : "+"}
              </button>
            )}
          </div>
        ))}
        {smetas.length === 0 && <p className="muted">Создайте первую смету.</p>}
      </div>
    </aside>
  );
}

export default SmetaList;
