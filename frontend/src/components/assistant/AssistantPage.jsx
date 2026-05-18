import React from "react";

function AssistantPage({
  selectedSmeta,
  previewSmeta,
  aiPrompt,
  setAiPrompt,
  aiResponse,
  handleAiRequest,
  money,
}) {
  return (
    <section className="page-content assistant-page">
      <section className="panel assistant">
        <h2>AI Ассистент</h2>
        {selectedSmeta && (
          <p className="muted">Текущая смета: {selectedSmeta.name} {"\u00B7"} {money(previewSmeta?.total || 0)}</p>
        )}
        <p className="muted">Настройки AI доступны только администратору.</p>
        <textarea
          placeholder="Например: создай смету 'СКУД офис', добавь монтажные работы 12 часов по 1800 или удали позицию #5"
          value={aiPrompt}
          onChange={e => setAiPrompt(e.target.value)}
        />
        <button onClick={handleAiRequest}>Выполнить</button>
        {aiResponse && <div className="assistant-answer">{aiResponse}</div>}
      </section>
    </section>
  );
}

export default AssistantPage;
