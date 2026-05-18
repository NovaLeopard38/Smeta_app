import React from "react";

function AdminPage({
  currentUser,
  adminUsers,
  adminSelectedUserId,
  adminUserSmetas,
  adminBusy,
  selectedAdminUser,
  handleSelectAdminUser,
  handleToggleAdmin,
  handleDeleteUser,
  aiSettings,
  setAiSettings,
  apiKeyInput,
  setApiKeyInput,
  models,
  handleSaveAiSettings,
  handleLoadModels,
  handleSelectModel,
  modelPrice,
  money,
}) {
  return (
    <section className="panel admin-settings-panel">
      <div className="section-title">
        <div>
          <h2>Админ-настройки</h2>
          <p>AI, доступы и управление пользователями</p>
        </div>
        <div className="title-actions">
          <button className="ghost" onClick={handleLoadModels}>
            Список моделей
          </button>
          <button onClick={handleSaveAiSettings}>Сохранить настройки</button>
        </div>
      </div>

      <div className="admin-settings-grid">
        <div className="admin-settings-column">
          <input
            type="text"
            placeholder="API URL"
            value={aiSettings.base_url}
            onChange={e => setAiSettings(current => ({ ...current, base_url: e.target.value }))}
          />
          <input
            type="password"
            placeholder={aiSettings.has_api_key ? `Ключ сохранён: ${aiSettings.masked_api_key}` : "API-ключ"}
            value={apiKeyInput}
            onChange={e => setApiKeyInput(e.target.value)}
          />
          <input
            type="text"
            placeholder="Модель"
            value={aiSettings.model}
            onChange={e => setAiSettings(current => ({ ...current, model: e.target.value }))}
          />
          {models.length > 0 && (
            <div className="models-compact">
              <div className="model-price-table">
                {models.slice(0, 80).map(model => (
                  <div
                    key={model.id}
                    className={model.id === aiSettings.model ? "price-row active" : "price-row"}
                    onClick={() => handleSelectModel(model.id)}
                  >
                    <span>{model.name || model.id}</span>
                    <small>{modelPrice(model)}</small>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="admin-settings-column">
          <textarea
            placeholder="Встроенный промпт ассистента"
            value={aiSettings.assistant_prompt || ""}
            onChange={e => setAiSettings(current => ({ ...current, assistant_prompt: e.target.value }))}
          />
        </div>
      </div>

      <div className="admin-two-col">
        <div className="admin-list">
          <div className="section-title compact">
            <div>
              <h2>Пользователи</h2>
              <p>{adminUsers.length} учетных записей</p>
            </div>
            {selectedAdminUser && <p className="muted">Выбран: {selectedAdminUser.email}</p>}
          </div>
          {adminUsers.map(user => (
            <div
              key={user.id}
              className={String(user.id) === String(adminSelectedUserId) ? "admin-user-row active" : "admin-user-row"}
              role="button"
              tabIndex={0}
              onClick={() => handleSelectAdminUser(user.id)}
              onKeyDown={e => {
                if (e.key === "Enter" || e.key === " ") {
                  handleSelectAdminUser(user.id);
                }
              }}
            >
              <div>
                <strong>{user.email}</strong>
                <span>
                  #{user.id}
                  {user.created_at ? ` \u00B7 ${new Date(user.created_at).toLocaleDateString("ru-RU")}` : ""}
                </span>
              </div>
              <div className="admin-user-actions">
                <span className={user.is_admin ? "badge admin" : "badge"}>{user.is_admin ? "админ" : "пользователь"}</span>
                {user.email !== "dboy@bk.ru" && (
                  <>
                    <button className="ghost" disabled={adminBusy} onClick={e => { e.stopPropagation(); handleToggleAdmin(user); }}>
                      {user.is_admin ? "Снять админа" : "Сделать админом"}
                    </button>
                    <button className="ghost danger" disabled={adminBusy} onClick={e => { e.stopPropagation(); handleDeleteUser(user); }}>
                      Удалить
                    </button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="admin-access">
          <div className="section-title compact">
            <div>
              <h3>{selectedAdminUser ? "Доступы пользователя" : "Пользователи"}</h3>
              <p className="muted">
                {selectedAdminUser ? selectedAdminUser.email : "Выберите пользователя"}
              </p>
            </div>
          </div>

          {selectedAdminUser ? (
            adminUserSmetas.length > 0 ? (
              <>
                <p className="muted">{selectedAdminUser.email} имеет доступ к {adminUserSmetas.length} сметам.</p>
                {adminUserSmetas.map(smeta => (
                  <div key={smeta.id} className="admin-access-row">
                    <div>
                      <strong>{smeta.name}</strong>
                      <span>
                        {smeta.permission === "owner"
                          ? "владелец"
                          : smeta.permission === "edit"
                            ? "редактирование"
                            : smeta.permission === "view"
                              ? "просмотр"
                              : "админ-доступ"}
                      </span>
                    </div>
                    <strong>{money(smeta.total)}</strong>
                  </div>
                ))}
              </>
            ) : (
              <p className="muted">У выбранного пользователя пока нет доступных смет.</p>
            )
          ) : (
            <p className="muted">Выберите пользователя, чтобы увидеть его сметы.</p>
          )}
        </div>
      </div>
    </section>
  );
}

export default AdminPage;
