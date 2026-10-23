"""Output profiles: which syntax, which identifiers, which rule sets.

A profile bundles everything that differs between e.g. "plain EN 16931 UBL",
"Peppol BIS Billing 3.0" and "XRechnung 3.0". Generators read the IDs from
here; the validator reads the rule-set list.
"""

PEPPOL_PROCESS = "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0"
EN16931 = "urn:cen.eu:en16931:2017"
PEPPOL_CUSTOMIZATION = EN16931 + "#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0"
XRECHNUNG_CUSTOMIZATION = EN16931 + "#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0"

PROFILES = {
    "en16931-ubl": {
        "syntax": "ubl",
        "customization_id": EN16931,
        "process_id": None,
        "rules": ["en16931-ubl"],
        "label": "EN 16931 core, UBL 2.1",
    },
    "en16931-cii": {
        "syntax": "cii",
        "customization_id": EN16931,
        "process_id": None,
        "rules": ["en16931-cii"],
        "label": "EN 16931 core, UN/CEFACT CII",
    },
    "peppol": {
        "syntax": "ubl",
        "customization_id": PEPPOL_CUSTOMIZATION,
        "process_id": PEPPOL_PROCESS,
        "rules": ["en16931-ubl", "peppol-ubl"],
        "label": "Peppol BIS Billing 3.0 (UBL)",
    },
    "xrechnung-ubl": {
        "syntax": "ubl",
        "customization_id": XRECHNUNG_CUSTOMIZATION,
        "process_id": PEPPOL_PROCESS,
        "rules": ["en16931-ubl", "xrechnung-ubl"],
        "label": "XRechnung 3.0 (UBL)",
    },
    "xrechnung-cii": {
        "syntax": "cii",
        "customization_id": XRECHNUNG_CUSTOMIZATION,
        "process_id": PEPPOL_PROCESS,
        "rules": ["en16931-cii", "xrechnung-cii"],
        "label": "XRechnung 3.0 (CII)",
    },
    "facturx": {
        "syntax": "cii",
        "customization_id": EN16931,
        "process_id": None,
        "rules": ["en16931-cii", "facturx-en16931"],
        "pdf": True,
        "label": "Factur-X / ZUGFeRD 2.x, profile EN 16931 (COMFORT)",
    },
}

ALIASES = {
    "ubl": "en16931-ubl",
    "cii": "en16931-cii",
    "en16931": "en16931-ubl",
    "peppol-bis": "peppol",
    "peppol-bis-3": "peppol",
    "xrechnung": "xrechnung-ubl",
    "zugferd": "facturx",
    "zugferd-en16931": "facturx",
    "facturx-en16931": "facturx",
    "factur-x": "facturx",
}


def get_profile(name):
    key = ALIASES.get(name.lower(), name.lower())
    if key not in PROFILES:
        raise ValueError(
            f"Unknown profile '{name}'. Choose one of: {', '.join(PROFILES)} "
            f"(aliases: {', '.join(ALIASES)})"
        )
    return key, PROFILES[key]


def detect_profile(customization_id, syntax):
    """Best-effort reverse lookup used when reading an existing XML."""
    cid = (customization_id or "").strip()
    if "xrechnung" in cid:
        return f"xrechnung-{syntax}"
    if "peppol" in cid and syntax == "ubl":
        return "peppol"
    return f"en16931-{syntax}"
