"""Check digits of identifiers that the Schematron rules do not (fully) verify.

A typo in a Leitweg-ID or SIREN produces an invoice that validates but is
routed to nobody or booked to the wrong company. These checks are cheap,
so the pre-flight runs them and reports a warning with the expected value.
Each function returns None when the value is fine, otherwise a message.
"""

import re

LEITWEG_RE = re.compile(r"^(\d{2,12})(?:-([A-Za-z0-9]{1,30}))?-(\d{2})$")


def _mod97_10_check(s):
    """ISO 7064 MOD 97-10 check digits for an alphanumeric string."""
    n = int("".join(str(int(c, 36)) for c in s.upper()) + "00")
    return 98 - n % 97


def looks_like_leitweg_id(value):
    return bool(LEITWEG_RE.match((value or "").strip()))


def check_leitweg_id(value):
    m = LEITWEG_RE.match((value or "").strip())
    if not m:
        return (f"'{value}' is not in Leitweg-ID form "
                "<Grobadressierung 2-12 digits>-<Feinadressierung, optional>-<2 check digits>")
    grob, fein, given = m.group(1), m.group(2) or "", m.group(3)
    expected = f"{_mod97_10_check(grob + fein):02d}"
    if expected != given:
        base = f"{grob}-{fein}" if fein else grob
        return (f"Leitweg-ID '{value}' has check digits {given}, but ISO 7064 MOD 97-10 gives {expected} "
                f"('{base}-{expected}'). Probably a typo: confirm the exact Leitweg-ID with the buyer "
                "before sending - a wrong one cannot be routed by the German e-invoice portals")
    return None


def _luhn_ok(digits):
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def check_siren(value):
    v = re.sub(r"\s", "", str(value or ""))
    if not re.fullmatch(r"\d{9}", v):
        return f"SIREN '{value}' must be exactly 9 digits"
    if not _luhn_ok(v):
        return f"SIREN '{value}' fails the Luhn check digit; confirm it (e.g. on annuaire-entreprises.data.gouv.fr)"
    return None


def check_siret(value):
    v = re.sub(r"\s", "", str(value or ""))
    if not re.fullmatch(r"\d{14}", v):
        return f"SIRET '{value}' must be exactly 14 digits (SIREN + 5-digit NIC)"
    if v.startswith("356000000"):  # La Poste: digit sum multiple of 5 instead of Luhn
        return None if sum(map(int, v)) % 5 == 0 else f"SIRET '{value}' (La Poste) fails its check"
    if not _luhn_ok(v):
        return f"SIRET '{value}' fails the Luhn check digit"
    return check_siren(v[:9])


def check_fr_vat(value):
    v = re.sub(r"\s", "", str(value or "")).upper()
    m = re.fullmatch(r"FR([0-9A-Z]{2})(\d{9})", v)
    if not m:
        return f"French VAT number '{value}' must be FR + 2-character key + 9-digit SIREN"
    key, siren = m.groups()
    if key.isdigit():
        expected = (12 + 3 * (int(siren) % 97)) % 97
        if int(key) != expected:
            return f"French VAT number '{value}': key {key} does not match SIREN {siren} (expected FR{expected:02d}{siren})"
    return check_siren(siren)


def check_be_enterprise(value):
    v = re.sub(r"[\s.]", "", str(value or "")).upper().removeprefix("BE")
    if not re.fullmatch(r"[01]\d{9}", v):
        return f"Belgian enterprise number '{value}' must be 10 digits starting with 0 or 1"
    if 97 - int(v[:8]) % 97 != int(v[8:]):
        return f"Belgian enterprise number '{value}' fails the mod-97 check"
    return None


def check_gs1(value, length=None):
    v = str(value or "").strip()
    if not v.isdigit() or (length and len(v) != length):
        return f"GS1 number '{value}' must be {length or 'all'} digits"
    body, check = v[:-1], int(v[-1])
    s = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    if (10 - s % 10) % 10 != check:
        return f"GS1 number '{value}' has a wrong check digit"
    return None


SCHEME_CHECKS = {
    "0002": check_siren,
    "0009": check_siret,
    "0204": check_leitweg_id,
    "0208": check_be_enterprise,
    "0088": lambda v: check_gs1(v, 13),
    "0160": check_gs1,
}


def check_scheme_id(scheme, value):
    fn = SCHEME_CHECKS.get(str(scheme or "").strip())
    return fn(value) if fn else None


def check_vat_id(value):
    v = str(value or "").upper()
    if v.startswith("FR"):
        return check_fr_vat(v)
    if v.startswith("BE"):
        return check_be_enterprise(v)
    return None
