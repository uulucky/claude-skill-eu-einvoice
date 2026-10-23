"""Visual invoice PDF + Factur-X / ZUGFeRD (PDF/A-3 with embedded XML).

PDF/A-3 needs: every font embedded, an OutputIntent with an ICC profile,
XMP metadata declaring pdfaid:part=3, and the XML attached with an
AFRelationship. reportlab embeds TrueType fonts; we add an sRGB OutputIntent
(the ICC profile is generated here, so nothing with a licence is bundled);
the factur-x library writes the XMP (incl. the fx: extension schema) and the
attachment.
"""

import datetime
import io
import os
import struct
from pathlib import Path

from .model import fmt_num, fmt_price
from .render import labels, lang_of, money, num, party_lines, title_of, unit_name

FONT_CANDIDATES = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
    ("/Library/Fonts/DejaVuSans.ttf", "/Library/Fonts/DejaVuSans-Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
]


# --------------------------------------------------------------------------
# sRGB ICC profile (ICC v2 display profile, built from the published sRGB
# primaries; no third-party file needed)
# --------------------------------------------------------------------------

def _s15(v):
    return struct.pack(">i", int(round(v * 65536)))


def srgb_icc():
    def xyz(x, y, z):
        return b"XYZ " + b"\0" * 4 + _s15(x) + _s15(y) + _s15(z)

    desc_txt = b"sRGB IEC61966-2.1 (eu-einvoice)\0"
    desc = (b"desc" + b"\0" * 4 + struct.pack(">I", len(desc_txt)) + desc_txt
            + struct.pack(">II", 0, 0) + struct.pack(">HB", 0, 0) + b"\0" * 67)
    cprt = b"text" + b"\0" * 4 + b"No copyright, use freely\0"
    curv = b"curv" + b"\0" * 4 + struct.pack(">IH", 1, 0x0233) + b"\0\0"  # gamma 2.2
    tags = [
        (b"desc", desc), (b"cprt", cprt),
        (b"wtpt", xyz(0.9505, 1.0, 1.0891)),
        (b"rXYZ", xyz(0.4361, 0.2225, 0.0139)),
        (b"gXYZ", xyz(0.3851, 0.7169, 0.0971)),
        (b"bXYZ", xyz(0.1431, 0.0606, 0.7141)),
        (b"rTRC", curv), (b"gTRC", curv), (b"bTRC", curv),
    ]
    offset = 128 + 4 + 12 * len(tags)
    table, data = b"", b""
    for sig, blob in tags:
        while (offset + len(data)) % 4:
            data += b"\0"
        table += sig + struct.pack(">II", offset + len(data), len(blob))
        data += blob
    body = struct.pack(">I", len(tags)) + table + data
    size = 128 + len(body)
    now = datetime.datetime(2026, 1, 1)
    header = (struct.pack(">I", size) + b"\0\0\0\0" + struct.pack(">I", 0x02100000) + b"mntr" + b"RGB " + b"XYZ "
              + struct.pack(">6H", now.year, now.month, now.day, 0, 0, 0) + b"acsp" + b"\0" * 4
              + b"\0" * 4 + b"\0" * 8 + b"\0" * 8 + struct.pack(">I", 0)
              + _s15(0.9642) + _s15(1.0) + _s15(0.8249) + b"\0" * 4)
    header += b"\0" * (128 - len(header))
    return header + body


# --------------------------------------------------------------------------
# Visual PDF
# --------------------------------------------------------------------------

def _fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    if "EInv" in pdfmetrics.getRegisteredFontNames():
        return "EInv", "EInvBold"
    env = os.environ.get("EINVOICE_FONT")
    pairs = ([(env, os.environ.get("EINVOICE_FONT_BOLD", env))] if env else []) + FONT_CANDIDATES
    for reg, bold in pairs:
        if reg and os.path.exists(reg):
            pdfmetrics.registerFont(TTFont("EInv", reg))
            pdfmetrics.registerFont(TTFont("EInvBold", bold if bold and os.path.exists(bold) else reg))
            return "EInv", "EInvBold"
    import reportlab
    base = Path(reportlab.__file__).parent / "fonts"
    pdfmetrics.registerFont(TTFont("EInv", str(base / "Vera.ttf")))
    pdfmetrics.registerFont(TTFont("EInvBold", str(base / "VeraBd.ttf")))
    return "EInv", "EInvBold"


def render_pdf(inv):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from xml.sax.saxutils import escape

    reg, bold = _fonts()
    L = labels(inv)
    lg = lang_of(inv)
    cur = inv["currency"]
    t = inv["totals"]
    ink = colors.Color(0.11, 0.14, 0.2)
    muted = colors.Color(0.4, 0.44, 0.52)
    accent = colors.Color(0.12, 0.31, 0.82)
    line = colors.Color(0.89, 0.9, 0.93)
    st = lambda **k: ParagraphStyle("s", fontName=k.pop("font", reg), fontSize=k.pop("size", 9), leading=k.pop("lead", 12), textColor=k.pop("color", ink), **k)
    P = lambda text, **k: Paragraph(escape(str(text)) if not k.pop("raw", False) else str(text), st(**k))

    seller, buyer = inv.get("seller") or {}, inv.get("buyer") or {}
    story = []
    head = Table([[P(title_of(inv, L), font=bold, size=20, lead=24, color=accent),
                   P("<br/>".join(escape(x) for x in party_lines(seller)), raw=True, size=8.5, color=muted, alignment=2)]],
                 colWidths=[95 * mm, 85 * mm])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story += [head, Spacer(1, 8 * mm)]

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
    buyer_txt = "<br/>".join(escape(x) for x in party_lines(buyer))
    if buyer.get("vat_id"):
        buyer_txt += f"<br/>{L['vat_id']} {escape(buyer['vat_id'])}"
    meta_tbl = Table([[P(k, color=muted, size=8.5), P(v, size=8.5)] for k, v in meta if v], colWidths=[32 * mm, 50 * mm])
    meta_tbl.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    top = Table([[[P(L["buyer"].upper(), font=bold, size=7.5, color=muted), P(buyer_txt, raw=True)], meta_tbl]], colWidths=[98 * mm, 82 * mm])
    top.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story += [top, Spacer(1, 8 * mm)]

    rows = [[P(L["pos"], font=bold, size=8), P(L["item"], font=bold, size=8), P(L["qty"], font=bold, size=8, alignment=2),
             P(L["unit"], font=bold, size=8), P(L["price"], font=bold, size=8, alignment=2), P(L["vat"], font=bold, size=8, alignment=2),
             P(L["net"], font=bold, size=8, alignment=2)]]
    for ln in inv["lines"]:
        desc = f"<font name='{bold}'>{escape(ln.get('name') or '')}</font>"
        if ln.get("description"):
            desc += f"<br/><font color='#667085'>{escape(ln['description'])}</font>"
        for a in ln.get("allowances") or []:
            desc += f"<br/><font color='#667085'>{L['allowance']}: {escape(str(a.get('reason') or a.get('reason_code')))} −{money(a['amount'], cur, lg)}</font>"
        for c in ln.get("charges") or []:
            desc += f"<br/><font color='#667085'>{L['charge']}: {escape(str(c.get('reason') or c.get('reason_code')))} +{money(c['amount'], cur, lg)}</font>"
        rate = "–" if ln["vat_rate"] is None else f"{num(fmt_num(ln['vat_rate']), lg)} %"
        rows.append([P(ln["id"]), P(desc, raw=True), P(num(fmt_num(ln["quantity"]), lg), alignment=2), P(unit_name(ln["unit"], lg)),
                     P(num(fmt_price(ln["price"]), lg), alignment=2), P(rate, alignment=2), P(money(ln["net_amount"], cur, lg), alignment=2)])
    lt = Table(rows, colWidths=[10 * mm, 72 * mm, 16 * mm, 16 * mm, 22 * mm, 14 * mm, 30 * mm], repeatRows=1)
    lt.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.5, line), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]))
    story += [lt, Spacer(1, 4 * mm)]

    tot = [(L["subtotal"], t["line_total"])]
    for a in inv.get("allowances") or []:
        tot.append((f"{L['allowance']}: {a.get('reason') or a.get('reason_code')}", -a["amount"]))
    for c in inv.get("charges") or []:
        tot.append((f"{L['charge']}: {c.get('reason') or c.get('reason_code')}", c["amount"]))
    tot += [(L["total_net"], t["tax_exclusive"])]
    for b in inv["vat_breakdown"]:
        rate = b["category"] if b["rate"] is None else f" {num(fmt_num(b['rate']), lg)} %"
        tot.append((f"{L['vat']} {rate.strip()} ({money(b['taxable'], cur, lg)})", b["tax"]))
    tot += [(L["total_gross"], t["tax_inclusive"])]
    if t["prepaid"]:
        tot.append((L["prepaid"], -t["prepaid"]))
    if t["rounding"]:
        tot.append((L["rounding"], t["rounding"]))
    trow = [[P(k, size=8.5), P(money(v, cur, lg), size=8.5, alignment=2)] for k, v in tot]
    trow.append([P(L["payable"], font=bold, size=11, lead=14), P(money(t["payable"], cur, lg), font=bold, size=11, lead=14, alignment=2)])
    tt = Table(trow, colWidths=[70 * mm, 35 * mm], hAlign="RIGHT")
    tt.setStyle(TableStyle([("LINEABOVE", (0, -1), (-1, -1), 1, ink), ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]))
    story += [tt, Spacer(1, 6 * mm)]

    for b in inv["vat_breakdown"]:
        if b.get("exemption_reason") or b.get("exemption_code"):
            story.append(P(f"{L['exemption']} ({b['category']}): {b.get('exemption_reason') or ''} {('[' + b['exemption_code'] + ']') if b.get('exemption_code') else ''}", size=8.5))
    pay = inv.get("payment") or {}
    pay_lines = []
    for ct in pay.get("credit_transfers") or []:
        s = f"{L['iban']}: {ct.get('iban') or ct.get('account_id')}"
        if ct.get("bic"):
            s += f"   {L['bic']}: {ct['bic']}"
        if ct.get("account_name"):
            s += f"   ({ct['account_name']})"
        pay_lines.append(s)
    if pay.get("remittance_info"):
        pay_lines.append(f"{L['ref']}: {pay['remittance_info']}")
    if pay.get("terms"):
        pay_lines.append(f"{L['terms']}: {pay['terms']}")
    if pay_lines:
        story += [Spacer(1, 3 * mm), P(L["payment"].upper(), font=bold, size=7.5, color=muted)] + [P(x, size=8.5) for x in pay_lines]
    if inv["notes"]:
        story += [Spacer(1, 3 * mm), P(L["notes"].upper(), font=bold, size=7.5, color=muted)] + [P(n["text"], size=8.5) for n in inv["notes"]]

    legal = seller.get("legal_id")
    legal = legal.get("id") if isinstance(legal, dict) else legal
    footer = " · ".join(str(x) for x in (seller.get("name"), seller.get("vat_id") and f"{L['vat_id']} {seller['vat_id']}", legal, seller.get("legal_info")) if x)

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(muted)
        canvas.setFont(reg, 7)
        canvas.drawString(15 * mm, 10 * mm, footer[:170])
        canvas.drawRightString(195 * mm, 10 * mm, f"{L['page']} {doc.page}")
        canvas.restoreState()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=18 * mm,
                            title=f"{title_of(inv, L)} {inv.get('number')}", author=seller.get("name") or "",
                            subject=f"{title_of(inv, L)} {inv.get('number')}", creator="eu-einvoice", invariant=1)
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()


# --------------------------------------------------------------------------
# PDF/A-3 + Factur-X
# --------------------------------------------------------------------------

def add_output_intent(pdf_bytes):
    from pypdf import PdfWriter
    from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, NameObject, NumberObject, TextStringObject

    w = PdfWriter(clone_from=io.BytesIO(pdf_bytes))
    root = w._root_object
    if "/OutputIntents" in root:
        return pdf_bytes
    icc = DecodedStreamObject()
    icc.set_data(srgb_icc())
    icc.update({NameObject("/N"): NumberObject(3)})
    icc_ref = w._add_object(icc)
    oi = DictionaryObject({
        NameObject("/Type"): NameObject("/OutputIntent"),
        NameObject("/S"): NameObject("/GTS_PDFA1"),
        NameObject("/OutputConditionIdentifier"): TextStringObject("sRGB IEC61966-2.1"),
        NameObject("/Info"): TextStringObject("sRGB IEC61966-2.1"),
        NameObject("/DestOutputProfile"): icc_ref,
    })
    root[NameObject("/OutputIntents")] = ArrayObject([w._add_object(oi)])
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()


def make_facturx(inv, xml_bytes, base_pdf=None, level="en16931", afrelationship="data"):
    try:
        from facturx import generate_from_binary
    except ImportError as e:
        raise RuntimeError("factur-x is not installed: pip install -r requirements.txt") from e
    if base_pdf:
        pdf = Path(base_pdf).read_bytes()
    else:
        pdf = render_pdf(inv)
    pdf = add_output_intent(pdf)
    L = labels(inv)
    seller = (inv.get("seller") or {}).get("name") or ""
    meta = {
        "author": seller,
        "keywords": "Factur-X, ZUGFeRD, EN 16931, e-invoice",
        "title": f"{seller}: {title_of(inv, L)} {inv.get('number')}",
        "subject": f"{title_of(inv, L)} {inv.get('number')} {inv.get('issue_date')} {seller}",
    }
    return generate_from_binary(pdf, xml_bytes, flavor="factur-x", level=level, check_xsd=False,
                                pdf_metadata=meta, lang=None, afrelationship=afrelationship)
