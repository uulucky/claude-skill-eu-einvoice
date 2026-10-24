"""Generate UN/CEFACT Cross Industry Invoice (CII D16B / D22B subset).

Used for XRechnung-CII, plain EN 16931 CII and as the XML inside
Factur-X / ZUGFeRD PDFs. Element order follows the CII XSD sequence.
"""

from lxml import etree

from .model import TAX_POINT_CII, fmt_amount, fmt_num

RSM = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
RAM = "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
UDT = "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"
QDT = "urn:un:unece:uncefact:data:standard:QualifiedDataType:100"
NSMAP = {"rsm": RSM, "ram": RAM, "udt": UDT, "qdt": QDT}


def _el(parent, tag, text=None, ns=RAM, **attrs):
    el = etree.SubElement(parent, f"{{{ns}}}{tag}")
    if text is not None:
        el.text = str(text)
    for k, v in attrs.items():
        if v not in (None, ""):
            el.set(k, str(v))
    return el


def _opt(parent, tag, text, **attrs):
    if text in (None, ""):
        return None
    return _el(parent, tag, text, **attrs)


def _date(parent, tag, iso, ns_child=UDT):
    if not iso:
        return
    wrap = _el(parent, tag)
    _el(wrap, "DateTimeString", iso.replace("-", ""), ns=ns_child, format="102")


def _amt(parent, tag, value, currency=None):
    return _el(parent, tag, fmt_amount(value), currencyID=currency)


def _address(parent, tag, a):
    if not a:
        return
    el = _el(parent, tag)
    _opt(el, "PostcodeCode", a.get("postal_code"))
    _opt(el, "LineOne", a.get("line1"))
    _opt(el, "LineTwo", a.get("line2"))
    _opt(el, "LineThree", a.get("line3"))
    _opt(el, "CityName", a.get("city"))
    _el(el, "CountryID", a.get("country"))
    _opt(el, "CountrySubDivisionName", a.get("subdivision"))


def _party(parent, tag, p):
    el = _el(parent, tag)
    for pid in p.get("ids") or []:
        pid = pid if isinstance(pid, dict) else {"id": pid}
        if pid.get("scheme"):
            _el(el, "GlobalID", pid["id"], schemeID=pid["scheme"])
        else:
            _el(el, "ID", pid["id"])
    _el(el, "Name", p.get("name"))
    _opt(el, "Description", p.get("legal_info"))
    legal = p.get("legal_id")
    legal = legal if isinstance(legal, dict) or legal is None else {"id": legal}
    if legal or p.get("trading_name"):
        lo = _el(el, "SpecifiedLegalOrganization")
        if legal:
            _el(lo, "ID", legal["id"], schemeID=legal.get("scheme"))
        _opt(lo, "TradingBusinessName", p.get("trading_name"))
    c = p.get("contact")
    if c:
        ce = _el(el, "DefinedTradeContact")
        _opt(ce, "PersonName", c.get("name"))
        if c.get("phone"):
            _el(_el(ce, "TelephoneUniversalCommunication"), "CompleteNumber", c["phone"])
        if c.get("email"):
            _el(_el(ce, "EmailURIUniversalCommunication"), "URIID", c["email"])
    _address(el, "PostalTradeAddress", p.get("address"))
    ea = p.get("electronic_address")
    if ea:
        _el(_el(el, "URIUniversalCommunication"), "URIID", ea["id"], schemeID=ea.get("scheme"))
    if p.get("vat_id"):
        _el(_el(el, "SpecifiedTaxRegistration"), "ID", p["vat_id"], schemeID="VA")
    if p.get("tax_registration_id"):
        _el(_el(el, "SpecifiedTaxRegistration"), "ID", p["tax_registration_id"], schemeID="FC")
    return el


def _allowance_charge(parent, ac, is_charge, with_tax):
    el = _el(parent, "SpecifiedTradeAllowanceCharge")
    _el(_el(el, "ChargeIndicator"), "Indicator", "true" if is_charge else "false", ns=UDT)
    if ac.get("percent") is not None:
        _el(el, "CalculationPercent", fmt_num(ac["percent"]))
    if ac.get("base_amount") is not None:
        _amt(el, "BasisAmount", ac["base_amount"])
    _amt(el, "ActualAmount", ac["amount"])
    _opt(el, "ReasonCode", ac.get("reason_code"))
    _opt(el, "Reason", ac.get("reason"))
    if with_tax:
        t = _el(el, "CategoryTradeTax")
        _el(t, "TypeCode", "VAT")
        _el(t, "CategoryCode", ac["vat_category"])
        if ac["vat_rate"] is not None:
            _el(t, "RateApplicablePercent", fmt_num(ac["vat_rate"]))


def _period(parent, period):
    if not period:
        return
    el = _el(parent, "BillingSpecifiedPeriod")
    _date(el, "StartDateTime", period.get("start"))
    _date(el, "EndDateTime", period.get("end"))


def generate(inv, profile):
    root = etree.Element(f"{{{RSM}}}CrossIndustryInvoice", nsmap=NSMAP)
    cur = inv["currency"]

    ctx = _el(root, "ExchangedDocumentContext", ns=RSM)
    process = profile.get("process_id") or inv.get("process_id")
    if process:
        _el(_el(ctx, "BusinessProcessSpecifiedDocumentContextParameter"), "ID", process)
    _el(_el(ctx, "GuidelineSpecifiedDocumentContextParameter"), "ID", profile["customization_id"])

    doc = _el(root, "ExchangedDocument", ns=RSM)
    _el(doc, "ID", inv["number"])
    _el(doc, "TypeCode", inv["type_code"])
    _date(doc, "IssueDateTime", inv["issue_date"])
    for n in inv["notes"]:
        ne = _el(doc, "IncludedNote")
        _el(ne, "Content", n["text"])
        _opt(ne, "SubjectCode", n.get("subject"))

    tx = _el(root, "SupplyChainTradeTransaction", ns=RSM)
    for ln in inv["lines"]:
        _line(tx, ln)

    # ---- agreement ----
    ag = _el(tx, "ApplicableHeaderTradeAgreement")
    _opt(ag, "BuyerReference", inv.get("buyer_reference"))
    _party(ag, "SellerTradeParty", inv["seller"])
    _party(ag, "BuyerTradeParty", inv["buyer"])
    rep = inv.get("tax_representative")
    if rep:
        re_ = _el(ag, "SellerTaxRepresentativeTradeParty")
        _el(re_, "Name", rep.get("name"))
        _address(re_, "PostalTradeAddress", rep.get("address"))
        _el(_el(re_, "SpecifiedTaxRegistration"), "ID", rep.get("vat_id"), schemeID="VA")
    if inv.get("sales_order_reference"):
        _el(_el(ag, "SellerOrderReferencedDocument"), "IssuerAssignedID", inv["sales_order_reference"])
    if inv.get("order_reference"):
        _el(_el(ag, "BuyerOrderReferencedDocument"), "IssuerAssignedID", inv["order_reference"])
    if inv.get("contract_reference"):
        _el(_el(ag, "ContractReferencedDocument"), "IssuerAssignedID", inv["contract_reference"])
    for att in inv.get("attachments") or []:
        r = _el(ag, "AdditionalReferencedDocument")
        _el(r, "IssuerAssignedID", att["id"])
        _opt(r, "URIID", att.get("uri"))
        _el(r, "TypeCode", "916")
        _opt(r, "Name", att.get("description"))
        if att.get("content_b64"):
            _el(r, "AttachmentBinaryObject", att["content_b64"], mimeCode=att.get("mime"), filename=att.get("filename"))
    if inv.get("tender_reference"):
        r = _el(ag, "AdditionalReferencedDocument")
        _el(r, "IssuerAssignedID", inv["tender_reference"])
        _el(r, "TypeCode", "50")
    if inv.get("object_reference"):
        o = inv["object_reference"] if isinstance(inv["object_reference"], dict) else {"id": inv["object_reference"]}
        r = _el(ag, "AdditionalReferencedDocument")
        _el(r, "IssuerAssignedID", o["id"])
        _el(r, "TypeCode", "130")
        _opt(r, "ReferenceTypeCode", o.get("scheme"))
    if inv.get("project_reference"):
        pr = _el(ag, "SpecifiedProcuringProject")
        _el(pr, "ID", inv["project_reference"])
        _el(pr, "Name", "Project reference")

    # ---- delivery ----
    dl = _el(tx, "ApplicableHeaderTradeDelivery")
    d = inv.get("delivery") or {}
    if d.get("party_name") or d.get("address") or d.get("location_id"):
        st = _el(dl, "ShipToTradeParty")
        lid = d.get("location_id")
        if lid:
            lid = lid if isinstance(lid, dict) else {"id": lid}
            if lid.get("scheme"):
                _el(st, "GlobalID", lid["id"], schemeID=lid["scheme"])
            else:
                _el(st, "ID", lid["id"])
        _opt(st, "Name", d.get("party_name"))
        _address(st, "PostalTradeAddress", d.get("address"))
    if d.get("date"):
        _date(_el(dl, "ActualDeliverySupplyChainEvent"), "OccurrenceDateTime", d["date"])
    if inv.get("despatch_advice_reference"):
        _el(_el(dl, "DespatchAdviceReferencedDocument"), "IssuerAssignedID", inv["despatch_advice_reference"])
    if inv.get("receiving_advice_reference"):
        _el(_el(dl, "ReceivingAdviceReferencedDocument"), "IssuerAssignedID", inv["receiving_advice_reference"])

    # ---- settlement ----
    se = _el(tx, "ApplicableHeaderTradeSettlement")
    pay = inv.get("payment") or {}
    dd = pay.get("direct_debit") or {}
    _opt(se, "CreditorReferenceID", dd.get("creditor_id"))
    _opt(se, "PaymentReference", pay.get("remittance_info"))
    if inv.get("tax_currency") and inv["tax_currency"] != cur:
        _el(se, "TaxCurrencyCode", inv["tax_currency"])
    _el(se, "InvoiceCurrencyCode", cur)
    payee = inv.get("payee")
    if payee:
        pe = _el(se, "PayeeTradeParty")
        for pid in payee.get("ids") or []:
            pid = pid if isinstance(pid, dict) else {"id": pid}
            if pid.get("scheme"):
                _el(pe, "GlobalID", pid["id"], schemeID=pid["scheme"])
            else:
                _el(pe, "ID", pid["id"])
        _el(pe, "Name", payee.get("name"))
        if payee.get("legal_id"):
            lid = payee["legal_id"] if isinstance(payee["legal_id"], dict) else {"id": payee["legal_id"]}
            _el(_el(pe, "SpecifiedLegalOrganization"), "ID", lid["id"], schemeID=lid.get("scheme"))
    if pay.get("means_code"):
        for ct in pay.get("credit_transfers") or [None]:
            pm = _el(se, "SpecifiedTradeSettlementPaymentMeans")
            _el(pm, "TypeCode", pay["means_code"])
            _opt(pm, "Information", pay.get("means_text"))
            card = pay.get("card")
            if card:
                ce = _el(pm, "ApplicableTradeSettlementFinancialCard")
                _el(ce, "ID", card.get("pan_last4") or card.get("pan"))
                _opt(ce, "CardholderName", card.get("holder"))
            if dd.get("debited_account"):
                _el(_el(pm, "PayerPartyDebtorFinancialAccount"), "IBANID", dd["debited_account"])
            if ct:
                fa = _el(pm, "PayeePartyCreditorFinancialAccount")
                _opt(fa, "IBANID", ct.get("iban"))
                _opt(fa, "AccountName", ct.get("account_name"))
                if not ct.get("iban"):
                    _opt(fa, "ProprietaryID", ct.get("account_id"))
                if ct.get("bic"):
                    _el(_el(pm, "PayeeSpecifiedCreditorFinancialInstitution"), "BICID", ct["bic"])
    for n, b in enumerate(inv["vat_breakdown"]):
        t = _el(se, "ApplicableTradeTax")
        _amt(t, "CalculatedAmount", b["tax"])
        _el(t, "TypeCode", "VAT")
        _opt(t, "ExemptionReason", b.get("exemption_reason"))
        _amt(t, "BasisAmount", b["taxable"])
        _el(t, "CategoryCode", b["category"])
        _opt(t, "ExemptionReasonCode", b.get("exemption_code"))
        if inv.get("tax_point_date") and n == 0:  # CII-SR-461: only once
            tp = _el(t, "TaxPointDate")
            _el(tp, "DateString", inv["tax_point_date"].replace("-", ""), ns=UDT, format="102")
        if n == 0:
            _opt(t, "DueDateTypeCode", TAX_POINT_CII.get(inv.get("tax_point_code")))
        if b["rate"] is not None:
            _el(t, "RateApplicablePercent", fmt_num(b["rate"]))
    _period(se, inv.get("period"))
    for a in inv.get("allowances") or []:
        _allowance_charge(se, a, False, True)
    for c in inv.get("charges") or []:
        _allowance_charge(se, c, True, True)
    if pay.get("terms") or inv.get("due_date") or dd.get("mandate_id"):
        pt = _el(se, "SpecifiedTradePaymentTerms")
        _opt(pt, "Description", pay.get("terms"))
        _date(pt, "DueDateDateTime", inv.get("due_date"))
        _opt(pt, "DirectDebitMandateID", dd.get("mandate_id"))

    t = inv["totals"]
    ms = _el(se, "SpecifiedTradeSettlementHeaderMonetarySummation")
    _amt(ms, "LineTotalAmount", t["line_total"])
    if inv.get("charges"):
        _amt(ms, "ChargeTotalAmount", t["charge_total"])
    if inv.get("allowances"):
        _amt(ms, "AllowanceTotalAmount", t["allowance_total"])
    _amt(ms, "TaxBasisTotalAmount", t["tax_exclusive"])
    _amt(ms, "TaxTotalAmount", t["tax_total"], cur)
    if "tax_total_tax_currency" in t:
        _amt(ms, "TaxTotalAmount", t["tax_total_tax_currency"], inv["tax_currency"])
    if t["rounding"]:
        _amt(ms, "RoundingAmount", t["rounding"])
    _amt(ms, "GrandTotalAmount", t["tax_inclusive"])
    if t["prepaid"]:
        _amt(ms, "TotalPrepaidAmount", t["prepaid"])
    _amt(ms, "DuePayableAmount", t["payable"])
    for p in inv.get("preceding_invoices") or []:
        r = _el(se, "InvoiceReferencedDocument")
        _el(r, "IssuerAssignedID", p.get("number"))
        _date(r, "FormattedIssueDateTime", p.get("date"), ns_child=QDT)
    if inv.get("accounting_reference"):
        _el(_el(se, "ReceivableSpecifiedTradeAccountingAccount"), "ID", inv["accounting_reference"])

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


def _line(tx, ln):
    li = _el(tx, "IncludedSupplyChainTradeLineItem")
    ad = _el(li, "AssociatedDocumentLineDocument")
    _el(ad, "LineID", ln["id"])
    if ln.get("note"):
        _el(_el(ad, "IncludedNote"), "Content", ln["note"])

    pr = _el(li, "SpecifiedTradeProduct")
    sid = ln.get("standard_item_id")
    if sid:
        sid = sid if isinstance(sid, dict) else {"id": sid, "scheme": "0160"}
        _el(pr, "GlobalID", sid["id"], schemeID=sid.get("scheme"))
    _opt(pr, "SellerAssignedID", ln.get("seller_item_id"))
    _opt(pr, "BuyerAssignedID", ln.get("buyer_item_id"))
    _el(pr, "Name", ln.get("name"))
    _opt(pr, "Description", ln.get("description"))
    for at in ln.get("attributes") or []:
        c = _el(pr, "ApplicableProductCharacteristic")
        _el(c, "Description", at["name"])
        _el(c, "Value", at["value"])
    for cl in ln.get("classifications") or []:
        c = _el(pr, "DesignatedProductClassification")
        _el(c, "ClassCode", cl["id"], listID=cl.get("scheme"), listVersionID=cl.get("version"))
    if ln.get("origin_country"):
        _el(_el(pr, "OriginTradeCountry"), "ID", ln["origin_country"])

    ag = _el(li, "SpecifiedLineTradeAgreement")
    if ln.get("order_line_reference"):
        _el(_el(ag, "BuyerOrderReferencedDocument"), "LineID", ln["order_line_reference"])
    unit = ln.get("base_unit") or ln["unit"]
    if ln.get("gross_price") is not None:
        gp = _el(ag, "GrossPriceProductTradePrice")
        _el(gp, "ChargeAmount", fmt_num(ln["gross_price"]))
        if ln.get("base_quantity") is not None:
            _el(gp, "BasisQuantity", fmt_num(ln["base_quantity"]), unitCode=unit)
        if ln.get("price_discount"):
            ac = _el(gp, "AppliedTradeAllowanceCharge")
            _el(_el(ac, "ChargeIndicator"), "Indicator", "false", ns=UDT)
            _el(ac, "ActualAmount", fmt_num(ln["price_discount"]))
    np_ = _el(ag, "NetPriceProductTradePrice")
    _el(np_, "ChargeAmount", fmt_num(ln["price"]))
    if ln.get("base_quantity") is not None:
        _el(np_, "BasisQuantity", fmt_num(ln["base_quantity"]), unitCode=unit)

    de = _el(li, "SpecifiedLineTradeDelivery")
    _el(de, "BilledQuantity", fmt_num(ln["quantity"]), unitCode=ln["unit"])

    se = _el(li, "SpecifiedLineTradeSettlement")
    t = _el(se, "ApplicableTradeTax")
    _el(t, "TypeCode", "VAT")
    _el(t, "CategoryCode", ln["vat_category"])
    if ln["vat_rate"] is not None:
        _el(t, "RateApplicablePercent", fmt_num(ln["vat_rate"]))
    _period(se, ln.get("period"))
    for a in ln.get("allowances") or []:
        _allowance_charge(se, a, False, False)
    for c in ln.get("charges") or []:
        _allowance_charge(se, c, True, False)
    _amt(_el(se, "SpecifiedTradeSettlementLineMonetarySummation"), "LineTotalAmount", ln["net_amount"])
    if ln.get("object_id"):
        o = ln["object_id"] if isinstance(ln["object_id"], dict) else {"id": ln["object_id"]}
        r = _el(se, "AdditionalReferencedDocument")
        _el(r, "IssuerAssignedID", o["id"])
        _el(r, "TypeCode", "130")
        _opt(r, "ReferenceTypeCode", o.get("scheme"))
    if ln.get("accounting_reference"):
        _el(_el(se, "ReceivableSpecifiedTradeAccountingAccount"), "ID", ln["accounting_reference"])
