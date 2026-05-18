
from html import escape
from html.parser import HTMLParser

from .excel import (
    effective_unit_price,
    grouped_smeta_items,
    item_total,
    org_rows,
    smeta_financials,
)


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        text_part = data.strip()
        if text_part:
            self.parts.append(text_part)

    def text(self):
        return "\n".join(self.parts)


def html_to_text(html):
    parser = TextExtractor()
    parser.feed(html)
    return parser.text()


def build_smeta_print_html(smeta):
    financials = smeta_financials(smeta)
    total = financials["total"]
    org_html = "".join(
        f"<tr><th>{escape(role)}</th><td>{escape(name)}</td><td>{escape(details).replace(chr(10), '<br>')}</td></tr>"
        for role, name, details in org_rows(smeta)
    )
    rows = []
    for section, items in grouped_smeta_items(smeta):
        section_total = sum(item_total(item, smeta) for item in items)
        rows.append(
            f"<tr class='section'><td colspan='6'>{escape(section)}</td><td>{section_total:,.2f}</td></tr>"
        )
        item_no = 1
        for item in items:
            price = effective_unit_price(item, smeta)
            total_item = item_total(item, smeta)
            rows.append(
                "<tr>"
                f"<td>{item_no}</td>"
                f"<td>{escape(item.name or '')}</td>"
                f"<td>{escape(item.characteristics or '').replace(chr(10), '<br>')}</td>"
                f"<td>{escape(item.unit or 'ед.')}</td>"
                f"<td>{item.quantity:g}</td>"
                f"<td>{price:,.2f}</td>"
                f"<td>{total_item:,.2f}</td>"
                "</tr>"
            )
            item_no += 1
    tax_html = ""
    if financials["tax_amount"] > 0 and (smeta.tax_mode or "") == "vat_added":
        tax_html = (
            f"<div class='subtotal'>Итого без НДС: {financials['subtotal']:,.2f} \u20bd</div>"
            f"<div class='subtotal'>НДС {float(smeta.tax_rate or 0):g}%: {financials['tax_amount']:,.2f} \u20bd</div>"
        )
    elif financials["tax_amount"] > 0 and (smeta.tax_mode or "") == "vat_included":
        tax_html = f"<div class='subtotal'>В том числе НДС {float(smeta.tax_rate or 0):g}%: {financials['tax_amount']:,.2f} \u20bd</div>"
    return f"""
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>Смета {escape(smeta.name)}</title>
  <style>
    body {{ font-family: Arial, sans-serif; color: #111827; margin: 28px; }}
    .actions {{ margin-bottom: 16px; }}
    button {{ background: #2364aa; color: white; border: 0; border-radius: 6px; padding: 10px 14px; }}
    h1 {{ font-size: 22px; margin: 0 0 14px; }}
    table {{ width: 100%; border-collapse: collapse; margin: 14px 0; }}
    th, td {{ border: 1px solid #cfd8e3; padding: 7px; vertical-align: top; font-size: 12px; }}
    th {{ background: #eaf2f8; }}
    .section td {{ background: #d9eaf7; font-weight: bold; }}
    .subtotal {{ text-align: right; font-size: 14px; font-weight: bold; margin-top: 8px; }}
    .total {{ text-align: right; font-size: 18px; font-weight: bold; margin-top: 12px; }}
    .sign {{ display: grid; grid-template-columns: 1fr 1fr; gap: 80px; margin-top: 42px; }}
    @media print {{ .actions {{ display: none; }} body {{ margin: 12mm; }} }}
  </style>
</head>
<body>
  <div class="actions"><button onclick="window.print()">Печать / сохранить в PDF</button></div>
  <h1>Смета: {escape(smeta.name)}</h1>
  <table>
    <thead><tr><th>Роль</th><th>Организация</th><th>Реквизиты</th></tr></thead>
    <tbody>{org_html}</tbody>
  </table>
  <table>
    <thead><tr><th>№</th><th>Позиция</th><th>Характеристики</th><th>Ед.</th><th>Кол-во</th><th>Цена</th><th>Сумма</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  {tax_html}
  <div class="total">Итого: {total:,.2f} \u20bd</div>
  <div class="sign"><div>Заказчик: __________________ /</div><div>Исполнитель: __________________ /</div></div>
</body>
</html>
"""
