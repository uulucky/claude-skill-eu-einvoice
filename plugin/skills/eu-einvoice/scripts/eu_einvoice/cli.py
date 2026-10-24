#!/usr/bin/env python3
"""eu-einvoice command line.

  create    JSON -> XRechnung / Peppol / EN 16931 XML, or Factur-X/ZUGFeRD PDF
  check     JSON -> computed totals + pre-flight problems (no XML written)
  validate  XML or PDF -> XSD + official Schematron report
  extract   XML or PDF -> JSON model (read a received e-invoice)
  convert   XML/PDF in one profile -> another profile (e.g. CII -> UBL)
  render    JSON/XML/PDF -> human-readable HTML or PDF
  template  print an example JSON for a scenario
  rules     fetch | status | check-updates for the official rule sets

Run `eu-einvoice <command> -h` (or `einvoice_cli.py <command> -h`) for options.
"""

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE / "examples"
REQUIREMENTS = "pip install eu-einvoice  (or: pip install -r requirements.txt from the skill folder)"


def _need(modname, pip_name=None):
    try:
        __import__(modname)
    except ImportError:
        sys.exit(f"Missing dependency '{pip_name or modname}'. Install with:\n  {REQUIREMENTS}")


def _json_default(o):
    if isinstance(o, Decimal):
        return str(o)
    raise TypeError(type(o))


def _print_issues(issues):
    for i in issues:
        print(f"  [{i['level'].upper()}] {i['path']}: {i['msg']}")


def _prepare(raw, profile_name, trust=False):
    from eu_einvoice.model import prepare
    from eu_einvoice.profiles import get_profile
    pkey, prof = get_profile(profile_name)
    inv, issues = prepare(raw, pkey, trust_amounts=trust)
    return pkey, prof, inv, issues


def _profile_name(args, raw):
    name = args.profile or (raw.get("profile") if isinstance(raw, dict) else None)
    if not name:
        sys.exit("No profile given: pass --profile (xrechnung-ubl, xrechnung-cii, peppol, facturx, en16931-ubl, en16931-cii) or set \"profile\" in the JSON.")
    return name


def build(raw, profile_name, out_path, pdf_in=None, force=False, do_validate=True, attach_files=True, trust=False, base_dir="."):
    """Shared by create and convert. Returns exit code."""
    from eu_einvoice import cii, ubl
    from eu_einvoice.model import load
    raw = load(raw)
    if attach_files:
        _load_attachment_files(raw, base_dir)
    pkey, prof, inv, issues = _prepare(raw, profile_name, trust)
    if issues:
        print(f"Pre-flight ({prof['label']}):")
        _print_issues(issues)
    if issues.errors and not force:
        print(f"\n{len(issues.errors)} error(s) in the input data; nothing written. Fix the JSON (or pass --force to write anyway).")
        return 2
    xml = (ubl if prof["syntax"] == "ubl" else cii).generate(inv, prof)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if prof.get("pdf"):
        from eu_einvoice import pdf
        if out.suffix.lower() != ".pdf":
            out = out.with_suffix(".pdf")
        pdf_bytes = pdf.make_facturx(inv, xml, base_pdf=pdf_in)
        out.write_bytes(pdf_bytes)
    else:
        out.write_bytes(xml)
    t = inv["totals"]
    print(f"\nWrote {out}  [{prof['label']}]")
    print(f"  net {t['tax_exclusive']}  VAT {t['tax_total']}  gross {t['tax_inclusive']}  due {t['payable']} {inv['currency']}")
    if not do_validate:
        return 0
    from eu_einvoice.validate import format_report, validate
    res = validate(out, profile=pkey, log=print)
    print()
    print(format_report(res))
    return 0 if res["valid"] else 1


def _load_attachment_files(raw, base_dir="."):
    import base64
    import mimetypes
    for att in raw.get("attachments") or []:
        f = att.pop("file", None)
        if f and not att.get("content_b64"):
            p = Path(f).expanduser()
            if not p.is_absolute():
                p = Path(base_dir) / p  # relative to the JSON file
            if not p.exists():
                sys.exit(f"attachment file not found: {p}")
            att["content_b64"] = base64.b64encode(p.read_bytes()).decode()
            att.setdefault("filename", p.name)
            att.setdefault("mime", mimetypes.guess_type(p.name)[0] or "application/octet-stream")


def cmd_create(a):
    _need("lxml")
    raw = json.loads(Path(a.input).read_text(encoding="utf-8"))
    if a.recompute:
        # repairing an extracted invoice: discard the source's (possibly wrong) amounts
        raw.pop("totals", None)
        raw.pop("vat_breakdown", None)
        for ln in raw.get("lines") or []:
            ln.pop("net_amount", None)
    return build(raw, _profile_name(a, raw), a.output, pdf_in=a.pdf, force=a.force, do_validate=not a.no_validate,
                 base_dir=Path(a.input).resolve().parent)


def cmd_check(a):
    _need("lxml")
    raw = json.loads(Path(a.input).read_text(encoding="utf-8"))
    pkey, prof, inv, issues = _prepare(raw, _profile_name(a, raw))
    print(f"Profile: {prof['label']}")
    print("Lines:")
    for ln in inv["lines"]:
        rate = "-" if ln["vat_rate"] is None else f"{ln['vat_rate']}%"
        print(f"  {ln['id']:>3}  {ln.get('name', '')[:40]:40}  {ln['quantity']} {ln['unit']} x {ln['price']}  = {ln['net_amount']}  [{ln['vat_category']} {rate}]")
    print("VAT breakdown:")
    for b in inv["vat_breakdown"]:
        rate = "-" if b["rate"] is None else f"{b['rate']}%"
        print(f"  {b['category']:>2} {rate:>6}  taxable {b['taxable']:>12}  VAT {b['tax']:>10}  {b.get('exemption_code') or ''}")
    print("Totals:")
    for k, v in inv["totals"].items():
        print(f"  {k:24} {v}")
    if issues:
        print("Issues:")
        _print_issues(issues)
    print("OK, ready to create." if not issues.errors else f"{len(issues.errors)} error(s) to fix.")
    if a.json:
        Path(a.json).write_text(json.dumps(inv, indent=2, ensure_ascii=False, default=_json_default))
    return 0 if not issues.errors else 2


def cmd_validate(a):
    _need("lxml")
    from eu_einvoice.validate import format_report, validate
    from eu_einvoice.profiles import get_profile
    profile = get_profile(a.profile)[0] if a.profile else None
    res = validate(a.input, profile=profile, fetch=not a.offline, log=print)
    if a.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print(format_report(res, max_items=a.max))
    return 0 if res["valid"] else 1


def cmd_extract(a):
    _need("lxml")
    from eu_einvoice.parse import parse_file
    model, notes = parse_file(a.input)
    text = json.dumps(model, indent=2, ensure_ascii=False, default=_json_default)
    if a.output:
        Path(a.output).write_text(text, encoding="utf-8")
        print(f"Wrote {a.output}")
    else:
        print(text)
    for n in notes:
        print(f"  note: {n}", file=sys.stderr)
    return 0


def cmd_convert(a):
    _need("lxml")
    from eu_einvoice.parse import parse_file
    model, notes = parse_file(a.input)
    for n in notes:
        print(f"  note: {n}")
    model.pop("profile", None)
    if a.keep_totals is False:
        model.pop("totals", None)
    return build(model, a.to, a.output, force=a.force, do_validate=not a.no_validate, attach_files=False, trust=True)


def cmd_render(a):
    _need("lxml")
    from eu_einvoice import render
    src = Path(a.input)
    if src.suffix.lower() == ".json":
        raw = json.loads(src.read_text(encoding="utf-8"))
        _, _, inv, issues = _prepare(raw, raw.get("profile") or "en16931-ubl")
    else:
        from eu_einvoice.parse import parse_file
        raw, _ = parse_file(src)
        _, _, inv, issues = _prepare(raw, "en16931-ubl", trust=True)
    out = Path(a.output)
    if out.suffix.lower() == ".html":
        out.write_text(render.to_html(inv), encoding="utf-8")
    else:
        _need("reportlab")
        from eu_einvoice import pdf
        out.write_bytes(pdf.render_pdf(inv))
    print(f"Wrote {out}")
    return 0


def cmd_template(a):
    files = sorted(EXAMPLES.glob("*.json"))
    if not a.scenario:
        print("Available scenarios:")
        for f in files:
            d = json.loads(f.read_text(encoding="utf-8"))
            print(f"  {f.stem:28} {d.get('_scenario', '')}")
        return 0
    f = EXAMPLES / f"{a.scenario}.json"
    if not f.exists():
        sys.exit(f"No scenario '{a.scenario}'. Run without argument to list.")
    print(f.read_text(encoding="utf-8"))
    return 0


def cmd_rules(a):
    from eu_einvoice import artifacts
    if a.action == "fetch":
        _need("saxonche")
        ok, failed = artifacts.fetch_all(force=a.force)
        print(f"cached: {', '.join(ok) or '-'}")
        if failed:
            print("failed:")
            for n, e in failed:
                print(f"  {n}: {e}")
            return 1
        print(f"cache dir: {artifacts.cache_dir()}")
    elif a.action == "status":
        for r in artifacts.status():
            print(f"  {'ok ' if r['cached'] else '-- '} {r['name']:15} {r['version']:24} {r['title']}")
        print(f"cache dir: {artifacts.cache_dir()}")
    else:
        print(json.dumps(artifacts.check_updates(), indent=2))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create", help="JSON -> e-invoice XML/PDF (computes totals, validates the result)")
    c.add_argument("input")
    c.add_argument("-o", "--output", required=True)
    c.add_argument("-p", "--profile")
    c.add_argument("--pdf", help="existing visual PDF to embed the XML into (Factur-X); default: render one")
    c.add_argument("--force", action="store_true", help="write even if pre-flight finds errors")
    c.add_argument("--no-validate", action="store_true")
    c.add_argument("--recompute", action="store_true",
                   help="ignore totals / vat_breakdown / line net_amount in the JSON (use when repairing an extracted invoice)")
    c.set_defaults(fn=cmd_create)

    c = sub.add_parser("check", help="pre-flight a JSON invoice: computed lines, VAT, totals, issues")
    c.add_argument("input")
    c.add_argument("-p", "--profile")
    c.add_argument("--json", help="also write the normalised model to this file")
    c.set_defaults(fn=cmd_check)

    c = sub.add_parser("validate", help="validate XML or Factur-X/ZUGFeRD PDF")
    c.add_argument("input")
    c.add_argument("-p", "--profile", help="override auto-detection")
    c.add_argument("--json", action="store_true", help="machine-readable output")
    c.add_argument("--offline", action="store_true", help="do not download rule sets")
    c.add_argument("--max", type=int, default=60)
    c.set_defaults(fn=cmd_validate)

    c = sub.add_parser("extract", help="XML/PDF -> JSON model")
    c.add_argument("input")
    c.add_argument("-o", "--output")
    c.set_defaults(fn=cmd_extract)

    c = sub.add_parser("convert", help="convert between profiles/syntaxes")
    c.add_argument("input")
    c.add_argument("--to", required=True)
    c.add_argument("-o", "--output", required=True)
    c.add_argument("--force", action="store_true")
    c.add_argument("--no-validate", action="store_true")
    c.add_argument("--keep-totals", action="store_true", default=True,
                   help="cross-check the source totals against recomputed ones (default on)")
    c.set_defaults(fn=cmd_convert)

    c = sub.add_parser("render", help="human-readable HTML/PDF of an invoice")
    c.add_argument("input")
    c.add_argument("-o", "--output", required=True, help=".html or .pdf")
    c.set_defaults(fn=cmd_render)

    c = sub.add_parser("template", help="print an example JSON")
    c.add_argument("scenario", nargs="?")
    c.set_defaults(fn=cmd_template)

    c = sub.add_parser("rules", help="manage official rule sets")
    c.add_argument("action", choices=["fetch", "status", "check-updates"])
    c.add_argument("--force", action="store_true")
    c.set_defaults(fn=cmd_rules)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
