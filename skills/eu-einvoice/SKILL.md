---
name: eu-einvoice
description: Create, validate, read and convert European structured e-invoices (EN 16931) - XRechnung (UBL/CII), Peppol BIS Billing 3.0, Factur-X / ZUGFeRD hybrid PDFs, plain UBL 2.1 and UN/CEFACT CII - with totals and VAT computed for you and validation against the official CEN, KoSIT and OpenPeppol Schematron rules (no Java needed). Use this skill whenever the user needs an e-invoice / E-Rechnung / facture électronique / e-factuur, mentions XRechnung, ZUGFeRD, Factur-X, Peppol, UBL, CII, EN 16931, Leitweg-ID, B2G invoicing in Germany, the German 2025-2028 B2B e-invoice mandate, the French 2026 e-invoicing reform, Belgium's 2026 Peppol mandate, asks why an e-invoice was rejected (BR-xx, BR-DE-xx, PEPPOL-EN16931-Rxxx errors), wants to read/visualise an invoice XML they received, or wants to turn invoice data (ERP export, CSV row, PDF content, chat description) into a compliant e-invoice - even if they only say "make this invoice machine-readable" or "my customer wants the invoice as XML".
---

# EU e-invoicing (EN 16931)

This skill turns invoice data into e-invoices that pass the official validators
on the first try, and explains/repairs ones that don't. The heavy lifting is in
`scripts/einvoice_cli.py`; your job is to get the data right, pick the right
profile, run the tool and explain the result.

Why a tool instead of writing XML by hand: e-invoices are rejected for things
that are easy to get wrong and hard to see - element order fixed by the XSD,
VAT breakdown per (category, rate) group, totals that must reconcile to the
cent (BR-CO-10..17), identifier schemes, code lists, and per-country rules.
The CLI computes all amounts from the lines and validates the output with the
same rule sets the receiving platforms use.

## Setup (once per machine)

```bash
python3 -m venv ~/.venvs/einvoice && ~/.venvs/einvoice/bin/pip install -r <skill-dir>/requirements.txt
```

Use that interpreter for every command below (`~/.venvs/einvoice/bin/python`).
The official rule sets are downloaded and SHA-256-verified on first validation
into `~/.cache/eu-einvoice/rules` (override with `EINVOICE_RULES_DIR`).
Without network, validation still runs XSD + local checks and reports which
layers were skipped - never present such a result as fully valid.

## Pick the profile

| Situation | `--profile` |
|---|---|
| German public-sector buyer (Bund/Länder/Kommunen), or German B2B buyer who asks for XRechnung | `xrechnung-ubl` (or `xrechnung-cii` if the buyer asks for CII) |
| German B2B buyer who wants a PDF they can also read (ZUGFeRD) / any French buyer (Factur-X) | `facturx` (PDF/A-3 with embedded CII, profile EN 16931) |
| Sending over the Peppol network (Belgium B2B since 2026, NL/Nordics/AU/SG public sector, any buyer with a Peppol ID) | `peppol` |
| Buyer just wants "EN 16931 XML" / unsure / internal archive | `en16931-ubl` (or `en16931-cii`) |

Details, country timelines and what each profile requires:
`references/profiles.md`. If the right profile is genuinely unclear (e.g. a
German B2B buyer with no stated preference), ask the user rather than guess:
the receiver's platform decides what it accepts.

## Creating an e-invoice

1. **Start from a template** close to the scenario:
   `python scripts/einvoice_cli.py template` lists them; `template <name>` prints one.
   The JSON keys map 1:1 to EN 16931 business terms - see
   `references/data-model.md` when you need a field not in the template.
2. **Fill in the user's real data.** Never invent tax IDs, IBANs, Leitweg-IDs,
   Peppol participant IDs, legal registration numbers or customer references -
   a plausible-looking fake gets the invoice rejected or the payment misrouted.
   If something mandatory is missing, ask for it (list everything missing in one
   question). Placeholders are acceptable only when the user explicitly wants a
   sample/test invoice, and say so.
   - Give each line `quantity`, `unit` (UN/ECE Rec 20, e.g. C62 piece, HUR hour,
     DAY, MON, KGM), `price` (net unit price), `vat_category`, `vat_rate`.
   - Do **not** type line totals, VAT amounts or document totals - they are
     computed. If the user has totals from their ERP, put them in `"totals"` so
     the tool cross-checks them and you can report any discrepancy.
   - VAT category: `S` standard, `Z` zero-rated, `E` exempt (needs a reason),
     `AE` reverse charge, `K` intra-EU supply, `G` export, `O` outside scope.
     Choosing it is a tax decision: follow what the user/their accountant says;
     `references/codes.md` explains each one and the VATEX reason codes.
3. **Pre-flight**: `python scripts/einvoice_cli.py check invoice.json --profile <p>`
   prints computed lines, the VAT breakdown and totals plus every problem with
   its JSON path and the rule behind it. Fix the JSON until there are no errors.
   It also verifies check digits the official rules don't (Leitweg-ID, SIREN,
   SIRET, French/Belgian VAT, GLN/GTIN). A check-digit warning almost always
   means a typo in what the user gave you: tell them the expected value and ask
   them to confirm with the buyer - never silently "correct" an identifier.
4. **Create**: `python scripts/einvoice_cli.py create invoice.json --profile <p> -o out.xml`
   (`-o out.pdf` for `facturx`; add `--pdf their-layout.pdf` to embed the XML
   into the user's own PDF instead of the generated layout). It writes the file
   and immediately validates it with XSD + CEN + CIUS rules.
5. **Report** to the user: file path, profile, net / VAT / gross / due amounts,
   and the validation verdict including which rule-set versions ran. Show any
   warnings with a one-line explanation. Offer `render` if they want to eyeball it.

Credit notes: `"type": "credit_note"` with **positive** quantities and prices
(the document type carries the sign) and `preceding_invoices` pointing to the
original. Corrections (`"type": "corrected"`, code 384) are XRechnung/DE-only.

## Validating or explaining a file someone else made

```bash
python scripts/einvoice_cli.py validate their.xml            # or their.pdf (Factur-X/ZUGFeRD)
python scripts/einvoice_cli.py validate their.xml --json     # machine-readable
```

The profile is detected from the CustomizationID / guideline; force it with
`--profile`. Each finding has the official rule ID, message, location and a
`fix:` hint phrased in terms of the JSON model. Explain errors in plain
language, grouped by cause (one wrong VAT rate often triggers five rules).
To repair: `extract` to JSON, fix the data, then `create ... --recompute`
(drops the source's totals and line amounts so the corrected figures are
computed; without it, wrong source totals are reported as errors - useful for
showing the user the discrepancy first). Regenerating is far more reliable
than patching XML by hand.

## Reading, rendering and converting

- `extract invoice.xml|.pdf -o data.json` - JSON model of a received e-invoice
  (also pulls the XML out of a Factur-X/ZUGFeRD PDF). Use it to answer
  questions about an invoice or to feed bookkeeping.
- `render invoice.xml -o invoice.html` (or `.pdf`) - human-readable view,
  labels in the seller's language (de/fr/nl/it/es/en). Use this when someone
  received an XRechnung and "can't open it".
- `convert in.xml --to xrechnung-cii -o out.xml` - between syntaxes/profiles
  (UBL <-> CII, plain -> Peppol, CII -> Factur-X PDF). Source amounts are kept
  as-is (fidelity mode) and re-checked; profile-specific mandatory data that the
  source lacks (e.g. Leitweg-ID, Peppol endpoint IDs) is reported - ask the
  user for it, add it to the extracted JSON and `create` instead.

## Things to tell the user when relevant

- This skill produces and checks the document. **Transmission** is separate:
  Peppol needs an access point provider; German B2G portals (ZRE/OZG-RE,
  state portals) need an upload or a Peppol/email channel; Factur-X can simply
  be emailed. Do not claim an invoice "was sent".
- PDF/A-3 conformance of generated Factur-X PDFs is built in (embedded fonts,
  sRGB OutputIntent, XMP) but formally verifying it needs veraPDF - see
  `references/facturx-zugferd.md`. When embedding into the user's own PDF,
  its fonts must be embedded for PDF/A to hold.
- Not covered: national non-EN16931 formats (Italy FatturaPA/SDI, Poland KSeF
  FA(3), Spain Verifactu/Facturae, Hungary NAV, Greece myDATA), Factur-X
  MINIMUM/BASIC WL/EXTENDED profiles, France's EXTENDED-CTC-FR flows,
  XRechnung extension profile. Say so instead of improvising them.

## Reference files (read when needed)

- `references/data-model.md` - every JSON key with its BT/BG number and notes.
- `references/profiles.md` - profile rules, CIUS specifics, country mandates.
- `references/codes.md` - VAT categories & VATEX codes, payment means, units,
  EAS electronic-address schemes, document type codes, allowance/charge reasons.
- `references/facturx-zugferd.md` - hybrid PDFs, PDF/A-3, veraPDF, embedding.
- `references/maintenance.md` - updating the pinned rule-set versions.
