"""Human-readable rendering (HTML) and the shared labels used by pdf.py.

A received XRechnung/Peppol XML is unreadable for most people; rendering it
is one of the most common requests. Language follows inv["language"] or the
seller's country.
"""

import html

from .model import VAT_CATEGORIES, fmt_amount, fmt_num, fmt_price

LABELS = {
    "en": dict(invoice="Invoice", credit_note="Credit note", corrected="Corrected invoice", number="Invoice no.",
               date="Invoice date", due="Due date", period="Service period", delivery="Delivery date",
               buyer_ref="Buyer reference", order="Order no.", seller="Seller", buyer="Bill to", pos="#",
               item="Description", qty="Qty", unit="Unit", price="Unit price", vat="VAT", net="Net amount",
               allowance="Allowance", charge="Charge", subtotal="Sum of lines", total_net="Total excl. VAT",
               total_vat="VAT total", total_gross="Total incl. VAT", prepaid="Paid in advance", rounding="Rounding",
               payable="Amount due", payment="Payment", iban="IBAN", bic="BIC", ref="Payment reference",
               vat_id="VAT ID", taxable="Taxable amount", rate="Rate", tax="VAT amount", notes="Notes",
               preceding="Refers to invoice", exemption="Exemption", page="Page", terms="Terms"),
    "de": dict(invoice="Rechnung", credit_note="Gutschrift", corrected="Rechnungskorrektur", number="Rechnungsnr.",
               date="Rechnungsdatum", due="Fällig am", period="Leistungszeitraum", delivery="Lieferdatum",
               buyer_ref="Käuferreferenz", order="Bestellnr.", seller="Verkäufer", buyer="Rechnungsempfänger", pos="Pos.",
               item="Bezeichnung", qty="Menge", unit="Einheit", price="Einzelpreis", vat="USt.", net="Nettobetrag",
               allowance="Nachlass", charge="Zuschlag", subtotal="Summe Positionen", total_net="Gesamt netto",
               total_vat="Umsatzsteuer", total_gross="Gesamt brutto", prepaid="Bereits gezahlt", rounding="Rundung",
               payable="Zahlbetrag", payment="Zahlung", iban="IBAN", bic="BIC", ref="Verwendungszweck",
               vat_id="USt-IdNr.", taxable="Bemessungsgrundlage", rate="Satz", tax="Steuerbetrag", notes="Hinweise",
               preceding="Bezug auf Rechnung", exemption="Befreiung", page="Seite", terms="Bedingungen"),
    "fr": dict(invoice="Facture", credit_note="Avoir", corrected="Facture rectificative", number="N° de facture",
               date="Date de facture", due="Échéance", period="Période", delivery="Date de livraison",
               buyer_ref="Référence acheteur", order="N° de commande", seller="Vendeur", buyer="Facturé à", pos="N°",
               item="Désignation", qty="Qté", unit="Unité", price="Prix unitaire", vat="TVA", net="Montant HT",
               allowance="Remise", charge="Frais", subtotal="Total des lignes", total_net="Total HT",
               total_vat="Total TVA", total_gross="Total TTC", prepaid="Acompte versé", rounding="Arrondi",
               payable="Net à payer", payment="Paiement", iban="IBAN", bic="BIC", ref="Référence de paiement",
               vat_id="N° TVA", taxable="Base HT", rate="Taux", tax="Montant TVA", notes="Mentions",
               preceding="Facture d'origine", exemption="Exonération", page="Page", terms="Conditions"),
    "nl": dict(invoice="Factuur", credit_note="Creditnota", corrected="Gecorrigeerde factuur", number="Factuurnr.",
               date="Factuurdatum", due="Vervaldatum", period="Periode", delivery="Leverdatum",
               buyer_ref="Referentie koper", order="Ordernr.", seller="Verkoper", buyer="Factuuradres", pos="#",
               item="Omschrijving", qty="Aantal", unit="Eenheid", price="Prijs", vat="Btw", net="Netto",
               allowance="Korting", charge="Toeslag", subtotal="Totaal regels", total_net="Totaal excl. btw",
               total_vat="Btw totaal", total_gross="Totaal incl. btw", prepaid="Vooruitbetaald", rounding="Afronding",
               payable="Te betalen", payment="Betaling", iban="IBAN", bic="BIC", ref="Betalingskenmerk",
               vat_id="Btw-nr.", taxable="Grondslag", rate="Tarief", tax="Btw-bedrag", notes="Opmerkingen",
               preceding="Betreft factuur", exemption="Vrijstelling", page="Pagina", terms="Voorwaarden"),
    "it": dict(invoice="Fattura", credit_note="Nota di credito", corrected="Fattura rettificativa", number="Fattura n.",
               date="Data fattura", due="Scadenza", period="Periodo", delivery="Data di consegna",
               buyer_ref="Riferimento acquirente", order="Ordine n.", seller="Cedente", buyer="Cessionario", pos="#",
               item="Descrizione", qty="Qtà", unit="U.M.", price="Prezzo unitario", vat="IVA", net="Imponibile",
               allowance="Sconto", charge="Maggiorazione", subtotal="Totale righe", total_net="Totale imponibile",
               total_vat="Totale IVA", total_gross="Totale documento", prepaid="Acconto", rounding="Arrotondamento",
               payable="Netto a pagare", payment="Pagamento", iban="IBAN", bic="BIC", ref="Causale",
               vat_id="P. IVA", taxable="Imponibile", rate="Aliquota", tax="Imposta", notes="Note",
               preceding="Rif. fattura", exemption="Esenzione", page="Pagina", terms="Condizioni"),
    "es": dict(invoice="Factura", credit_note="Factura rectificativa (abono)", corrected="Factura rectificativa", number="N.º de factura",
               date="Fecha", due="Vencimiento", period="Periodo", delivery="Fecha de entrega",
               buyer_ref="Referencia del comprador", order="N.º de pedido", seller="Vendedor", buyer="Cliente", pos="#",
               item="Descripción", qty="Cant.", unit="Unidad", price="Precio", vat="IVA", net="Importe neto",
               allowance="Descuento", charge="Recargo", subtotal="Suma de líneas", total_net="Base imponible",
               total_vat="Total IVA", total_gross="Total", prepaid="Anticipo", rounding="Redondeo",
               payable="Importe a pagar", payment="Pago", iban="IBAN", bic="BIC", ref="Referencia de pago",
               vat_id="NIF-IVA", taxable="Base", rate="Tipo", tax="Cuota", notes="Observaciones",
               preceding="Factura rectificada", exemption="Exención", page="Página", terms="Condiciones"),
}
COUNTRY_LANG = {"DE": "de", "AT": "de", "CH": "de", "LU": "fr", "FR": "fr", "BE": "fr", "NL": "nl",
                "IT": "it", "ES": "es"}
UNITS = {"C62": "pcs", "H87": "pcs", "EA": "each", "XPP": "piece", "HUR": "h", "DAY": "day", "MON": "month",
         "ANN": "year", "WEE": "week", "MIN": "min", "KGM": "kg", "GRM": "g", "TNE": "t", "MTR": "m", "MTK": "m²",
         "MTQ": "m³", "LTR": "l", "KMT": "km", "KWH": "kWh", "SET": "set", "LS": "lump sum", "PR": "pair",
         "XBX": "box", "XPK": "pack", "E48": "service unit", "P1": "%"}


UNITS_L10N = {
    "de": {"C62": "Stk.", "H87": "Stk.", "EA": "Stk.", "HUR": "Std.", "DAY": "Tag", "MON": "Monat", "ANN": "Jahr",
           "WEE": "Woche", "SET": "Satz", "PR": "Paar", "LS": "pauschal", "XBX": "Karton", "XPK": "Pck."},
    "fr": {"C62": "pce", "H87": "pce", "EA": "u.", "HUR": "h", "DAY": "jour", "MON": "mois", "ANN": "an",
           "WEE": "sem.", "SET": "lot", "PR": "paire", "LS": "forfait", "XBX": "carton"},
    "nl": {"C62": "st.", "H87": "st.", "HUR": "uur", "DAY": "dag", "MON": "maand", "ANN": "jaar", "LS": "forfait"},
    "it": {"C62": "pz", "H87": "pz", "HUR": "ore", "DAY": "gg", "MON": "mese", "ANN": "anno", "LS": "forfait"},
    "es": {"C62": "ud.", "H87": "ud.", "HUR": "h", "DAY": "día", "MON": "mes", "ANN": "año", "LS": "global"},
}
# (thousands separator, decimal separator)
NUM_FMT = {"en": (",", "."), "de": (".", ","), "nl": (".", ","), "it": (".", ","), "es": (".", ","), "fr": ("\u202f", ",")}


def unit_name(code, lang):
    return UNITS_L10N.get(lang, {}).get(code) or UNITS.get(code, code)


def num(s, lang):
    """Localise an already formatted decimal string like '-1234.50'."""
    th, dp = NUM_FMT.get(lang, NUM_FMT["en"])
    neg = s.startswith("-")
    whole, _, frac = s.lstrip("-").partition(".")
    whole = f"{int(whole):,}".replace(",", th)
    return f"{'-' if neg else ''}{whole}{dp + frac if frac else ''}"


def lang_of(inv):
    lang = (inv.get("language") or "").lower()[:2]
    if lang in LABELS:
        return lang
    return COUNTRY_LANG.get(((inv.get("seller") or {}).get("address") or {}).get("country"), "en")


def labels(inv):
    return LABELS[lang_of(inv)]


def title_of(inv, L):
    if inv["is_credit_note"]:
        return L["credit_note"]
    if inv["type_code"] == "384":
        return L["corrected"]
    return L["invoice"]


def money(d, cur, lang="en"):
    return f"{num(fmt_amount(d), lang)} {cur}"


def party_lines(p):
    if not p:
        return []
    a = p.get("address") or {}
    out = [p.get("name") or ""]
    if p.get("trading_name") and p.get("trading_name") != p.get("name"):
        out.append(p["trading_name"])
    for k in ("line1", "line2", "line3"):
        if a.get(k):
            out.append(a[k])
    out.append(" ".join(x for x in (a.get("postal_code"), a.get("city")) if x))
    out.append(a.get("country") or "")
    return [x for x in out if x]


def _e(s):
    return html.escape(str(s)) if s is not None else ""


def to_html(inv):
    L = labels(inv)
    lg = lang_of(inv)
    cur = inv["currency"]
    t = inv["totals"]
    seller, buyer = inv.get("seller") or {}, inv.get("buyer") or {}
    meta = [(L["number"], inv.get("number")), (L["date"], inv.get("issue_date")), (L["due"], inv.get("due_date"))]
    if inv.get("period"):
        meta.append((L["period"], f"{inv['period'].get('start', '')} – {inv['period'].get('end', '')}"))
    if (inv.get("delivery") or {}).get("date"):
        meta.append((L["delivery"], inv["delivery"]["date"]))
    for key, lab in (("buyer_reference", "buyer_ref"), ("order_reference", "order")):
        if inv.get(key):
            meta.append((L[lab], inv[key]))
    for p in inv.get("preceding_invoices") or []:
        meta.append((L["preceding"], f"{p.get('number', '')} {p.get('date', '')}"))
    rows = []
    for ln in inv["lines"]:
        rate = "–" if ln["vat_rate"] is None else f"{num(fmt_num(ln['vat_rate']), lg)} %"
        desc = f"<b>{_e(ln.get('name'))}</b>"
        if ln.get("description"):
            desc += f"<br><span class=muted>{_e(ln['description'])}</span>"
        for a in ln.get("allowances") or []:
            desc += f"<br><span class=muted>{L['allowance']}: {_e(a.get('reason') or a.get('reason_code'))} −{money(a['amount'], cur, lg)}</span>"
        for c in ln.get("charges") or []:
            desc += f"<br><span class=muted>{L['charge']}: {_e(c.get('reason') or c.get('reason_code'))} +{money(c['amount'], cur, lg)}</span>"
        rows.append(f"<tr><td>{_e(ln['id'])}</td><td>{desc}</td><td class=r>{num(fmt_num(ln['quantity']), lg)}</td>"
                    f"<td>{_e(unit_name(ln['unit'], lg))}</td><td class=r>{num(fmt_price(ln['price']), lg)}</td>"
                    f"<td class=r>{rate}</td><td class=r>{money(ln['net_amount'], cur, lg)}</td></tr>")
    tot = [(L["subtotal"], t["line_total"])]
    for a in inv.get("allowances") or []:
        tot.append((f"{L['allowance']}: {a.get('reason') or a.get('reason_code')}", -a["amount"]))
    for c in inv.get("charges") or []:
        tot.append((f"{L['charge']}: {c.get('reason') or c.get('reason_code')}", c["amount"]))
    tot += [(L["total_net"], t["tax_exclusive"]), (L["total_vat"], t["tax_total"]), (L["total_gross"], t["tax_inclusive"])]
    if t["prepaid"]:
        tot.append((L["prepaid"], -t["prepaid"]))
    if t["rounding"]:
        tot.append((L["rounding"], t["rounding"]))
    vat_rows = "".join(
        f"<tr><td>{_e(b['category'])} – {_e(VAT_CATEGORIES.get(b['category'], ''))}"
        f"{'<br><span class=muted>' + _e(b.get('exemption_reason') or b.get('exemption_code')) + '</span>' if b.get('exemption_reason') or b.get('exemption_code') else ''}</td>"
        f"<td class=r>{'–' if b['rate'] is None else fmt_num(b['rate']) + ' %'}</td>"
        f"<td class=r>{money(b['taxable'], cur, lg)}</td><td class=r>{money(b['tax'], cur, lg)}</td></tr>"
        for b in inv["vat_breakdown"])
    pay = inv.get("payment") or {}
    pay_html = []
    for ct in pay.get("credit_transfers") or []:
        pay_html.append(f"{L['iban']}: <b>{_e(ct.get('iban') or ct.get('account_id'))}</b>"
                        + (f" &nbsp; {L['bic']}: {_e(ct['bic'])}" if ct.get("bic") else "")
                        + (f" &nbsp; ({_e(ct['account_name'])})" if ct.get("account_name") else ""))
    if pay.get("remittance_info"):
        pay_html.append(f"{L['ref']}: <b>{_e(pay['remittance_info'])}</b>")
    if pay.get("terms"):
        pay_html.append(f"{L['terms']}: {_e(pay['terms'])}")
    notes = "".join(f"<p>{_e(n['text'])}</p>" for n in inv["notes"])
    footer = " · ".join(_e(x) for x in (
        seller.get("name"), seller.get("vat_id") and f"{L['vat_id']} {seller['vat_id']}",
        (seller.get("legal_id") or {}).get("id") if isinstance(seller.get("legal_id"), dict) else seller.get("legal_id"),
        seller.get("legal_info")) if x)
    return f"""<!doctype html><html lang="{lang_of(inv)}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{_e(title_of(inv, L))} {_e(inv.get('number'))}</title>
<style>
:root{{--ink:#1d2433;--muted:#667085;--line:#e4e7ec;--accent:#1f4fd1;--bg:#fff}}
body{{font:14px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--ink);background:var(--bg);margin:0}}
.page{{max-width:860px;margin:24px auto;padding:32px;border:1px solid var(--line);border-radius:10px}}
h1{{font-size:26px;margin:0 0 4px;color:var(--accent)}} .muted{{color:var(--muted);font-size:12.5px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin:20px 0}} .box h3{{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:0 0 6px}}
table{{width:100%;border-collapse:collapse;margin:12px 0}} th,td{{padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top;text-align:left}}
th{{font-size:12px;color:var(--muted);font-weight:600}} .r{{text-align:right;white-space:nowrap}}
.totals{{margin-left:auto;max-width:420px}} .totals .due td{{font-weight:700;font-size:16px;border-top:2px solid var(--ink)}}
footer{{margin-top:28px;font-size:12px;color:var(--muted);border-top:1px solid var(--line);padding-top:10px}}
@media (max-width:640px){{.page{{margin:0;padding:16px;border:0}}.grid{{grid-template-columns:1fr}}table{{font-size:12.5px}}}}
</style></head><body><div class=page>
<h1>{_e(title_of(inv, L))}</h1><div class=muted>{_e(inv.get('number'))}</div>
<div class=grid><div class=box><h3>{L['seller']}</h3>{'<br>'.join(_e(x) for x in party_lines(seller))}
{('<br>' + L['vat_id'] + ' ' + _e(seller['vat_id'])) if seller.get('vat_id') else ''}</div>
<div class=box><h3>{L['buyer']}</h3>{'<br>'.join(_e(x) for x in party_lines(buyer))}
{('<br>' + L['vat_id'] + ' ' + _e(buyer['vat_id'])) if buyer.get('vat_id') else ''}</div></div>
<table>{''.join(f'<tr><th style="width:40%">{_e(k)}</th><td>{_e(v)}</td></tr>' for k, v in meta if v)}</table>
<table><thead><tr><th>{L['pos']}</th><th>{L['item']}</th><th class=r>{L['qty']}</th><th>{L['unit']}</th><th class=r>{L['price']}</th><th class=r>{L['vat']}</th><th class=r>{L['net']}</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
<table class=totals>{''.join(f'<tr><td>{_e(k)}</td><td class=r>{money(v, cur, lg)}</td></tr>' for k, v in tot)}
<tr class=due><td>{L['payable']}</td><td class=r>{money(t['payable'], cur, lg)}</td></tr></table>
<h3 class=muted>{L['vat']}</h3><table><thead><tr><th></th><th class=r>{L['rate']}</th><th class=r>{L['taxable']}</th><th class=r>{L['tax']}</th></tr></thead><tbody>{vat_rows}</tbody></table>
{('<h3 class=muted>' + L['payment'] + '</h3><p>' + '<br>'.join(pay_html) + '</p>') if pay_html else ''}
{('<h3 class=muted>' + L['notes'] + '</h3>' + notes) if notes else ''}
<footer>{footer}</footer></div></body></html>"""
