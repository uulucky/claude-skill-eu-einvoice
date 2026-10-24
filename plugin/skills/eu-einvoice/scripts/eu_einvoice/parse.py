"""Read UBL / CII / Factur-X PDF into the JSON model (inverse of ubl.py/cii.py).

The output is the same shape the generators accept, so
extract -> edit -> create and convert (CII <-> UBL) are lossless for every
EN 16931 business term this skill models. Totals found in the document are
kept under "totals" so a re-generation cross-checks the arithmetic.
"""

from pathlib import Path

from lxml import etree

from .profiles import detect_profile

CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
UBL_NS = {"cbc": CBC, "cac": CAC}
RAM = "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
CII_NS = {
    "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
    "ram": RAM,
    "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
    "qdt": "urn:un:unece:uncefact:data:standard:QualifiedDataType:100",
}


def _clean(d):
    """Drop None / empty values recursively so the JSON stays readable."""
    if isinstance(d, dict):
        out = {}
        for k, v in d.items():
            v = _clean(v)
            if v not in (None, "", [], {}):
                out[k] = v
        return out
    if isinstance(d, list):
        return [x for x in (_clean(v) for v in d) if x not in (None, "", [], {})]
    return d


class _X:
    def __init__(self, ns):
        self.ns = ns

    def t(self, node, path):
        if node is None:
            return None
        r = node.xpath(path, namespaces=self.ns)
        if not r:
            return None
        v = r[0]
        v = v.text if hasattr(v, "text") else str(v)
        return v.strip() if v else None

    def el(self, node, path):
        if node is None:
            return None
        r = node.xpath(path, namespaces=self.ns)
        return r[0] if r else None

    def all(self, node, path):
        return node.xpath(path, namespaces=self.ns) if node is not None else []

    def idsch(self, node, path):
        e = self.el(node, path)
        if e is None or not (e.text or "").strip():
            return None
        d = {"id": e.text.strip()}
        if e.get("schemeID"):
            d["scheme"] = e.get("schemeID")
        return d


def _cii_date(s):
    if not s:
        return None
    s = s.strip()
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) == 8 and s.isdigit() else s


# --------------------------------------------------------------------------
# UBL
# --------------------------------------------------------------------------

def _ubl_address(x, a):
    if a is None:
        return None
    return {
        "line1": x.t(a, "cbc:StreetName"),
        "line2": x.t(a, "cbc:AdditionalStreetName"),
        "line3": x.t(a, "cac:AddressLine/cbc:Line"),
        "city": x.t(a, "cbc:CityName"),
        "postal_code": x.t(a, "cbc:PostalZone"),
        "subdivision": x.t(a, "cbc:CountrySubentity"),
        "country": x.t(a, "cac:Country/cbc:IdentificationCode"),
    }


# xs:boolean allows true/false/1/0
_TRUE = "normalize-space(cbc:ChargeIndicator)='true' or normalize-space(cbc:ChargeIndicator)='1'"
_FALSE = "normalize-space(cbc:ChargeIndicator)='false' or normalize-space(cbc:ChargeIndicator)='0'"


def _ubl_party(x, p, model):
    if p is None:
        return None
    d = {
        "name": x.t(p, "cac:PartyLegalEntity/cbc:RegistrationName"),
        "trading_name": x.t(p, "cac:PartyName/cbc:Name"),
        "electronic_address": x.idsch(p, "cbc:EndpointID"),
        "address": _ubl_address(x, x.el(p, "cac:PostalAddress")),
        "legal_id": x.idsch(p, "cac:PartyLegalEntity/cbc:CompanyID"),
        "legal_info": x.t(p, "cac:PartyLegalEntity/cbc:CompanyLegalForm"),
        "ids": [],
    }
    for e in x.all(p, "cac:PartyIdentification/cbc:ID"):
        if e.get("schemeID") == "SEPA":
            model.setdefault("payment", {}).setdefault("direct_debit", {})["creditor_id"] = e.text.strip()
            continue
        i = {"id": e.text.strip()}
        if e.get("schemeID"):
            i["scheme"] = e.get("schemeID")
        d["ids"].append(i)
    for ts in x.all(p, "cac:PartyTaxScheme"):
        if (x.t(ts, "cac:TaxScheme/cbc:ID") or "").upper() == "VAT":
            d["vat_id"] = x.t(ts, "cbc:CompanyID")
        else:
            d["tax_registration_id"] = x.t(ts, "cbc:CompanyID")
    c = x.el(p, "cac:Contact")
    if c is not None:
        d["contact"] = {"name": x.t(c, "cbc:Name"), "phone": x.t(c, "cbc:Telephone"), "email": x.t(c, "cbc:ElectronicMail")}
    if not d["name"]:
        d["name"] = d.pop("trading_name", None)
    return d


def _ubl_ac(x, e, with_tax):
    d = {
        "reason": x.t(e, "cbc:AllowanceChargeReason"),
        "reason_code": x.t(e, "cbc:AllowanceChargeReasonCode"),
        "percent": x.t(e, "cbc:MultiplierFactorNumeric"),
        "amount": x.t(e, "cbc:Amount"),
        "base_amount": x.t(e, "cbc:BaseAmount"),
    }
    if with_tax:
        d["vat_category"] = x.t(e, "cac:TaxCategory/cbc:ID")
        d["vat_rate"] = x.t(e, "cac:TaxCategory/cbc:Percent")
    return d


def parse_ubl(root):
    x = _X(UBL_NS)
    notes = []
    cn = etree.QName(root).localname == "CreditNote"
    m = {
        "profile": detect_profile(x.t(root, "cbc:CustomizationID"), "ubl"),
        "customization_id": x.t(root, "cbc:CustomizationID"),
        "process_id": x.t(root, "cbc:ProfileID"),
        "type": x.t(root, "cbc:CreditNoteTypeCode" if cn else "cbc:InvoiceTypeCode") or ("381" if cn else "380"),
        "number": x.t(root, "cbc:ID"),
        "issue_date": x.t(root, "cbc:IssueDate"),
        "due_date": x.t(root, "cbc:DueDate") or x.t(root, "cac:PaymentMeans/cbc:PaymentDueDate"),
        "tax_point_date": x.t(root, "cbc:TaxPointDate"),
        "currency": x.t(root, "cbc:DocumentCurrencyCode"),
        "tax_currency": x.t(root, "cbc:TaxCurrencyCode"),
        "accounting_reference": x.t(root, "cbc:AccountingCost"),
        "buyer_reference": x.t(root, "cbc:BuyerReference"),
        "order_reference": x.t(root, "cac:OrderReference/cbc:ID"),
        "sales_order_reference": x.t(root, "cac:OrderReference/cbc:SalesOrderID"),
        "despatch_advice_reference": x.t(root, "cac:DespatchDocumentReference/cbc:ID"),
        "receiving_advice_reference": x.t(root, "cac:ReceiptDocumentReference/cbc:ID"),
        "tender_reference": x.t(root, "cac:OriginatorDocumentReference/cbc:ID"),
        "contract_reference": x.t(root, "cac:ContractDocumentReference/cbc:ID"),
        "project_reference": x.t(root, "cac:ProjectReference/cbc:ID"),
        "notes": [],
    }
    if m["order_reference"] == "NA":
        m["order_reference"] = None
    for n in x.all(root, "cbc:Note"):
        text = (n.text or "").strip()
        if text.startswith("#") and text.count("#") >= 2 and len(text.split("#")[1]) == 3:
            _, subj, rest = text.split("#", 2)
            m["notes"].append({"subject": subj, "text": rest})
        else:
            m["notes"].append(text)
    per = x.el(root, "cac:InvoicePeriod")
    if per is not None:
        m["period"] = {"start": x.t(per, "cbc:StartDate"), "end": x.t(per, "cbc:EndDate")}
        m["tax_point_code"] = x.t(per, "cbc:DescriptionCode")
    m["preceding_invoices"] = [
        {"number": x.t(r, "cbc:ID"), "date": x.t(r, "cbc:IssueDate")}
        for r in x.all(root, "cac:BillingReference/cac:InvoiceDocumentReference")
    ]
    m["attachments"] = []
    for r in x.all(root, "cac:AdditionalDocumentReference"):
        code = x.t(r, "cbc:DocumentTypeCode")
        if code == "130":
            m["object_reference"] = x.idsch(r, "cbc:ID")
        elif code == "50":
            if cn:
                m["project_reference"] = x.t(r, "cbc:ID")
            else:
                m["tender_reference"] = m["tender_reference"] or x.t(r, "cbc:ID")
        else:
            b = x.el(r, "cac:Attachment/cbc:EmbeddedDocumentBinaryObject")
            m["attachments"].append({
                "id": x.t(r, "cbc:ID"),
                "description": x.t(r, "cbc:DocumentDescription"),
                "uri": x.t(r, "cac:Attachment/cac:ExternalReference/cbc:URI"),
                "content_b64": (b.text or "").strip() if b is not None else None,
                "mime": b.get("mimeCode") if b is not None else None,
                "filename": b.get("filename") if b is not None else None,
            })

    m["seller"] = _ubl_party(x, x.el(root, "cac:AccountingSupplierParty/cac:Party"), m)
    m["buyer"] = _ubl_party(x, x.el(root, "cac:AccountingCustomerParty/cac:Party"), m)
    pe = x.el(root, "cac:PayeeParty")
    if pe is not None:
        m["payee"] = {
            "name": x.t(pe, "cac:PartyName/cbc:Name"),
            "ids": [x.idsch(e, ".") for e in x.all(pe, "cac:PartyIdentification/cbc:ID") if e.get("schemeID") != "SEPA"],
            "legal_id": x.idsch(pe, "cac:PartyLegalEntity/cbc:CompanyID"),
        }
        sepa = x.t(pe, "cac:PartyIdentification/cbc:ID[@schemeID='SEPA']")
        if sepa:
            m.setdefault("payment", {}).setdefault("direct_debit", {})["creditor_id"] = sepa
    tr = x.el(root, "cac:TaxRepresentativeParty")
    if tr is not None:
        m["tax_representative"] = {
            "name": x.t(tr, "cac:PartyName/cbc:Name"),
            "address": _ubl_address(x, x.el(tr, "cac:PostalAddress")),
            "vat_id": x.t(tr, "cac:PartyTaxScheme/cbc:CompanyID"),
        }
    de = x.el(root, "cac:Delivery")
    if de is not None:
        m["delivery"] = {
            "date": x.t(de, "cbc:ActualDeliveryDate"),
            "location_id": x.idsch(de, "cac:DeliveryLocation/cbc:ID"),
            "address": _ubl_address(x, x.el(de, "cac:DeliveryLocation/cac:Address")),
            "party_name": x.t(de, "cac:DeliveryParty/cac:PartyName/cbc:Name"),
        }
        if len(x.all(root, "cac:Delivery")) > 1:
            notes.append("more than one Delivery: only the first is kept (EN 16931 has one)")

    pms = x.all(root, "cac:PaymentMeans")
    pay = m.setdefault("payment", {})
    if pms:
        first = pms[0]
        pay["means_code"] = x.t(first, "cbc:PaymentMeansCode")
        code_el = x.el(first, "cbc:PaymentMeansCode")
        pay["means_text"] = code_el.get("name") if code_el is not None else None
        pay["remittance_info"] = x.t(first, "cbc:PaymentID")
        if len({x.t(p, "cbc:PaymentMeansCode") for p in pms}) > 1:
            notes.append("several different payment means codes: only the first code is kept")
        cts = []
        for p in pms:
            fa = x.el(p, "cac:PayeeFinancialAccount")
            if fa is not None:
                acct = x.t(fa, "cbc:ID") or ""
                ct = {"account_name": x.t(fa, "cbc:Name"), "bic": x.t(fa, "cac:FinancialInstitutionBranch/cbc:ID")}
                ct["iban" if acct[:2].isalpha() and acct[2:4].isdigit() else "account_id"] = acct
                cts.append(ct)
        pay["credit_transfers"] = cts
        ca = x.el(first, "cac:CardAccount")
        if ca is not None:
            pay["card"] = {"pan_last4": x.t(ca, "cbc:PrimaryAccountNumberID"), "network": x.t(ca, "cbc:NetworkID"), "holder": x.t(ca, "cbc:HolderName")}
        md = x.el(first, "cac:PaymentMandate")
        if md is not None:
            dd = pay.setdefault("direct_debit", {})
            dd["mandate_id"] = x.t(md, "cbc:ID")
            dd["debited_account"] = x.t(md, "cac:PayerFinancialAccount/cbc:ID")
    pay["terms"] = x.t(root, "cac:PaymentTerms/cbc:Note")

    m["allowances"] = [_ubl_ac(x, e, True) for e in x.all(root, f"cac:AllowanceCharge[{_FALSE}]")]
    m["charges"] = [_ubl_ac(x, e, True) for e in x.all(root, f"cac:AllowanceCharge[{_TRUE}]")]

    m["vat_exemptions"] = {}
    m["vat_breakdown"] = []
    for st in x.all(root, "cac:TaxTotal/cac:TaxSubtotal"):
        cat = x.t(st, "cac:TaxCategory/cbc:ID")
        m["vat_breakdown"].append({"category": cat, "rate": x.t(st, "cac:TaxCategory/cbc:Percent"),
                                   "taxable": x.t(st, "cbc:TaxableAmount"), "tax": x.t(st, "cbc:TaxAmount")})
        reason, code = x.t(st, "cac:TaxCategory/cbc:TaxExemptionReason"), x.t(st, "cac:TaxCategory/cbc:TaxExemptionReasonCode")
        if reason or code:
            m["vat_exemptions"][cat] = {"reason": reason, "code": code}
    cur = m["currency"]
    tax_totals = x.all(root, "cac:TaxTotal")
    tax_amount = None
    for tt in tax_totals:
        amt = x.el(tt, "cbc:TaxAmount")
        if amt is not None and amt.get("currencyID") == cur:
            tax_amount = amt.text.strip()
        elif amt is not None and m.get("tax_currency"):
            m["tax_total_in_tax_currency"] = amt.text.strip()
    mt = x.el(root, "cac:LegalMonetaryTotal")
    m["totals"] = {
        "line_total": x.t(mt, "cbc:LineExtensionAmount"),
        "allowance_total": x.t(mt, "cbc:AllowanceTotalAmount"),
        "charge_total": x.t(mt, "cbc:ChargeTotalAmount"),
        "tax_exclusive": x.t(mt, "cbc:TaxExclusiveAmount"),
        "tax_total": tax_amount,
        "tax_inclusive": x.t(mt, "cbc:TaxInclusiveAmount"),
        "prepaid": x.t(mt, "cbc:PrepaidAmount"),
        "rounding": x.t(mt, "cbc:PayableRoundingAmount"),
        "payable": x.t(mt, "cbc:PayableAmount"),
    }
    m["prepaid_amount"] = m["totals"]["prepaid"]
    m["rounding_amount"] = m["totals"]["rounding"]

    m["lines"] = []
    for ln in x.all(root, "cac:InvoiceLine|cac:CreditNoteLine"):
        qty_el = x.el(ln, "cbc:InvoicedQuantity|cbc:CreditedQuantity")
        item = x.el(ln, "cac:Item")
        price = x.el(ln, "cac:Price")
        bq = x.el(price, "cbc:BaseQuantity")
        d = {
            "id": x.t(ln, "cbc:ID"),
            "note": x.t(ln, "cbc:Note"),
            "quantity": qty_el.text.strip() if qty_el is not None else None,
            "unit": qty_el.get("unitCode") if qty_el is not None else None,
            "net_amount": x.t(ln, "cbc:LineExtensionAmount"),
            "accounting_reference": x.t(ln, "cbc:AccountingCost"),
            "order_line_reference": x.t(ln, "cac:OrderLineReference/cbc:LineID"),
            "object_id": x.idsch(ln, "cac:DocumentReference[cbc:DocumentTypeCode='130']/cbc:ID"),
            "name": x.t(item, "cbc:Name"),
            "description": x.t(item, "cbc:Description"),
            "seller_item_id": x.t(item, "cac:SellersItemIdentification/cbc:ID"),
            "buyer_item_id": x.t(item, "cac:BuyersItemIdentification/cbc:ID"),
            "standard_item_id": x.idsch(item, "cac:StandardItemIdentification/cbc:ID"),
            "origin_country": x.t(item, "cac:OriginCountry/cbc:IdentificationCode"),
            "classifications": [
                {"id": e.text.strip(), "scheme": e.get("listID"), "version": e.get("listVersionID")}
                for e in x.all(item, "cac:CommodityClassification/cbc:ItemClassificationCode")
            ],
            "vat_category": x.t(item, "cac:ClassifiedTaxCategory/cbc:ID"),
            "vat_rate": x.t(item, "cac:ClassifiedTaxCategory/cbc:Percent"),
            "attributes": [
                {"name": x.t(e, "cbc:Name"), "value": x.t(e, "cbc:Value")}
                for e in x.all(item, "cac:AdditionalItemProperty")
            ],
            "price": x.t(price, "cbc:PriceAmount"),
            "base_quantity": bq.text.strip() if bq is not None else None,
            "base_unit": bq.get("unitCode") if bq is not None and bq.get("unitCode") != (qty_el.get("unitCode") if qty_el is not None else None) else None,
            "gross_price": x.t(price, "cac:AllowanceCharge/cbc:BaseAmount"),
            "price_discount": x.t(price, "cac:AllowanceCharge/cbc:Amount"),
            "allowances": [_ubl_ac(x, e, False) for e in x.all(ln, f"cac:AllowanceCharge[{_FALSE}]")],
            "charges": [_ubl_ac(x, e, False) for e in x.all(ln, f"cac:AllowanceCharge[{_TRUE}]")],
        }
        p = x.el(ln, "cac:InvoicePeriod")
        if p is not None:
            d["period"] = {"start": x.t(p, "cbc:StartDate"), "end": x.t(p, "cbc:EndDate")}
        if d["gross_price"] is None and d["price_discount"] is not None:
            d["price_discount"] = None
        m["lines"].append(d)
    return _clean(m), notes


# --------------------------------------------------------------------------
# CII
# --------------------------------------------------------------------------

def _cii_address(x, a):
    if a is None:
        return None
    return {
        "line1": x.t(a, "ram:LineOne"),
        "line2": x.t(a, "ram:LineTwo"),
        "line3": x.t(a, "ram:LineThree"),
        "city": x.t(a, "ram:CityName"),
        "postal_code": x.t(a, "ram:PostcodeCode"),
        "subdivision": x.t(a, "ram:CountrySubDivisionName"),
        "country": x.t(a, "ram:CountryID"),
    }


def _cii_party(x, p):
    if p is None:
        return None
    d = {
        "name": x.t(p, "ram:Name"),
        "legal_info": x.t(p, "ram:Description"),
        "trading_name": x.t(p, "ram:SpecifiedLegalOrganization/ram:TradingBusinessName"),
        "legal_id": x.idsch(p, "ram:SpecifiedLegalOrganization/ram:ID"),
        "address": _cii_address(x, x.el(p, "ram:PostalTradeAddress")),
        "electronic_address": x.idsch(p, "ram:URIUniversalCommunication/ram:URIID"),
        "ids": [{"id": e.text.strip()} for e in x.all(p, "ram:ID")]
        + [{"id": e.text.strip(), "scheme": e.get("schemeID")} for e in x.all(p, "ram:GlobalID")],
        "vat_id": x.t(p, "ram:SpecifiedTaxRegistration/ram:ID[@schemeID='VA']"),
        "tax_registration_id": x.t(p, "ram:SpecifiedTaxRegistration/ram:ID[@schemeID='FC']"),
    }
    c = x.el(p, "ram:DefinedTradeContact")
    if c is not None:
        d["contact"] = {
            "name": x.t(c, "ram:PersonName") or x.t(c, "ram:DepartmentName"),
            "phone": x.t(c, "ram:TelephoneUniversalCommunication/ram:CompleteNumber"),
            "email": x.t(c, "ram:EmailURIUniversalCommunication/ram:URIID"),
        }
    return d


def _cii_ac(x, e, with_tax):
    ind = (x.t(e, "ram:ChargeIndicator/udt:Indicator") or "").lower()
    d = {
        "_charge": ind in ("true", "1"),
        "reason": x.t(e, "ram:Reason"),
        "reason_code": x.t(e, "ram:ReasonCode"),
        "percent": x.t(e, "ram:CalculationPercent"),
        "amount": x.t(e, "ram:ActualAmount"),
        "base_amount": x.t(e, "ram:BasisAmount"),
    }
    if with_tax:
        d["vat_category"] = x.t(e, "ram:CategoryTradeTax/ram:CategoryCode")
        d["vat_rate"] = x.t(e, "ram:CategoryTradeTax/ram:RateApplicablePercent")
    return d


def _split_ac(items):
    allow, charge = [], []
    for i in items:
        (charge if i.pop("_charge") else allow).append(i)
    return allow, charge


def parse_cii(root):
    x = _X(CII_NS)
    notes = []
    guideline = x.t(root, "rsm:ExchangedDocumentContext/ram:GuidelineSpecifiedDocumentContextParameter/ram:ID")
    doc = x.el(root, "rsm:ExchangedDocument")
    tx = x.el(root, "rsm:SupplyChainTradeTransaction")
    ag = x.el(tx, "ram:ApplicableHeaderTradeAgreement")
    dl = x.el(tx, "ram:ApplicableHeaderTradeDelivery")
    se = x.el(tx, "ram:ApplicableHeaderTradeSettlement")
    m = {
        "profile": detect_profile(guideline, "cii"),
        "customization_id": guideline,
        "process_id": x.t(root, "rsm:ExchangedDocumentContext/ram:BusinessProcessSpecifiedDocumentContextParameter/ram:ID"),
        "type": x.t(doc, "ram:TypeCode"),
        "number": x.t(doc, "ram:ID"),
        "issue_date": _cii_date(x.t(doc, "ram:IssueDateTime/udt:DateTimeString")),
        "notes": [],
        "buyer_reference": x.t(ag, "ram:BuyerReference"),
        "order_reference": x.t(ag, "ram:BuyerOrderReferencedDocument/ram:IssuerAssignedID"),
        "sales_order_reference": x.t(ag, "ram:SellerOrderReferencedDocument/ram:IssuerAssignedID"),
        "contract_reference": x.t(ag, "ram:ContractReferencedDocument/ram:IssuerAssignedID"),
        "project_reference": x.t(ag, "ram:SpecifiedProcuringProject/ram:ID"),
        "despatch_advice_reference": x.t(dl, "ram:DespatchAdviceReferencedDocument/ram:IssuerAssignedID"),
        "receiving_advice_reference": x.t(dl, "ram:ReceivingAdviceReferencedDocument/ram:IssuerAssignedID"),
        "currency": x.t(se, "ram:InvoiceCurrencyCode"),
        "tax_currency": x.t(se, "ram:TaxCurrencyCode"),
        "accounting_reference": x.t(se, "ram:ReceivableSpecifiedTradeAccountingAccount/ram:ID"),
        "due_date": _cii_date(x.t(se, "ram:SpecifiedTradePaymentTerms/ram:DueDateDateTime/udt:DateTimeString")),
        "tax_point_date": _cii_date(x.t(se, "ram:ApplicableTradeTax/ram:TaxPointDate/udt:DateString")),
        "tax_point_code": x.t(se, "ram:ApplicableTradeTax/ram:DueDateTypeCode"),
    }
    for n in x.all(doc, "ram:IncludedNote"):
        content, subj = x.t(n, "ram:Content"), x.t(n, "ram:SubjectCode")
        m["notes"].append({"subject": subj, "text": content} if subj else content)
    m["attachments"] = []
    for r in x.all(ag, "ram:AdditionalReferencedDocument"):
        code = x.t(r, "ram:TypeCode")
        if code == "130":
            m["object_reference"] = {"id": x.t(r, "ram:IssuerAssignedID"), "scheme": x.t(r, "ram:ReferenceTypeCode")}
        elif code == "50":
            m["tender_reference"] = x.t(r, "ram:IssuerAssignedID")
        else:
            b = x.el(r, "ram:AttachmentBinaryObject")
            m["attachments"].append({
                "id": x.t(r, "ram:IssuerAssignedID"),
                "description": x.t(r, "ram:Name"),
                "uri": x.t(r, "ram:URIID"),
                "content_b64": (b.text or "").strip() if b is not None else None,
                "mime": b.get("mimeCode") if b is not None else None,
                "filename": b.get("filename") if b is not None else None,
            })
    per = x.el(se, "ram:BillingSpecifiedPeriod")
    if per is not None:
        m["period"] = {"start": _cii_date(x.t(per, "ram:StartDateTime/udt:DateTimeString")),
                       "end": _cii_date(x.t(per, "ram:EndDateTime/udt:DateTimeString"))}
    m["preceding_invoices"] = [
        {"number": x.t(r, "ram:IssuerAssignedID"), "date": _cii_date(x.t(r, "ram:FormattedIssueDateTime/qdt:DateTimeString"))}
        for r in x.all(se, "ram:InvoiceReferencedDocument")
    ]
    m["seller"] = _cii_party(x, x.el(ag, "ram:SellerTradeParty"))
    m["buyer"] = _cii_party(x, x.el(ag, "ram:BuyerTradeParty"))
    rep = x.el(ag, "ram:SellerTaxRepresentativeTradeParty")
    if rep is not None:
        m["tax_representative"] = {"name": x.t(rep, "ram:Name"), "address": _cii_address(x, x.el(rep, "ram:PostalTradeAddress")),
                                   "vat_id": x.t(rep, "ram:SpecifiedTaxRegistration/ram:ID")}
    pe = x.el(se, "ram:PayeeTradeParty")
    if pe is not None:
        m["payee"] = {"name": x.t(pe, "ram:Name"),
                      "ids": [{"id": e.text.strip()} for e in x.all(pe, "ram:ID")]
                      + [{"id": e.text.strip(), "scheme": e.get("schemeID")} for e in x.all(pe, "ram:GlobalID")],
                      "legal_id": x.idsch(pe, "ram:SpecifiedLegalOrganization/ram:ID")}
    st = x.el(dl, "ram:ShipToTradeParty")
    ddate = _cii_date(x.t(dl, "ram:ActualDeliverySupplyChainEvent/ram:OccurrenceDateTime/udt:DateTimeString"))
    if st is not None or ddate:
        loc = x.idsch(st, "ram:GlobalID") or x.idsch(st, "ram:ID")
        m["delivery"] = {"date": ddate, "party_name": x.t(st, "ram:Name"), "location_id": loc,
                         "address": _cii_address(x, x.el(st, "ram:PostalTradeAddress"))}

    pay = {"remittance_info": x.t(se, "ram:PaymentReference"),
           "terms": x.t(se, "ram:SpecifiedTradePaymentTerms/ram:Description")}
    pms = x.all(se, "ram:SpecifiedTradeSettlementPaymentMeans")
    if pms:
        pay["means_code"] = x.t(pms[0], "ram:TypeCode")
        pay["means_text"] = x.t(pms[0], "ram:Information")
        if len({x.t(p, "ram:TypeCode") for p in pms}) > 1:
            notes.append("several different payment means codes: only the first code is kept")
        cts = []
        for p in pms:
            fa = x.el(p, "ram:PayeePartyCreditorFinancialAccount")
            if fa is not None:
                cts.append({"iban": x.t(fa, "ram:IBANID"), "account_id": x.t(fa, "ram:ProprietaryID"),
                            "account_name": x.t(fa, "ram:AccountName"),
                            "bic": x.t(p, "ram:PayeeSpecifiedCreditorFinancialInstitution/ram:BICID")})
        pay["credit_transfers"] = cts
        card = x.el(pms[0], "ram:ApplicableTradeSettlementFinancialCard")
        if card is not None:
            pay["card"] = {"pan_last4": x.t(card, "ram:ID"), "holder": x.t(card, "ram:CardholderName")}
        dd = {"debited_account": x.t(pms[0], "ram:PayerPartyDebtorFinancialAccount/ram:IBANID")}
    else:
        dd = {}
    dd["mandate_id"] = x.t(se, "ram:SpecifiedTradePaymentTerms/ram:DirectDebitMandateID")
    dd["creditor_id"] = x.t(se, "ram:CreditorReferenceID")
    pay["direct_debit"] = dd
    m["payment"] = pay

    m["allowances"], m["charges"] = _split_ac([_cii_ac(x, e, True) for e in x.all(se, "ram:SpecifiedTradeAllowanceCharge")])
    m["vat_exemptions"] = {}
    m["vat_breakdown"] = []
    for t in x.all(se, "ram:ApplicableTradeTax"):
        m["vat_breakdown"].append({"category": x.t(t, "ram:CategoryCode"), "rate": x.t(t, "ram:RateApplicablePercent"),
                                   "taxable": x.t(t, "ram:BasisAmount"), "tax": x.t(t, "ram:CalculatedAmount")})
        reason, code = x.t(t, "ram:ExemptionReason"), x.t(t, "ram:ExemptionReasonCode")
        if reason or code:
            m["vat_exemptions"][x.t(t, "ram:CategoryCode")] = {"reason": reason, "code": code}
    ms = x.el(se, "ram:SpecifiedTradeSettlementHeaderMonetarySummation")
    cur = m["currency"]
    tax_total = None
    for e in x.all(ms, "ram:TaxTotalAmount"):
        if e.get("currencyID") in (None, cur):
            tax_total = e.text.strip()
        else:
            m["tax_total_in_tax_currency"] = e.text.strip()
    m["totals"] = {
        "line_total": x.t(ms, "ram:LineTotalAmount"),
        "charge_total": x.t(ms, "ram:ChargeTotalAmount"),
        "allowance_total": x.t(ms, "ram:AllowanceTotalAmount"),
        "tax_exclusive": x.t(ms, "ram:TaxBasisTotalAmount"),
        "tax_total": tax_total,
        "rounding": x.t(ms, "ram:RoundingAmount"),
        "tax_inclusive": x.t(ms, "ram:GrandTotalAmount"),
        "prepaid": x.t(ms, "ram:TotalPrepaidAmount"),
        "payable": x.t(ms, "ram:DuePayableAmount"),
    }
    m["prepaid_amount"] = m["totals"]["prepaid"]
    m["rounding_amount"] = m["totals"]["rounding"]

    m["lines"] = []
    for li in x.all(tx, "ram:IncludedSupplyChainTradeLineItem"):
        pr = x.el(li, "ram:SpecifiedTradeProduct")
        la = x.el(li, "ram:SpecifiedLineTradeAgreement")
        ls = x.el(li, "ram:SpecifiedLineTradeSettlement")
        q = x.el(li, "ram:SpecifiedLineTradeDelivery/ram:BilledQuantity")
        nb = x.el(la, "ram:NetPriceProductTradePrice/ram:BasisQuantity")
        gb = x.el(la, "ram:GrossPriceProductTradePrice/ram:BasisQuantity")
        bq = nb if nb is not None else gb
        allow, charge = _split_ac([_cii_ac(x, e, False) for e in x.all(ls, "ram:SpecifiedTradeAllowanceCharge")])
        d = {
            "id": x.t(li, "ram:AssociatedDocumentLineDocument/ram:LineID"),
            "note": x.t(li, "ram:AssociatedDocumentLineDocument/ram:IncludedNote/ram:Content"),
            "name": x.t(pr, "ram:Name"),
            "description": x.t(pr, "ram:Description"),
            "seller_item_id": x.t(pr, "ram:SellerAssignedID"),
            "buyer_item_id": x.t(pr, "ram:BuyerAssignedID"),
            "standard_item_id": x.idsch(pr, "ram:GlobalID"),
            "origin_country": x.t(pr, "ram:OriginTradeCountry/ram:ID"),
            "classifications": [{"id": e.text.strip(), "scheme": e.get("listID"), "version": e.get("listVersionID")}
                                for e in x.all(pr, "ram:DesignatedProductClassification/ram:ClassCode")],
            "attributes": [{"name": x.t(e, "ram:Description"), "value": x.t(e, "ram:Value")}
                           for e in x.all(pr, "ram:ApplicableProductCharacteristic")],
            "order_line_reference": x.t(la, "ram:BuyerOrderReferencedDocument/ram:LineID"),
            "price": x.t(la, "ram:NetPriceProductTradePrice/ram:ChargeAmount"),
            "gross_price": x.t(la, "ram:GrossPriceProductTradePrice/ram:ChargeAmount"),
            "price_discount": x.t(la, "ram:GrossPriceProductTradePrice/ram:AppliedTradeAllowanceCharge/ram:ActualAmount"),
            "base_quantity": bq.text.strip() if bq is not None else None,
            "base_unit": bq.get("unitCode") if bq is not None and q is not None and bq.get("unitCode") != q.get("unitCode") else None,
            "quantity": q.text.strip() if q is not None else None,
            "unit": q.get("unitCode") if q is not None else None,
            "vat_category": x.t(ls, "ram:ApplicableTradeTax/ram:CategoryCode"),
            "vat_rate": x.t(ls, "ram:ApplicableTradeTax/ram:RateApplicablePercent"),
            "allowances": allow,
            "charges": charge,
            "net_amount": x.t(ls, "ram:SpecifiedTradeSettlementLineMonetarySummation/ram:LineTotalAmount"),
            "accounting_reference": x.t(ls, "ram:ReceivableSpecifiedTradeAccountingAccount/ram:ID"),
        }
        obj = x.el(ls, "ram:AdditionalReferencedDocument[ram:TypeCode='130']")
        if obj is not None:
            d["object_id"] = {"id": x.t(obj, "ram:IssuerAssignedID"), "scheme": x.t(obj, "ram:ReferenceTypeCode")}
        p = x.el(ls, "ram:BillingSpecifiedPeriod")
        if p is not None:
            d["period"] = {"start": _cii_date(x.t(p, "ram:StartDateTime/udt:DateTimeString")),
                           "end": _cii_date(x.t(p, "ram:EndDateTime/udt:DateTimeString"))}
        m["lines"].append(d)
    return _clean(m), notes


def parse_bytes(data):
    notes = []
    if data[:5] == b"%PDF-":
        from .validate import extract_xml_from_pdf
        fname, xml = extract_xml_from_pdf(data)
        if not xml:
            raise ValueError("PDF contains no embedded e-invoice XML (not Factur-X/ZUGFeRD); it is just a picture of an invoice")
        notes.append(f"read embedded {fname} from PDF")
        data = xml
    root = etree.fromstring(data)
    ns = etree.QName(root).namespace
    if ns in ("urn:oasis:names:specification:ubl:schema:xsd:Invoice-2", "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"):
        model, n2 = parse_ubl(root)
    elif ns == CII_NS["rsm"]:
        model, n2 = parse_cii(root)
    else:
        raise ValueError(f"unsupported root element {root.tag}")
    return model, notes + n2


def parse_file(path):
    return parse_bytes(Path(path).read_bytes())
