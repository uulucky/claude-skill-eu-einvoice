"""Download, verify and cache the official validation artefacts.

Nothing is bundled: the rule sets are published by CEN/TC 434
(ConnectingEurope), KoSIT (XRechnung) and OpenPeppol under their own
licences and get code-list updates twice a year. We pin exact releases with
SHA-256 so a validation result is reproducible, and compile Peppol's
Schematron source to XSLT locally with SchXslt (pure XSLT, run by Saxon-HE
via saxonche: no Java needed).

Cache location: $EINVOICE_RULES_DIR or ~/.cache/eu-einvoice/rules
"""

import hashlib
import io
import json
import os
import shutil
import urllib.request
import zipfile
from pathlib import Path

GH = "https://github.com"
RAW = "https://raw.githubusercontent.com"

# Pinned releases (checked 2026-10). Update procedure: references/maintenance.md
MANIFEST = {
    "en16931-ubl": {
        "version": "1.3.17",
        "url": f"{GH}/ConnectingEurope/eInvoicing-EN16931/releases/download/validation-1.3.17/en16931-ubl-1.3.17.zip",
        "sha256": "bf02a0e3f6cbe692a4a28e70be7bdcaded5612b4169b543e13d6cb4f33c29e92",
        "xslt": "xslt/EN16931-UBL-validation.xslt",
        "title": "CEN EN 16931 business rules (UBL)",
    },
    "en16931-cii": {
        "version": "1.3.17",
        "url": f"{GH}/ConnectingEurope/eInvoicing-EN16931/releases/download/validation-1.3.17/en16931-cii-1.3.17.zip",
        "sha256": "e5f3235824b6b38454b1d54cf3f14e01efb5b33971fbefc4e64997d0ef619e89",
        "xslt": "xslt/EN16931-CII-validation.xslt",
        "title": "CEN EN 16931 business rules (CII)",
    },
    "xrechnung-ubl": {
        "version": "3.0.2-schematron-2.6.0",
        "url": f"{GH}/itplr-kosit/xrechnung-schematron/releases/download/v2.6.0/xrechnung-3.0.2-schematron-2.6.0.zip",
        "sha256": "ca5e07afd04e72cd283d581590ffff3a15f4aac9d2f40c993345d78e67ea22b4",
        "xslt": "schematron/ubl/XRechnung-UBL-validation.xsl",
        "title": "KoSIT XRechnung 3.0 rules (UBL)",
        "cache_as": "xrechnung",
    },
    "xrechnung-cii": {
        "version": "3.0.2-schematron-2.6.0",
        "url": f"{GH}/itplr-kosit/xrechnung-schematron/releases/download/v2.6.0/xrechnung-3.0.2-schematron-2.6.0.zip",
        "sha256": "ca5e07afd04e72cd283d581590ffff3a15f4aac9d2f40c993345d78e67ea22b4",
        "xslt": "schematron/cii/XRechnung-CII-validation.xsl",
        "title": "KoSIT XRechnung 3.0 rules (CII)",
        "cache_as": "xrechnung",
    },
    "peppol-ubl": {
        "version": "3.0.20",
        "url": f"{RAW}/OpenPEPPOL/peppol-bis-invoice-3/v3.0.20/rules/sch/PEPPOL-EN16931-UBL.sch",
        "sha256": "5ddf3a2f6633147b20b7805df9902d825af1a984f10014fcee186d4170364b1d",
        "schematron": "PEPPOL-EN16931-UBL.sch",
        "xslt": "PEPPOL-EN16931-UBL.xsl",
        "title": "OpenPeppol BIS Billing 3.0 rules (UBL)",
    },
}
SCHXSLT = {
    "version": "1.10.1",
    "url": "https://repo1.maven.org/maven2/name/dmaus/schxslt/schxslt/1.10.1/schxslt-1.10.1.jar",
    "sha256": "4f4f21edab7b37f96ad59ae12a344d3510f1092ac46b6d81a4efa0120b73cb58",
}


def cache_dir():
    d = os.environ.get("EINVOICE_RULES_DIR")
    return Path(d).expanduser() if d else Path.home() / ".cache" / "eu-einvoice" / "rules"


def _download(url, sha256):
    req = urllib.request.Request(url, headers={"User-Agent": "eu-einvoice-skill"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    got = hashlib.sha256(data).hexdigest()
    if sha256 and got != sha256:
        raise RuntimeError(f"checksum mismatch for {url}\n expected {sha256}\n got      {got}")
    return data


def _target(name):
    m = MANIFEST[name]
    return cache_dir() / f"{m.get('cache_as', name)}-{m['version']}"


def xslt_path(name):
    """Path of the compiled validation XSLT, or None if not fetched yet."""
    p = _target(name) / MANIFEST[name]["xslt"]
    return p if p.exists() else None


def _schxslt_dir():
    d = cache_dir() / f"schxslt-{SCHXSLT['version']}"
    if not (d / "xslt/2.0/pipeline-for-svrl.xsl").exists():
        data = _download(SCHXSLT["url"], SCHXSLT["sha256"])
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for member in z.namelist():
                if member.startswith("xslt/"):
                    z.extract(member, d)
    return d


def compile_schematron(sch_path, out_path):
    from .saxon import processor

    pipeline = _schxslt_dir() / "xslt/2.0/pipeline-for-svrl.xsl"
    xp = processor().new_xslt30_processor()
    exe = xp.compile_stylesheet(stylesheet_file=str(pipeline))
    out = exe.transform_to_string(source_file=str(sch_path))
    if not out or "<xsl:stylesheet" not in out and "<xsl:transform" not in out:
        raise RuntimeError(f"SchXslt failed to compile {sch_path}")
    Path(out_path).write_text(out, encoding="utf-8")


def fetch(name, force=False, log=print):
    m = MANIFEST[name]
    target = _target(name)
    if xslt_path(name) and not force:
        return xslt_path(name)
    log(f"fetching {m['title']} {m['version']} ...")
    data = _download(m["url"], m["sha256"])
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    if m["url"].endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            z.extractall(target)
    else:
        (target / m["schematron"]).write_bytes(data)
    if m.get("schematron"):
        log(f"compiling {m['schematron']} to XSLT with SchXslt {SCHXSLT['version']} ...")
        compile_schematron(target / m["schematron"], target / m["xslt"])
    (target / "SOURCE.json").write_text(json.dumps({k: m[k] for k in ("title", "version", "url", "sha256")}, indent=2))
    return xslt_path(name)


def fetch_all(names=None, force=False, log=print):
    ok, failed = [], []
    for n in names or MANIFEST:
        try:
            fetch(n, force=force, log=log)
            ok.append(n)
        except Exception as e:  # network errors are reported, not fatal
            failed.append((n, str(e)))
            log(f"  ! {n}: {e}")
    return ok, failed


def status():
    rows = []
    for n, m in MANIFEST.items():
        p = xslt_path(n)
        rows.append({"name": n, "version": m["version"], "title": m["title"], "cached": bool(p), "path": str(p) if p else None})
    return rows


def check_updates():
    """Ask GitHub for newer releases than the pinned ones (informational)."""
    repos = {
        "en16931": ("ConnectingEurope/eInvoicing-EN16931", MANIFEST["en16931-ubl"]["version"]),
        "xrechnung": ("itplr-kosit/xrechnung-schematron", "v2.6.0"),
        "peppol": ("OpenPEPPOL/peppol-bis-invoice-3", "v3.0.20"),
    }
    out = {}
    for key, (repo, pinned) in repos.items():
        try:
            req = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases?per_page=1",
                                         headers={"User-Agent": "eu-einvoice-skill"})
            with urllib.request.urlopen(req, timeout=20) as r:
                latest = json.load(r)[0]["tag_name"]
            out[key] = {"pinned": pinned, "latest": latest}
        except Exception as e:
            out[key] = {"pinned": pinned, "error": str(e)}
    return out
