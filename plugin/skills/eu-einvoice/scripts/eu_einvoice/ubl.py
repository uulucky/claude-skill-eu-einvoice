"""Generate UBL 2.1 Invoice / CreditNote from a prepared invoice model.

Element order follows the UBL 2.1 XSD sequence exactly; XSD validation fails
on any out-of-order element, so keep new elements in their schema position.
"""

from decimal import Decimal

from lxml import etree

from .model import TAX_POINT_UBL, fmt_amount, fmt_num

NS_INV = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
NS_CN = "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"
CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"


def _cac(parent, tag):
    return etree.SubElement(parent, f"{{{CAC}}}{tag}")


def _cbc(parent, tag, text, **attrs):
    if text is None or text == "":
        return None
    el = etree.SubElement(parent, f"{{{CBC}}}{tag}")
    el.text = str(text)
    for k, v in attrs.items():
        if v not in (None, ""):
            el.set(k, str(v))
    return el


def _amt(parent, tag, value, currency):
    return _cbc(parent, tag, fmt_amount(value), currencyID=currency)


def _address(parent, tag, a):
    if not a:
        return
    el = _cac(parent, tag)
    _cbc(el, "StreetName", a.get("line1"))
    _cbc(el, "AdditionalStreetName", a.get("line2"))
    _cbc(el, "CityName", a.get("city"))
    _cbc(el, "PostalZone", a.get("postal_code"))
    _cbc(el, "CountrySubentity", a.get("subdivision"))
    if a.get("line3"):
        _cbc(_cac(el, "AddressLine"), "Line", a["line3"])
    _cbc(_cac(el, "Country"), "IdentificationCode", a.get("country"))


def _ids(party_el, ids):
    for pid in ids or []:
        if isinstance(pid, str):
            pid = {"id": pid}
        _cbc(_cac(party_el, "PartyIdentification"), "ID", pid["id"], schemeID=pid.get("scheme"))


def _party(parent, tag, p, role, inv):
    wrap = _cac(parent, tag)
    party = _cac(wrap, "Party")
    ea = p.get("electronic_address")
    if ea:
        _cbc(party, "EndpointID", ea["id"], schemeID=ea.get("scheme"))
    ids = list(p.get("ids") or [])
    if role == "seller" and (inv.get("payment") or {}).get("direct_debit", {}).get("creditor_id"):
        ids.append({"id": inv["payment"]["direct_debit"]["creditor_id"], "scheme": "SEPA"})
    _ids(party, ids)
    trading = p.get("trading_name")
    if trading:
        _cbc(_cac(party, "PartyName"), "Name", trading)
    _address(party, "PostalAddress", p.get("address"))
    if p.get("vat_id"):
        ts = _cac(party, "PartyTaxScheme")
        _cbc(ts, "CompanyID", p["vat_id"])
        _cbc(_cac(ts, "TaxScheme"), "ID", "VAT")
    if p.get("tax_registration_id"):
        ts = _cac(party, "PartyTaxScheme")
        _cbc(ts, "CompanyID", p["tax_registration_id"])
        _cbc(_cac(ts, "TaxScheme"), "ID", "FC")
    le = _cac(party, "PartyLegalEntity")
    _cbc(le, "RegistrationName", p.get("name"))
    legal = p.get("legal_id")
    if isinstance(legal, str):
        legal = {"id": legal}
    if legal:
        _cbc(le, "CompanyID", legal["id"], schemeID=legal.get("scheme"))
    _cbc(le, "CompanyLegalForm", p.get("legal_info"))
    c = p.get("contact")
    if c:
        ce = _cac(party, "Contact")
        _cbc(ce, "Name", c.get("name"))
        _cbc(ce, "Telephone", c.get("phone"))
        _cbc(ce, "ElectronicMail", c.get("email"))


def _tax_category(parent, tag, cat, rate, reason=None, code=None):
    tc = _cac(parent, tag)
    _cbc(tc, "ID", cat)
    if rate is not None:
        _cbc(tc, "Percent", fmt_num(rate))
    _cbc(tc, "TaxExemptionReasonCode", code)
    _cbc(tc, "TaxExemptionReason", reason)
    _cbc(_cac(tc, "TaxScheme"), "ID", "VAT")


def _allowance_charge(parent, ac, is_charge, currency, with_tax):
    el = _cac(parent, "AllowanceCharge")
    _cbc(el, "ChargeIndicator", "true" if is_charge else "false")
    _cbc(el, "AllowanceChargeReasonCode", ac.get("reason_code"))
    _cbc(el, "AllowanceChargeReason", ac.get("reason"))
    if ac.get("percent") is not None:
        _cbc(el, "MultiplierFactorNumeric", fmt_num(ac["percent"]))
    _amt(el, "Amount", ac["amount"], currency)
    if ac.get("base_amount") is not None:
        _amt(el, "BaseAmount", ac["base_amount"], currency)
    if with_tax:
        _tax_category(el, "TaxCategory", ac["vat_category"], ac["vat_rate"])


def _doc_ref(parent, tag, ref_id):
    if ref_id:
        _cbc(_cac(parent, tag), "ID", ref_id)


def _period(parent, period, code=None):
    if not (period or code):
        return
    period = period or {}
    el = _cac(parent, "InvoicePeriod")
    _cbc(el, "StartDate", period.get("start"))
    _cbc(el, "EndDate", period.get("end"))
    _cbc(el, "DescriptionCode", code)


def generate(inv, profile):
    cn = inv["is_credit_note"]
    root_tag = f"{{{NS_CN}}}CreditNote" if cn else f"{{{NS_INV}}}Invoice"
    root = etree.Element(root_tag, nsmap={None: NS_CN if cn else NS_INV, "cac": CAC, "cbc": CBC})
    cur = inv["currency"]
    pay = inv.get("payment") or {}

    _cbc(root, "CustomizationID", profile["customization_id"])
    _cbc(root, "ProfileID", profile.get("process_id") or inv.get("process_id"))
    _cbc(root, "ID", inv["number"])
    _cbc(root, "IssueDate", inv["issue_date"])
    if not cn:
        _cbc(root, "DueDate", inv.get("due_date"))
        _cbc(root, "InvoiceTypeCode", inv["type_code"])
    else:
        _cbc(root, "CreditNoteTypeCode", inv["type_code"])
    for n in inv["notes"]:
        text = n["text"]
        if n.get("subject"):
            text = f"#{n['subject']}#{text}"
        _cbc(root, "Note", text)
    _cbc(root, "TaxPointDate", inv.get("tax_point_date"))
    _cbc(root, "DocumentCurrencyCode", cur)
    if inv.get("tax_currency") and inv["tax_currency"] != cur:
        _cbc(root, "TaxCurrencyCode", inv["tax_currency"])
    _cbc(root, "AccountingCost", inv.get("accounting_reference"))
    _cbc(root, "BuyerReference", inv.get("buyer_reference"))
    _period(root, inv.get("period"), TAX_POINT_UBL.get(inv.get("tax_point_code")))
    if inv.get("order_reference") or inv.get("sales_order_reference"):
        o = _cac(root, "OrderReference")
        _cbc(o, "ID", inv.get("order_reference") or "NA")
        _cbc(o, "SalesOrderID", inv.get("sales_order_reference"))
    for p in inv.get("preceding_invoices") or []:
        r = _cac(_cac(root, "BillingReference"), "InvoiceDocumentReference")
        _cbc(r, "ID", p.get("number"))
        _cbc(r, "IssueDate", p.get("date"))
    _doc_ref(root, "DespatchDocumentReference", inv.get("despatch_advice_reference"))
    _doc_ref(root, "ReceiptDocumentReference", inv.get("receiving_advice_reference"))
    _doc_ref(root, "OriginatorDocumentReference", inv.get("tender_reference"))
    _doc_ref(root, "ContractDocumentReference", inv.get("contract_reference"))
    if inv.get("object_reference"):
        o = inv["object_reference"]
        if isinstance(o, str):
            o = {"id": o}
        r = _cac(root, "AdditionalDocumentReference")
        _cbc(r, "ID", o["id"], schemeID=o.get("scheme"))
        _cbc(r, "DocumentTypeCode", "130")
    for att in inv.get("attachments") or []:
        r = _cac(root, "AdditionalDocumentReference")
        _cbc(r, "ID", att["id"])
        _cbc(r, "DocumentDescription", att.get("description"))
        if att.get("content_b64") or att.get("uri"):
            a = _cac(r, "Attachment")
            if att.get("content_b64"):
                _cbc(a, "EmbeddedDocumentBinaryObject", att["content_b64"],
                     mimeCode=att.get("mime"), filename=att.get("filename"))
            if att.get("uri"):
                _cbc(_cac(a, "ExternalReference"), "URI", att["uri"])
    if inv.get("project_reference"):
        if cn:  # UBL 2.1 CreditNote has no ProjectReference: EN 16931 binding uses doc type 50
            r = _cac(root, "AdditionalDocumentReference")
            _cbc(r, "ID", inv["project_reference"])
            _cbc(r, "DocumentTypeCode", "50")
        else:
            _doc_ref(root, "ProjectReference", inv["project_reference"])

    _party(root, "AccountingSupplierParty", inv["seller"], "seller", inv)
    _party(root, "AccountingCustomerParty", inv["buyer"], "buyer", inv)

    payee = inv.get("payee")
    if payee:
        pe = _cac(root, "PayeeParty")
        _ids(pe, payee.get("ids"))
        _cbc(_cac(pe, "PartyName"), "Name", payee.get("name"))
        if payee.get("legal_id"):
            lid = payee["legal_id"] if isinstance(payee["legal_id"], dict) else {"id": payee["legal_id"]}
            _cbc(_cac(pe, "PartyLegalEntity"), "CompanyID", lid["id"], schemeID=lid.get("scheme"))
    rep = inv.get("tax_representative")
    if rep:
        te = _cac(root, "TaxRepresentativeParty")
        _cbc(_cac(te, "PartyName"), "Name", rep.get("name"))
        _address(te, "PostalAddress", rep.get("address"))
        ts = _cac(te, "PartyTaxScheme")
        _cbc(ts, "CompanyID", rep.get("vat_id"))
        _cbc(_cac(ts, "TaxScheme"), "ID", "VAT")

    d = inv.get("delivery")
    if d:
        de = _cac(root, "Delivery")
        _cbc(de, "ActualDeliveryDate", d.get("date"))
        if d.get("location_id") or d.get("address"):
            loc = _cac(de, "DeliveryLocation")
            lid = d.get("location_id")
            if lid:
                lid = lid if isinstance(lid, dict) else {"id": lid}
                _cbc(loc, "ID", lid["id"], schemeID=lid.get("scheme"))
            _address(loc, "Address", d.get("address"))
        if d.get("party_name"):
            _cbc(_cac(_cac(de, "DeliveryParty"), "PartyName"), "Name", d["party_name"])

    if pay.get("means_code"):
        transfers = pay.get("credit_transfers") or [None]
        for n, ct in enumerate(transfers):
            # UBL-SR-46..55: text, remittance info, card and mandate at most once
            first = n == 0
            pm = _cac(root, "PaymentMeans")
            _cbc(pm, "PaymentMeansCode", pay["means_code"], name=pay.get("means_text") if first else None)
            if cn and first:
                _cbc(pm, "PaymentDueDate", inv.get("due_date"))
            if first:
                _cbc(pm, "PaymentID", pay.get("remittance_info"))
            card = pay.get("card") if first else None
            if card:
                ca = _cac(pm, "CardAccount")
                _cbc(ca, "PrimaryAccountNumberID", card.get("pan_last4") or card.get("pan"))
                _cbc(ca, "NetworkID", card.get("network") or "NA")
                _cbc(ca, "HolderName", card.get("holder"))
            if ct:
                fa = _cac(pm, "PayeeFinancialAccount")
                _cbc(fa, "ID", ct.get("iban") or ct.get("account_id"))
                _cbc(fa, "Name", ct.get("account_name"))
                if ct.get("bic"):
                    _cbc(_cac(fa, "FinancialInstitutionBranch"), "ID", ct["bic"])
            dd = pay.get("direct_debit") if first else None
            if dd and (dd.get("mandate_id") or dd.get("debited_account")):
                m = _cac(pm, "PaymentMandate")
                _cbc(m, "ID", dd.get("mandate_id"))
                if dd.get("debited_account"):
                    _cbc(_cac(m, "PayerFinancialAccount"), "ID", dd["debited_account"])
    if pay.get("terms"):
        _cbc(_cac(root, "PaymentTerms"), "Note", pay["terms"])

    for a in inv.get("allowances") or []:
        _allowance_charge(root, a, False, cur, True)
    for c in inv.get("charges") or []:
        _allowance_charge(root, c, True, cur, True)

    t = inv["totals"]
    tt = _cac(root, "TaxTotal")
    _amt(tt, "TaxAmount", t["tax_total"], cur)
    for b in inv["vat_breakdown"]:
        st = _cac(tt, "TaxSubtotal")
        _amt(st, "TaxableAmount", b["taxable"], cur)
        _amt(st, "TaxAmount", b["tax"], cur)
        _tax_category(st, "TaxCategory", b["category"], b["rate"], b.get("exemption_reason"), b.get("exemption_code"))
    if "tax_total_tax_currency" in t:
        _amt(_cac(root, "TaxTotal"), "TaxAmount", t["tax_total_tax_currency"], inv["tax_currency"])

    mt = _cac(root, "LegalMonetaryTotal")
    _amt(mt, "LineExtensionAmount", t["line_total"], cur)
    _amt(mt, "TaxExclusiveAmount", t["tax_exclusive"], cur)
    _amt(mt, "TaxInclusiveAmount", t["tax_inclusive"], cur)
    if inv.get("allowances"):
        _amt(mt, "AllowanceTotalAmount", t["allowance_total"], cur)
    if inv.get("charges"):
        _amt(mt, "ChargeTotalAmount", t["charge_total"], cur)
    if t["prepaid"]:
        _amt(mt, "PrepaidAmount", t["prepaid"], cur)
    if t["rounding"]:
        _amt(mt, "PayableRoundingAmount", t["rounding"], cur)
    _amt(mt, "PayableAmount", t["payable"], cur)

    for ln in inv["lines"]:
        _line(root, ln, cn, cur)

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


def _line(root, ln, cn, cur):
    el = _cac(root, "CreditNoteLine" if cn else "InvoiceLine")
    _cbc(el, "ID", ln["id"])
    _cbc(el, "Note", ln.get("note"))
    _cbc(el, "CreditedQuantity" if cn else "InvoicedQuantity", fmt_num(ln["quantity"]), unitCode=ln["unit"])
    _amt(el, "LineExtensionAmount", ln["net_amount"], cur)
    _cbc(el, "AccountingCost", ln.get("accounting_reference"))
    if ln.get("period"):
        _period(el, ln["period"])
    if ln.get("order_line_reference"):
        _cbc(_cac(el, "OrderLineReference"), "LineID", ln["order_line_reference"])
    if ln.get("object_id"):
        o = ln["object_id"] if isinstance(ln["object_id"], dict) else {"id": ln["object_id"]}
        r = _cac(el, "DocumentReference")
        _cbc(r, "ID", o["id"], schemeID=o.get("scheme"))
        _cbc(r, "DocumentTypeCode", "130")
    for a in ln.get("allowances") or []:
        _allowance_charge(el, a, False, cur, False)
    for c in ln.get("charges") or []:
        _allowance_charge(el, c, True, cur, False)

    item = _cac(el, "Item")
    _cbc(item, "Description", ln.get("description"))
    _cbc(item, "Name", ln.get("name"))
    if ln.get("buyer_item_id"):
        _cbc(_cac(item, "BuyersItemIdentification"), "ID", ln["buyer_item_id"])
    if ln.get("seller_item_id"):
        _cbc(_cac(item, "SellersItemIdentification"), "ID", ln["seller_item_id"])
    sid = ln.get("standard_item_id")
    if sid:
        sid = sid if isinstance(sid, dict) else {"id": sid, "scheme": "0160"}
        _cbc(_cac(item, "StandardItemIdentification"), "ID", sid["id"], schemeID=sid.get("scheme"))
    if ln.get("origin_country"):
        _cbc(_cac(item, "OriginCountry"), "IdentificationCode", ln["origin_country"])
    for cl in ln.get("classifications") or []:
        _cbc(_cac(item, "CommodityClassification"), "ItemClassificationCode", cl["id"],
             listID=cl.get("scheme"), listVersionID=cl.get("version"))
    _tax_category(item, "ClassifiedTaxCategory", ln["vat_category"], ln["vat_rate"])
    for at in ln.get("attributes") or []:
        p = _cac(item, "AdditionalItemProperty")
        _cbc(p, "Name", at["name"])
        _cbc(p, "Value", at["value"])

    price = _cac(el, "Price")
    _cbc(price, "PriceAmount", fmt_num(ln["price"]), currencyID=cur)
    if ln.get("base_quantity") is not None:
        _cbc(price, "BaseQuantity", fmt_num(ln["base_quantity"]), unitCode=ln.get("base_unit") or ln["unit"])
    if ln.get("gross_price") is not None:
        pa = _cac(price, "AllowanceCharge")
        _cbc(pa, "ChargeIndicator", "false")
        _cbc(pa, "Amount", fmt_num(ln.get("price_discount") or Decimal(0)), currencyID=cur)
        _cbc(pa, "BaseAmount", fmt_num(ln["gross_price"]), currencyID=cur)
