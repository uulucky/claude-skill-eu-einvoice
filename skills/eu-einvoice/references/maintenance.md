# Maintaining the pinned rule sets

Rule sets get code-list and bug-fix releases about twice a year (typically
April/May and October/November). Validation results are only comparable if
everyone runs the same versions, so the skill pins exact releases with
SHA-256 in `scripts/einvoice/artifacts.py` (`MANIFEST`).

## Check for newer releases

```bash
python scripts/einvoice_cli.py rules check-updates
python scripts/einvoice_cli.py rules status
```

## Update a pin

1. Download the new release asset (URL pattern is in `MANIFEST`):
   - CEN: github.com/ConnectingEurope/eInvoicing-EN16931/releases (`en16931-ubl-X.zip`, `en16931-cii-X.zip`)
   - KoSIT: github.com/itplr-kosit/xrechnung-schematron/releases (`xrechnung-3.0.x-schematron-Y.zip`)
   - Peppol: raw `rules/sch/PEPPOL-EN16931-UBL.sch` at the release tag of
     github.com/OpenPEPPOL/peppol-bis-invoice-3
2. `shasum -a 256 <file>` and update `version`, `url`, `sha256` (and the
   `xslt` member path if the zip layout changed).
3. `python scripts/einvoice_cli.py rules fetch --force`
4. Regenerate every `assets/examples/*.json` with `create` and confirm all
   are still VALID; run the test cases under `evals/`.

A major XRechnung version (3.1, 4.0) also changes the specification
identifier in `scripts/einvoice/profiles.py` and possibly mandatory fields
(update `model._profile_checks` and `references/profiles.md`).

## Factur-X schematron

The Factur-X EN 16931 schematron and the UBL/CII XSDs come from the
`factur-x` Python package (akretion/factur-x, BSD). Upgrade that package to
pick up new Factur-X releases.
