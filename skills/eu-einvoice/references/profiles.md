# Profiles, CIUS rules and country mandates

## Contents
- [How the pieces fit](#how-the-pieces-fit)
- [Profiles in this skill](#profiles-in-this-skill)
- [XRechnung 3.0](#xrechnung-30-germany)
- [Peppol BIS Billing 3.0](#peppol-bis-billing-30)
- [Factur-X / ZUGFeRD](#factur-x--zugferd)
- [Country overview](#country-overview-status-as-of-october-2026)

## How the pieces fit

- **EN 16931** is the European semantic standard: ~160 business terms (BT/BG)
  and ~200 business rules (BR-xx). It is syntax-neutral.
- Two **syntaxes** carry it: **UBL 2.1** (OASIS) and **UN/CEFACT CII** (D16B).
  Same data, different XML.
- A **CIUS** (Core Invoice Usage Specification) restricts/clarifies EN 16931
  for a community and adds rules: XRechnung (DE public sector, rules BR-DE-xx),
  Peppol BIS Billing 3.0 (network, rules PEPPOL-EN16931-Rxxx + country rules
  like NL-R-xxx), Factur-X/ZUGFeRD (hybrid PDF).
- The `CustomizationID` (UBL) / `GuidelineSpecifiedDocumentContextParameter`
  (CII) - BT-24 - says which CIUS the document claims. Validators pick rules
  by it, so the profile you choose must match the receiver's expectations.

## Profiles in this skill

| profile | syntax | BT-24 specification identifier | rule layers run |
|---|---|---|---|
| `en16931-ubl` | UBL | `urn:cen.eu:en16931:2017` | XSD, CEN |
| `en16931-cii` | CII | `urn:cen.eu:en16931:2017` | XSD, CEN |
| `peppol` | UBL | `urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0` | XSD, CEN, Peppol |
| `xrechnung-ubl` | UBL | `urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0` | XSD, CEN, KoSIT |
| `xrechnung-cii` | CII | same | XSD, CEN, KoSIT |
| `facturx` | CII in PDF/A-3 | `urn:cen.eu:en16931:2017` (Factur-X EN 16931 = ZUGFeRD COMFORT) | PDF container, XSD, CEN, Factur-X |

Peppol and XRechnung also set BT-23 (business process) to
`urn:fdc:peppol.eu:2017:poacc:billing:01:1.0`.

## XRechnung 3.0 (Germany)

Required on top of EN 16931 (the tool pre-checks these):
- `buyer_reference` BT-10 (BR-DE-15). Public buyers give you a **Leitweg-ID**
  (format like `04011000-12345-03`); B2B buyers may give any reference.
- Seller contact name, phone, e-mail (BR-DE-2, -5, -6, -7).
- Seller and buyer city + post code (BR-DE-3/4/8/9).
- Seller and buyer electronic address BT-34/BT-49 (e-mail with scheme `EM`
  is fine; public buyers often use the Leitweg-ID with scheme `0204`).
- Payment instructions BG-16 (BR-DE-1), with the matching group for the
  means code (BR-DE-23/24/25).
- Seller VAT ID or Steuernummer (`tax_registration_id`) when VAT applies (BR-DE-16).
- Skonto only in the `#SKONTO#TAGE=n#PROZENT=n.nn#` form (BR-DE-18).
- Allowed type codes: 326, 380, 384, 389, 381, 875, 876, 877 (BR-DE-17).
- A delivery/service date (BT-72, BG-14 or BG-26) is a German legal
  requirement (§14 UStG) and a KoSIT warning (BR-DE-TMP-32).

UBL vs CII: both are accepted by federal and most state portals; UBL is the
more common default, but use what the buyer/portal specifies.

## Peppol BIS Billing 3.0

Required on top of EN 16931:
- Seller and buyer `electronic_address` = Peppol participant IDs
  (scheme + id, e.g. `0208` + Belgian enterprise number, `0106` KvK,
  `0192` Norwegian org.no, `9925` BE VAT, `0088` GLN). Look up the buyer in
  the Peppol Directory (directory.peppol.eu) - don't guess.
- `buyer_reference` or `order_reference` (R003).
- One document note only unless seller and buyer are both German (R002).
- Line amounts must equal quantity x price / base quantity +/- line
  allowances/charges, 2 decimals (R120); allowance amount = base x % (R040).
- Country rules apply by seller country: NL (KvK/OIN legal IDs, payment means),
  NO, DK, SE, IT, GR, DE. See hints in the validation output.
- Type codes 326/384 only between German parties (P0112).

Peppol is a network: the XML is sent via a certified access point (AP).
Belgium uses Peppol for its 2026 B2B mandate; many public sectors (NL, NO,
SE, DK, AU, NZ, SG, JP via JP PINT - different spec) receive via Peppol.

## Factur-X / ZUGFeRD

One standard under two names (FR: Factur-X 1.0.x, DE: ZUGFeRD 2.x). A
PDF/A-3 with the CII XML attached as `factur-x.xml`. Profiles: MINIMUM,
BASIC WL, BASIC, EN 16931 (= ZUGFeRD COMFORT), EXTENDED, XRECHNUNG. This skill
produces **EN 16931**, the only profile that is a full EN 16931 invoice in
the German B2B sense (MINIMUM/BASIC WL are not valid invoices in Germany).
See `facturx-zugferd.md`.

## Country overview (status as of October 2026)

Dates move; verify with the national authority before advising on deadlines.

| country | what | format(s) | covered here |
|---|---|---|---|
| Germany | B2G: XRechnung since 2020. B2B: receiving mandatory since 1 Jan 2025; issuing mandatory from 1 Jan 2027 for companies with prior-year turnover > EUR 800k, for all from 1 Jan 2028 | XRechnung, ZUGFeRD 2.x (EN 16931 or higher), other EN 16931 formats by agreement | yes |
| France | Reform (CTC via registered platforms, "PA"): receiving for all and issuing for large/mid-size from 1 Sep 2026; small and micro businesses issue from 1 Sep 2027. E-reporting alongside | UBL, CII, Factur-X (EN 16931 + French extensions/flows) | EN 16931 documents yes; platform submission and FR CTC extensions no |
| Belgium | B2B mandatory via Peppol from 1 Jan 2026 | Peppol BIS 3.0 | yes |
| Netherlands, Nordics | B2G via Peppol | Peppol BIS 3.0 (NL also SI-UBL) | yes (Peppol) |
| Austria | B2G via USP / Peppol | ebInterface or Peppol/EN 16931 UBL | Peppol / UBL yes |
| Croatia | B2B fiscalised e-invoicing from 1 Jan 2026 | EN 16931 UBL with HR extensions + fiscalisation | XML basis only, not fiscalisation |
| Poland | KSeF mandatory in 2026 | FA(3) XML (not EN 16931) | no |
| Italy | SDI since 2019 | FatturaPA (not EN 16931) | no |
| Spain | Verifactu / B2B e-invoice law being phased in | Facturae, UBL, CII, EDIFACT via platforms | not specifically |

Any EU public buyer must accept EN 16931 invoices in UBL or CII (Directive
2014/55/EU), so `en16931-ubl` is a safe fallback for B2G outside Germany.
