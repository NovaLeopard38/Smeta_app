import React from "react";

function SmetaDetails({
  selectedSmeta,
  smetaDetails,
  updateSmetaDetails,
  handleSaveSmetaDetails,
  shareForm,
  setShareForm,
  handleShareSmeta,
  previewSmeta,
  money,
}) {
  if (!selectedSmeta) return null;

  return (
    <div className="smeta-details">
      <input
        type="text"
        placeholder="Название сметы"
        value={smetaDetails.name}
        onChange={e => updateSmetaDetails("name", e.target.value)}
      />
      <input
        type="text"
        placeholder="Заказчик"
        value={smetaDetails.customer_name}
        onChange={e => updateSmetaDetails("customer_name", e.target.value)}
      />
      <textarea
        placeholder="Реквизиты заказчика"
        value={smetaDetails.customer_details}
        onChange={e => updateSmetaDetails("customer_details", e.target.value)}
      />
      <input
        type="text"
        placeholder="Исполнитель"
        value={smetaDetails.contractor_name}
        onChange={e => updateSmetaDetails("contractor_name", e.target.value)}
      />
      <textarea
        placeholder="Реквизиты исполнителя"
        value={smetaDetails.contractor_details}
        onChange={e => updateSmetaDetails("contractor_details", e.target.value)}
      />
      <input
        type="text"
        placeholder="Согласующий"
        value={smetaDetails.approver_name}
        onChange={e => updateSmetaDetails("approver_name", e.target.value)}
      />
      <textarea
        placeholder="Реквизиты согласующего"
        value={smetaDetails.approver_details}
        onChange={e => updateSmetaDetails("approver_details", e.target.value)}
      />
      <select
        value={smetaDetails.tax_mode}
        onChange={e => updateSmetaDetails("tax_mode", e.target.value)}
      >
        <option value="none">Без НДС</option>
        <option value="vat_added">НДС сверху</option>
        <option value="vat_included">НДС в том числе</option>
      </select>
      <select
        value={smetaDetails.tax_rate}
        onChange={e => updateSmetaDetails("tax_rate", e.target.value)}
      >
        <option value="0">0%</option>
        <option value="5">5% УСН</option>
        <option value="7">7% УСН</option>
        <option value="10">10%</option>
        <option value="22">22% НДС</option>
      </select>
      <div className="tax-summary">
        <span>До налога: {money(previewSmeta.subtotal || 0)}</span>
        <span>Налог: {money(previewSmeta.tax_amount || 0)}</span>
      </div>
      <button onClick={handleSaveSmetaDetails}>Сохранить реквизиты</button>
      <input
        type="email"
        placeholder="Email для доступа"
        value={shareForm.email}
        onChange={e => setShareForm(current => ({ ...current, email: e.target.value }))}
      />
      <select
        value={shareForm.permission}
        onChange={e => setShareForm(current => ({ ...current, permission: e.target.value }))}
      >
        <option value="view">Только просмотр</option>
        <option value="edit">Совместное редактирование</option>
      </select>
      <button className="ghost" onClick={handleShareSmeta}>Поделиться</button>
    </div>
  );
}

export default SmetaDetails;
