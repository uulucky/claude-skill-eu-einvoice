"""Invoice data model: load JSON, normalise, calculate, pre-check.

The JSON model uses readable keys; every key maps to an EN 16931 business
term (BT-xx / BG-xx). See references/data-model.md for the full mapping.

The single most common reason real-world e-invoices are rejected is
arithmetic: line totals, VAT breakdown and document totals that do not add
up to the cent the way EN 16931 (BR-CO-xx) and Peppol (R040-R120) demand.
So this module *computes* those values from the line data instead of
trusting what the caller typed, and only cross-checks caller-supplied
totals against the computed ones.
"""

import copy
import datetime
import json
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from . import identifiers

TWO = Decimal("0.01")
ZERO = Decimal("0")
HUNDRED = Decimal("100")

TYPE_CODES = {
    "invoice": "380",
    "commercial_invoice": "380",
    "credit_note": "381",
    "debit_note": "383",
    "corrected": "384",
    "corrected_invoice": "384",
    "prepayment": "386",
    "prepayment_invoice": "386",
    "self_billed": "389",
    "self_billed_invoice": "389",
    "self_billed_credit_note": "261",
    "partial": "326",
    "partial_invoice": "326",
}
CREDIT_NOTE_CODES = {"381", "261", "262", "296", "308", "396", "420", "458", "532"}

# VAT categories (UNCL5305 subset used by EN 16931) and the default
# exemption reason code we fill in when the caller gives none.
VAT_CATEGORIES = {
    "S": "Standard rate",
    "Z": "Zero rated goods",
    "E": "Exempt from tax",
    "AE": "VAT reverse charge",
    "K": "Intra-community supply (VAT exempt for EEA)",
    "G": "Free export item, tax not charged",
    "O": "Services outside scope of tax",
    "L": "Canary Islands general indirect tax (IGIC)",
    "M": "Tax for production, services and importation in Ceuta and Melilla (IPSI)",
    "B": "Transferred (VAT), Italy split payment",
}
DEFAULT_EXEMPTION = {
    "AE": ("VATEX-EU-AE", "Reverse charge"),
    "K": ("VATEX-EU-IC", "Intra-Community supply"),
    "G": ("VATEX-EU-G", "Export outside the EU"),
    "O": ("VATEX-EU-O", "Not subject to VAT"),
}
RULE_PREFIX = {"S": "S", "Z": "Z", "E": "E", "AE": "AE", "K": "IC", "G": "G", "O": "O", "L": "IG", "M": "IP", "B": "B"}
# BT-8 "VAT point date code" uses different code lists per syntax.
TAX_POINT_CODES = {"3": "invoice", "5": "invoice", "35": "delivery", "29": "delivery", "432": "payment", "72": "payment"}
TAX_POINT_UBL = {"invoice": "3", "delivery": "35", "payment": "432"}
TAX_POINT_CII = {"invoice": "5", "delivery": "29", "payment": "72"}
CREDIT_TRANSFER_CODES = {"30", "58"}
CARD_CODES = {"48", "54", "55"}
DIRECT_DEBIT_CODES = {"49", "59"}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class Issues(list):
    def add(self, level, path, msg):
        self.append({"level": level, "path": path, "msg": msg})

    def error(self, path, msg):
        self.add("error", path, msg)

    def warn(self, path, msg):
        self.add("warning", path, msg)

    def info(self, path, msg):
        self.add("info", path, msg)

    @property
    def errors(self):
        return [i for i in self if i["level"] == "error"]


# --------------------------------------------------------------------------
# Number helpers
# --------------------------------------------------------------------------

def dec(value, path, issues, required=False):
    if value is None or value == "":
        if required:
            issues.error(path, "is required")
        return None
    if isinstance(value, float):
        value = repr(value)
    try:
        d = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        issues.error(path, f"'{value}' is not a number")
        return None
    if not d.is_finite():
        issues.error(path, f"'{value}' is not a finite number")
        return None
    return d


def r2(d):
    d = d.quantize(TWO, rounding=ROUND_HALF_UP)
    return d.copy_abs() if d.is_zero() else d  # never emit "-0.00"


def fmt_amount(d):
    """Monetary amounts: always exactly 2 decimals (EN 16931 / Peppol)."""
    return str(r2(d))


def fmt_price(d):
    """Unit prices for display: at least 2 decimals, more only if present."""
    s = fmt_num(d)
    whole, _, frac = s.partition(".")
    return f"{whole}.{frac.ljust(2, '0')}"


def fmt_num(d):
    """Quantities, prices, percentages: shortest exact decimal."""
    if d is None:
        return None
    s = format(d.normalize(), "f")
    return s if s not in ("-0",) else "0"


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

def load(path_or_dict):
    if isinstance(path_or_dict, dict):
        return copy.deepcopy(path_or_dict)
    with open(path_or_dict, encoding="utf-8") as fh:
        return json.load(fh)


def type_code_of(inv):
    t = str(inv.get("type") or inv.get("type_code") or "invoice").strip().lower()
    return TYPE_CODES.get(t, t)


def is_credit_note(inv):
    return type_code_of(inv) in CREDIT_NOTE_CODES


def _check_date(inv_part, key, path, issues, required=False):
    v = inv_part.get(key)
    if v in (None, ""):
        if required:
            issues.error(path, "is required (YYYY-MM-DD)")
        return
    if isinstance(v, (datetime.date, datetime.datetime)):
        inv_part[key] = v.strftime("%Y-%m-%d")
        return
    v = str(v).strip()
    if not DATE_RE.match(v):
        issues.error(path, f"'{v}' must be an ISO date YYYY-MM-DD")
        return
    try:
        datetime.date.fromisoformat(v)
    except ValueError:
        issues.error(path, f"'{v}' is not a valid calendar date")
        return
    inv_part[key] = v


def _calc_allowance_charge(ac, path, issues, default_base=None, soft=None):
    """Fill `amount` from percent x base when only the percentage is given.

    Peppol R040: amount = base x percent / 100 (rounded), so we compute it
    that way rather than accepting an independently rounded figure.
    """
    amount = dec(ac.get("amount"), path + ".amount", issues)
    percent = dec(ac.get("percent"), path + ".percent", issues)
    base = dec(ac.get("base_amount"), path + ".base_amount", issues)
    if percent is not None and base is None and default_base is not None:
        base = r2(default_base)
    if amount is None:
        if percent is None or base is None:
            issues.error(path, "needs 'amount', or 'percent' together with 'base_amount'")
            amount = ZERO
        else:
            amount = r2(base * percent / HUNDRED)
    elif percent is not None and base is not None:
        expected = r2(base * percent / HUNDRED)
        if r2(amount) != expected:
            (soft or issues.error)(
                path,
                f"amount {fmt_amount(amount)} != base_amount {fmt_amount(base)} x "
                f"{fmt_num(percent)}% = {fmt_amount(expected)} (Peppol R040 / BR-CO)",
            )
    ac["amount"] = r2(amount)
    ac["percent"] = percent
    ac["base_amount"] = r2(base) if base is not None else None
    if not (ac.get("reason") or ac.get("reason_code")):
        issues.error(path, "needs 'reason' or 'reason_code' (BR-33/BR-38/BR-42/BR-44)")
    return ac["amount"]


# --------------------------------------------------------------------------
# Main entry point
# --------------------------------------------------------------------------

def prepare(raw, profile_key=None, trust_amounts=False):
    """Return (invoice, issues). The invoice is a normalised deep copy with
    all computed amounts filled in; it is what the generators consume.

    trust_amounts=True is for documents that already exist (convert/render):
    line net amounts given in the source are kept even when they do not
    match quantity x price, so the output says what the source said. Such
    mismatches become warnings (errors for Peppol, whose R120 is fatal).
    New invoices should leave it False and let every amount be computed."""
    inv = load(raw)
    issues = Issues()
    soft = issues.warn if trust_amounts and profile_key != "peppol" else issues.error

    inv["type_code"] = type_code_of(inv)
    inv["is_credit_note"] = inv["type_code"] in CREDIT_NOTE_CODES
    if not inv.get("number"):
        issues.error("number", "invoice number (BT-1) is required")
    _check_date(inv, "issue_date", "issue_date", issues, required=True)
    _check_date(inv, "due_date", "due_date", issues)
    _check_date(inv, "tax_point_date", "tax_point_date", issues)
    inv["currency"] = (inv.get("currency") or "EUR").upper()
    if not re.match(r"^[A-Z]{3}$", inv["currency"]):
        issues.error("currency", "must be an ISO 4217 code such as EUR")
    if inv.get("tax_currency"):
        inv["tax_currency"] = inv["tax_currency"].upper()
    if inv.get("tax_point_code"):
        tpc = str(inv["tax_point_code"]).strip().lower()
        inv["tax_point_code"] = TAX_POINT_CODES.get(tpc, tpc)
        if inv["tax_point_code"] not in TAX_POINT_UBL:
            issues.error("tax_point_code", "must be 'invoice', 'delivery' or 'payment' (BT-8)")

    for key in ("period",):
        if inv.get(key):
            _check_date(inv[key], "start", key + ".start", issues)
            _check_date(inv[key], "end", key + ".end", issues)
    if inv.get("delivery"):
        _check_date(inv["delivery"], "date", "delivery.date", issues)
    for i, p in enumerate(inv.get("preceding_invoices") or []):
        _check_date(p, "date", f"preceding_invoices[{i}].date", issues)

    notes = inv.get("notes") or []
    if isinstance(notes, str):
        notes = [notes]
    inv["notes"] = [n if isinstance(n, dict) else {"text": n} for n in notes]

    _check_party(inv.get("seller"), "seller", issues, is_seller=True)
    _check_party(inv.get("buyer"), "buyer", issues, is_seller=False)

    # ---------------- lines ----------------
    lines = inv.get("lines") or []
    if not lines:
        issues.error("lines", "at least one invoice line (BG-25) is required")
    groups = {}  # (category, rate) -> taxable

    def group_add(cat, rate, amount):
        key = (cat, rate)
        groups[key] = groups.get(key, ZERO) + amount

    sum_lines = ZERO
    for i, ln in enumerate(lines):
        p = f"lines[{i}]"
        ln.setdefault("id", str(i + 1))
        ln["id"] = str(ln["id"])
        if not ln.get("name"):
            issues.error(p + ".name", "item name (BT-153) is required")
        qty = dec(ln.get("quantity"), p + ".quantity", issues, required=True) or ZERO
        ln["quantity"] = qty
        ln["unit"] = ln.get("unit") or "C62"
        base_qty = dec(ln.get("base_quantity"), p + ".base_quantity", issues)
        if base_qty is not None and base_qty <= 0:
            issues.error(p + ".base_quantity", "must be > 0")
            base_qty = None
        ln["base_quantity"] = base_qty
        gross = dec(ln.get("gross_price"), p + ".gross_price", issues)
        disc = dec(ln.get("price_discount"), p + ".price_discount", issues)
        price = dec(ln.get("price"), p + ".price", issues)
        if price is None:
            if gross is not None:
                price = gross - (disc or ZERO)
            else:
                issues.error(p + ".price", "net unit price (BT-146) is required")
                price = ZERO
        elif gross is not None and disc is not None and gross - disc != price:
            soft(p + ".price", f"price {price} != gross_price {gross} - price_discount {disc} (BR-CO / BT-146)")
        if price < 0:
            issues.error(p + ".price", "item net price (BT-146) must not be negative (BR-27); use a negative quantity or an allowance instead")
        ln["price"], ln["gross_price"], ln["price_discount"] = price, gross, disc

        gross_line = qty * price / (base_qty or Decimal(1))
        allow_sum = sum(
            (_calc_allowance_charge(a, f"{p}.allowances[{j}]", issues, gross_line, soft)
             for j, a in enumerate(ln.get("allowances") or [])), ZERO)
        charge_sum = sum(
            (_calc_allowance_charge(c, f"{p}.charges[{j}]", issues, gross_line, soft)
             for j, c in enumerate(ln.get("charges") or [])), ZERO)
        net = r2(r2(gross_line) + charge_sum - allow_sum)
        given = dec(ln.get("net_amount"), p + ".net_amount", issues)
        if given is not None and r2(given) != net:
            soft(
                p + ".net_amount",
                f"given {fmt_amount(given)} but quantity x price / base_quantity "
                f"+ charges - allowances = {fmt_amount(net)} (BR-CO / Peppol R120). "
                f"Remove net_amount to let it be computed, or fix the inputs.",
            )
            if trust_amounts:
                net = r2(given)
        ln["net_amount"] = net
        sum_lines += net

        cat, rate = _vat_of(ln, p, issues)
        ln["vat_category"], ln["vat_rate"] = cat, rate
        sid = ln.get("standard_item_id")
        if isinstance(sid, dict) and sid.get("scheme"):
            msg = identifiers.check_scheme_id(sid["scheme"], sid.get("id"))
            if msg:
                issues.warn(p + ".standard_item_id", msg)
        group_add(cat, rate, net)
        if ln.get("period"):
            _check_date(ln["period"], "start", p + ".period.start", issues)
            _check_date(ln["period"], "end", p + ".period.end", issues)

    # ---------------- document level allowances / charges ----------------
    allow_total = ZERO
    for j, a in enumerate(inv.get("allowances") or []):
        p = f"allowances[{j}]"
        amt = _calc_allowance_charge(a, p, issues, sum_lines, soft)
        a["vat_category"], a["vat_rate"] = _vat_of(a, p, issues)
        group_add(a["vat_category"], a["vat_rate"], -amt)
        allow_total += amt
    charge_total = ZERO
    for j, c in enumerate(inv.get("charges") or []):
        p = f"charges[{j}]"
        amt = _calc_allowance_charge(c, p, issues, sum_lines, soft)
        c["vat_category"], c["vat_rate"] = _vat_of(c, p, issues)
        group_add(c["vat_category"], c["vat_rate"], amt)
        charge_total += amt

    # ---------------- VAT breakdown (BG-23) ----------------
    exemptions = inv.get("vat_exemptions") or {}
    given_vat = {}
    for g in inv.get("vat_breakdown") or []:
        gr = dec(g.get("rate"), "vat_breakdown.rate", issues)
        given_vat[((g.get("category") or "").upper(), None if (g.get("category") or "").upper() == "O" else (gr if gr is not None else ZERO))] = g
    breakdown = []
    for (cat, rate), taxable in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1] or ZERO)):
        taxable = r2(taxable)
        tax = r2(taxable * (rate or ZERO) / HUNDRED)
        g = given_vat.get((cat, rate))
        if g is not None:
            gtax = dec(g.get("tax"), f"vat_breakdown[{cat} {rate}].tax", issues)
            if gtax is not None and r2(gtax) != tax:
                # EN 16931 tolerates +/-1 unit of rounding in BT-117 (BR-CO-17); some
                # countries (e.g. HUF invoices) round VAT to whole units on purpose.
                if trust_amounts and abs(r2(gtax) - tax) <= 1:
                    issues.info(f"vat_breakdown[{cat} {rate}]", f"keeping source VAT {fmt_amount(gtax)} (computed {fmt_amount(tax)}; within the BR-CO-17 tolerance)")
                    tax = r2(gtax)
                else:
                    soft(f"vat_breakdown[{cat} {rate}].tax", f"given {fmt_amount(gtax)} but taxable {fmt_amount(taxable)} x {fmt_num(rate or ZERO)}% = {fmt_amount(tax)} (BR-CO-17)")
        row = {"category": cat, "rate": rate, "taxable": taxable, "tax": tax}
        ex = exemptions.get(cat) or {}
        if isinstance(ex, str):
            ex = {"reason": ex}
        row["exemption_reason"] = ex.get("reason")
        row["exemption_code"] = ex.get("code")
        if cat in ("E", "AE", "K", "G", "O") and not (row["exemption_reason"] or row["exemption_code"]):
            if cat in DEFAULT_EXEMPTION:
                row["exemption_code"], row["exemption_reason"] = DEFAULT_EXEMPTION[cat]
                issues.info(f"vat_exemptions.{cat}", f"no exemption reason given; using default {row['exemption_code']} '{row['exemption_reason']}'")
            else:
                issues.error(
                    f"vat_exemptions.{cat}",
                    "category E (exempt) needs an exemption reason text or VATEX code, e.g. "
                    "{\"E\": {\"code\": \"VATEX-EU-132\", \"reason\": \"Exempt based on article 132 of Council Directive 2006/112/EC\"}} (BR-E-10)",
                )
        breakdown.append(row)
    inv["vat_breakdown"] = breakdown
    _check_vat_rules(inv, issues)

    # ---------------- totals (BG-22) ----------------
    tax_total = sum((b["tax"] for b in breakdown), ZERO)
    tax_exclusive = sum_lines - allow_total + charge_total
    prepaid = r2(dec(inv.get("prepaid_amount"), "prepaid_amount", issues) or ZERO)
    rounding = r2(dec(inv.get("rounding_amount"), "rounding_amount", issues) or ZERO)
    totals = {
        "line_total": r2(sum_lines),                       # BT-106
        "allowance_total": r2(allow_total),                # BT-107
        "charge_total": r2(charge_total),                  # BT-108
        "tax_exclusive": r2(tax_exclusive),                # BT-109
        "tax_total": r2(tax_total),                        # BT-110
        "tax_inclusive": r2(tax_exclusive + tax_total),    # BT-112
        "prepaid": prepaid,                                # BT-113
        "rounding": rounding,                              # BT-114
    }
    totals["payable"] = r2(totals["tax_inclusive"] - prepaid + rounding)  # BT-115
    if inv.get("tax_currency") and inv["tax_currency"] != inv["currency"]:
        tcta = dec(inv.get("tax_total_in_tax_currency"), "tax_total_in_tax_currency", issues)
        if tcta is None:
            issues.error("tax_total_in_tax_currency", "required when tax_currency (BT-6) differs from currency (BR-53)")
        else:
            totals["tax_total_tax_currency"] = r2(tcta)    # BT-111

    expected = inv.get("totals") or {}
    for key, val in expected.items():
        if key not in totals:
            continue
        d = dec(val, f"totals.{key}", issues)
        if d is not None and r2(d) != totals[key]:
            issues.error(
                f"totals.{key}",
                f"you supplied {fmt_amount(d)} but the lines compute to {fmt_amount(totals[key])}. "
                "The XML must carry the computed value; check line prices, quantities, "
                "allowances and VAT rates (or drop 'totals' to accept the computed figures).",
            )
    inv["totals"] = totals

    # ---------------- payment ----------------
    _check_payment(inv, issues)
    if totals["payable"] > 0 and not inv["is_credit_note"] and not inv.get("due_date") and not (inv.get("payment") or {}).get("terms"):
        issues.error("due_date", "amount due > 0 requires due_date (BT-9) or payment.terms (BT-20) (BR-CO-25)")

    for i, att in enumerate(inv.get("attachments") or []):
        if not att.get("id"):
            issues.error(f"attachments[{i}].id", "attachment reference id (BT-122) is required")

    if profile_key:
        _profile_checks(inv, profile_key, issues)
    return inv, issues


def _vat_of(obj, path, issues):
    cat = (obj.get("vat_category") or "").upper().strip()
    if not cat:
        issues.error(path + ".vat_category", "VAT category code is required (S, Z, E, AE, K, G, O, L, M)")
        cat = "S"
    elif cat not in VAT_CATEGORIES:
        issues.error(path + ".vat_category", f"'{cat}' is not a valid EN 16931 VAT category ({', '.join(VAT_CATEGORIES)})")
    rate = dec(obj.get("vat_rate"), path + ".vat_rate", issues)
    if cat == "O":
        if rate not in (None, ZERO):
            issues.error(path + ".vat_rate", "category O (not subject to VAT) must not have a VAT rate (BR-O-05)")
        rate = None
    elif rate is None:
        if cat in ("Z", "E", "AE", "K", "G"):
            rate = ZERO
        else:
            issues.error(path + ".vat_rate", f"VAT rate is required for category {cat}")
            rate = ZERO
    if cat in ("Z", "E", "AE", "K", "G") and rate not in (None, ZERO):
        issues.error(path + ".vat_rate", f"category {cat} requires a VAT rate of 0 (BR-{RULE_PREFIX[cat]}-05)")
    if cat == "S" and rate is not None and rate <= 0:
        issues.error(path + ".vat_rate", "category S (standard) requires a VAT rate greater than 0 (BR-S-05)")
    return cat, rate


def _check_party(party, path, issues, is_seller):
    if not party:
        issues.error(path, f"{path} (BG-{4 if is_seller else 7}) is required")
        return
    if not party.get("name"):
        issues.error(path + ".name", f"{path} name (BT-{27 if is_seller else 44}) is required")
    addr = party.get("address") or {}
    if not addr.get("country"):
        issues.error(path + ".address.country", f"{path} country code (BT-{40 if is_seller else 55}) is required, ISO 3166-1 alpha-2 like DE")
    elif not re.match(r"^[A-Z]{2}$", str(addr["country"]).upper()):
        issues.error(path + ".address.country", "must be ISO 3166-1 alpha-2, e.g. DE, FR, NL")
    else:
        addr["country"] = str(addr["country"]).upper()
    party["address"] = addr
    if party.get("vat_id"):
        vid = str(party["vat_id"]).replace(" ", "")
        party["vat_id"] = vid
        if not re.match(r"^[A-Z]{2}", vid):
            issues.error(path + ".vat_id", "VAT identifier must start with the ISO country prefix, e.g. DE123456789 (BR-CO-09)")
    ea = party.get("electronic_address")
    if isinstance(ea, str):
        party["electronic_address"] = {"id": ea, "scheme": "EM" if "@" in ea else None}
        ea = party["electronic_address"]
    if ea and not ea.get("scheme"):
        issues.error(path + ".electronic_address.scheme", "electronic address needs an EAS scheme code, e.g. 'EM' for e-mail, '9930' for DE VAT, '0088' for GLN, '0204' for Leitweg-ID (BR-62/BR-63)")
    _check_identifiers(party, path, issues)
    if is_seller and not (party.get("vat_id") or party.get("legal_id") or party.get("ids") or party.get("tax_registration_id")):
        issues.warn(path, "seller has no VAT ID, legal registration ID or identifier; most rules (BR-CO-26, BR-S-02) need at least one")


def _check_identifiers(party, path, issues):
    """Check digits the Schematron does not verify (Leitweg-ID, SIREN/SIRET, FR/BE VAT, GLN)."""
    if party.get("vat_id"):
        msg = identifiers.check_vat_id(party["vat_id"])
        if msg:
            issues.warn(path + ".vat_id", msg)
    refs = [("legal_id", party.get("legal_id")), ("electronic_address", party.get("electronic_address"))]
    refs += [(f"ids[{i}]", x) for i, x in enumerate(party.get("ids") or [])]
    for key, ref in refs:
        if isinstance(ref, dict) and ref.get("scheme"):
            msg = identifiers.check_scheme_id(ref["scheme"], ref.get("id"))
            if msg:
                issues.warn(f"{path}.{key}", msg)


def _check_vat_rules(inv, issues):
    cats = {b["category"] for b in inv["vat_breakdown"]}
    seller = inv.get("seller") or {}
    buyer = inv.get("buyer") or {}
    has_seller_tax = seller.get("vat_id") or seller.get("tax_registration_id") or inv.get("tax_representative")
    for cat in cats & {"S", "Z", "E", "L", "M"}:
        if not has_seller_tax:
            issues.error("seller.vat_id", f"VAT category {cat} requires seller VAT ID (BT-31), tax registration ID (BT-32) or a tax representative (BR-{cat}-02)")
    for cat, rule in (("AE", "AE"), ("K", "IC"), ("G", "G")):
        if cat in cats and not (seller.get("vat_id") or inv.get("tax_representative")):
            issues.error("seller.vat_id", f"VAT category {cat} requires the seller VAT ID (BR-{rule}-02)")
    if "AE" in cats and not (buyer.get("vat_id") or buyer.get("legal_id")):
        issues.error("buyer.vat_id", "reverse charge (AE) requires the buyer VAT ID (BT-48) or legal registration ID (BR-AE-02)")
    if "K" in cats:
        if not buyer.get("vat_id"):
            issues.error("buyer.vat_id", "intra-community supply (K) requires the buyer VAT ID (BR-IC-02)")
        if not ((inv.get("delivery") or {}).get("date") or inv.get("period")):
            issues.error("delivery.date", "intra-community supply (K) requires an actual delivery date (BT-72) or invoicing period (BG-14) (BR-IC-11)")
        if not ((inv.get("delivery") or {}).get("address") or {}).get("country"):
            issues.error("delivery.address.country", "intra-community supply (K) requires the deliver-to country code (BT-80) (BR-IC-12)")
    if "O" in cats:
        if len(cats) > 1:
            issues.error("lines", "category O (not subject to VAT) cannot be combined with other VAT categories in one invoice (BR-O-11..14)")
        if seller.get("vat_id") or buyer.get("vat_id"):
            issues.error("seller.vat_id", "an invoice with category O must not contain seller or buyer VAT IDs (BR-O-02)")


def _check_payment(inv, issues):
    pay = inv.get("payment") or {}
    code = str(pay.get("means_code") or "").strip()
    if not pay:
        return
    needs_code = pay.get("credit_transfers") or pay.get("card") or (pay.get("direct_debit") or {}).get("mandate_id") or pay.get("means_text")
    if not code and needs_code:
        issues.error("payment.means_code", "payment means type code (BT-81) is required when payment is given, e.g. 58 = SEPA credit transfer, 30 = credit transfer, 59 = SEPA direct debit, 48 = card, 10 = cash")
    pay["means_code"] = code
    if code in CREDIT_TRANSFER_CODES and not pay.get("credit_transfers"):
        issues.error("payment.credit_transfers", "credit transfer (30/58) requires at least one account (iban) (BR-61)")
    for i, ct in enumerate(pay.get("credit_transfers") or []):
        if not (ct.get("iban") or ct.get("account_id")):
            issues.error(f"payment.credit_transfers[{i}].iban", "payment account identifier (BT-84) is required")
        if ct.get("iban"):
            ct["iban"] = ct["iban"].replace(" ", "").upper()
            if not _iban_ok(ct["iban"]):
                issues.warn(f"payment.credit_transfers[{i}].iban", f"'{ct['iban']}' is not a valid IBAN (format/checksum); payments to it will fail. Use 'account_id' for non-IBAN accounts")
    if code in DIRECT_DEBIT_CODES:
        dd = pay.get("direct_debit") or {}
        if not dd.get("mandate_id"):
            issues.warn("payment.direct_debit.mandate_id", "direct debit usually needs the mandate reference (BT-89)")


def _iban_ok(iban):
    if not re.match(r"^[A-Z]{2}\d{2}[A-Z0-9]{8,30}$", iban):
        return False
    s = iban[4:] + iban[:4]
    num = "".join(str(int(c, 36)) for c in s)
    return int(num) % 97 == 1


def _profile_checks(inv, profile_key, issues):
    """Cheap early warnings for the rules that trip people most often.
    The schematron validation is still the authority."""
    seller, buyer = inv.get("seller") or {}, inv.get("buyer") or {}
    pay = inv.get("payment") or {}
    br = inv.get("buyer_reference")
    if br and identifiers.looks_like_leitweg_id(br) and (profile_key.startswith("xrechnung") or (buyer.get("address") or {}).get("country") == "DE"):
        msg = identifiers.check_leitweg_id(br)
        if msg:
            issues.warn("buyer_reference", msg)
    if profile_key.startswith("xrechnung"):
        if not inv.get("buyer_reference"):
            issues.error("buyer_reference", "XRechnung requires the buyer reference BT-10 (for public buyers: the Leitweg-ID, e.g. 04011000-12345-03) (BR-DE-15)")
        c = seller.get("contact") or {}
        for k, rule in (("name", "BR-DE-5"), ("phone", "BR-DE-6"), ("email", "BR-DE-7")):
            if not c.get(k):
                issues.error(f"seller.contact.{k}", f"XRechnung requires seller contact {k} ({rule})")
        for who, party in (("seller", seller), ("buyer", buyer)):
            a = party.get("address") or {}
            if not a.get("city"):
                issues.error(f"{who}.address.city", f"XRechnung requires the {who} city (BR-DE-3/BR-DE-8)")
            if not a.get("postal_code"):
                issues.error(f"{who}.address.postal_code", f"XRechnung requires the {who} post code (BR-DE-4/BR-DE-9)")
            if not party.get("electronic_address"):
                issues.error(f"{who}.electronic_address", f"XRechnung 3.0 requires the {who} electronic address (BT-{34 if who == 'seller' else 49}); e-mail with scheme 'EM' is accepted (BR-DE-30/31 area)")
        if not pay:
            issues.error("payment", "XRechnung requires payment instructions BG-16 (BR-DE-1)")
        if not ((inv.get("delivery") or {}).get("date") or inv.get("period") or all(ln.get("period") for ln in inv.get("lines") or [])):
            issues.warn("delivery.date", "German invoices must state the date of supply/service (§14 UStG): set delivery.date or period (BR-DE-TMP-32)")
        if inv["type_code"] == "384" and not inv.get("preceding_invoices"):
            issues.error("preceding_invoices", "a corrected invoice (384) requires the preceding invoice reference (BR-DE-26)")
        terms = pay.get("terms") or ""
        if "SKONTO" in terms.upper() and not re.search(r"#SKONTO#TAGE=\d+#PROZENT=\d+\.\d{2}(#BASISBETRAG=-?\d+\.\d{2})?#", terms):
            issues.error("payment.terms", "XRechnung Skonto must be written exactly as '#SKONTO#TAGE=14#PROZENT=2.00#' followed by a newline (BR-DE-18)")
    if profile_key == "peppol":
        both_de = (seller.get("address") or {}).get("country") == "DE" and (buyer.get("address") or {}).get("country") == "DE"
        if len(inv["notes"]) > 1 and not both_de:
            issues.error("notes", "Peppol allows only one document-level note unless seller and buyer are both German; merge them (PEPPOL-EN16931-R002)")
        if inv["type_code"] in ("326", "384") and not both_de:
            issues.error("type", "Peppol allows type 326/384 only between German parties; use 380 or a credit note (PEPPOL-EN16931-P0112)")
        if not (inv.get("buyer_reference") or inv.get("order_reference")):
            issues.error("buyer_reference", "Peppol requires buyer_reference (BT-10) or order_reference (BT-13) (PEPPOL-EN16931-R003)")
        for who, party, rule in (("seller", seller, "R020"), ("buyer", buyer, "R010")):
            if ((party.get("electronic_address") or {}).get("scheme") or "").upper() == "EM":
                issues.error(f"{who}.electronic_address.scheme", "e-mail (EM) is not a Peppol participant scheme; use the party's Peppol ID, e.g. 0208 (BE), 0106 (NL), 0088 (GLN), 9930 (DE VAT) (PEPPOL-EN16931-CL008)")
            if not party.get("electronic_address"):
                issues.error(f"{who}.electronic_address", f"Peppol requires the {who} electronic address = Peppol participant ID, e.g. {{\"id\": \"987654321\", \"scheme\": \"0192\"}} (PEPPOL-EN16931-{rule})")
