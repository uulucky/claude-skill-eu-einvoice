# Code lists you will need

The authoritative, versioned lists are published by the European Commission
("EN 16931 code lists", updated each April/October) and by OpenPeppol. The
validation step checks codes against the current lists, so when in doubt,
validate rather than guess. Below are the codes used in practice.

## Contents
- [VAT category (BT-118/151)](#vat-category-codes-uncl-5305-subset)
- [VAT exemption reason codes (BT-121)](#vat-exemption-reason-codes-vatex-bt-121)
- [Invoice type (BT-3)](#invoice-type-codes-untdid-1001-bt-3)
- [Payment means (BT-81)](#payment-means-uncl-4461-bt-81)
- [Units (BT-130)](#unit-codes-unece-rec-20--21-bt-130)
- [Electronic address schemes (BT-34/49)](#electronic-address-schemes-eas-bt-34--bt-49)
- [Identifier schemes ICD (BT-29/30/46/47/157)](#identifier-schemes-iso-6523-icd)
- [Allowance / charge reasons](#allowance--charge-reason-codes)
- [Note subjects (BT-21)](#note-subject-codes-untdid-4451-bt-21)

## VAT category codes (UNCL 5305 subset)

| code | meaning | rate | needs |
|---|---|---|---|
| S | standard / reduced rate | > 0 | seller VAT ID (or tax reg. / representative) |
| Z | zero-rated goods (e.g. UK-style zero rate, some IE/MT goods) | 0 | seller VAT ID |
| E | exempt (medical, education, financial, small-business schemes...) | 0 | exemption reason text or VATEX code |
| AE | reverse charge (buyer accounts for VAT: B2B services cross-border, construction services in DE §13b...) | 0 | seller AND buyer VAT ID |
| K | intra-community supply of goods (VAT-exempt dispatch to another EU business) | 0 | seller AND buyer VAT ID, delivery date/period, deliver-to country |
| G | export outside the EU | 0 | seller VAT ID |
| O | outside the scope of VAT (e.g. non-taxable person, out-of-scope services) | none | no seller/buyer VAT ID; cannot mix with other categories |
| L | Canary Islands IGIC | any | |
| M | Ceuta and Melilla IPSI | any | |
| B | Italian split payment | > 0 | |

Small-business exemptions (DE §19 UStG "Kleinunternehmer", FR "franchise en
base") are category **E** with a reason such as "Kein Ausweis von Umsatzsteuer,
da Kleinunternehmer gemäß §19 UStG" (DE) or code `VATEX-FR-FRANCHISE` (FR).

## VAT exemption reason codes (VATEX, BT-121)

| code | use with | meaning |
|---|---|---|
| VATEX-EU-AE | AE | reverse charge |
| VATEX-EU-IC | K | intra-community supply |
| VATEX-EU-G | G | export outside the EU |
| VATEX-EU-O | O | not subject to VAT |
| VATEX-EU-132 | E | exempt under Art. 132 Directive 2006/112/EC (public-interest activities); sub-codes VATEX-EU-132-1A ... -1Q |
| VATEX-EU-143 | E | exempt importation (Art. 143), sub-codes -1A ... |
| VATEX-EU-148 | E | international transport / vessels / aircraft (Art. 148), sub-codes A-G |
| VATEX-EU-151 | E | diplomatic / NATO / international bodies (Art. 151), sub-codes |
| VATEX-EU-309 | E | travel agents outside the EU (Art. 309) |
| VATEX-EU-79-C | E | amounts paid on behalf of the customer (disbursements, Art. 79(c)) |
| VATEX-EU-D | E | travel agents margin scheme |
| VATEX-EU-F | E | second-hand goods margin scheme |
| VATEX-EU-I | E | works of art margin scheme |
| VATEX-EU-J | E | collectors' items and antiques margin scheme |
| VATEX-FR-FRANCHISE | E | France: franchise en base de TVA |
| VATEX-FR-CNWVAT | E | France: invoice issued by a non-VAT-registered entity |

Always add the human-readable `reason` too - receivers read text, not codes.

## Invoice type codes (UNTDID 1001, BT-3)

380 commercial invoice · 381 credit note · 383 debit note · 384 corrected
invoice (XRechnung/DE) · 386 prepayment invoice · 389 self-billed invoice ·
261 self-billed credit note · 326 partial invoice · 875/876/877 partial
construction invoices (DE) · 751 invoice information for accounting purposes.
Peppol accepts a defined subset; XRechnung allows 326, 380, 384, 389, 381,
875, 876, 877.

## Payment means (UNCL 4461, BT-81)

| code | meaning | group required |
|---|---|---|
| 58 | SEPA credit transfer | `credit_transfers` (IBAN) |
| 30 | credit transfer (non-SEPA) | `credit_transfers` |
| 59 | SEPA direct debit | `direct_debit` (mandate, creditor ID, debited IBAN) |
| 49 | direct debit | `direct_debit` |
| 48 | bank card | `card` |
| 54 | credit card | `card` |
| 55 | debit card | `card` |
| 57 | standing agreement | – |
| 10 | in cash | – |
| 20 | cheque | – |
| 68 | online payment service | – |
| 97 | clearing between partners | – |
| 1 | instrument not defined | – |
| ZZZ | mutually defined | – |

## Unit codes (UN/ECE Rec 20 / 21, BT-130)

C62 one (piece) · H87 piece · EA each · XPP piece (package) · SET set · PR pair ·
HUR hour · MIN minute · DAY day · WEE week · MON month · ANN year ·
KGM kilogram · GRM gram · TNE tonne · MTR metre · KMT kilometre ·
MTK square metre · MTQ cubic metre · LTR litre · KWH kilowatt hour ·
LS lump sum · E48 service unit · XBX box · XPK package · P1 percent.
Use C62 when nothing else fits.

## Electronic address schemes (EAS, BT-34 / BT-49)

Common values (full list: CEF/EC "Electronic Address Scheme" code list):

| scheme | identifier |
|---|---|
| EM | e-mail address (allowed by EN 16931 and XRechnung; **not** routable in Peppol) |
| 0204 | DE Leitweg-ID (German public buyers) |
| 9930 | DE VAT number |
| 0088 | GS1 GLN |
| 0060 | DUNS |
| 0208 | BE enterprise number (KBO/BCE) |
| 9925 | BE VAT number |
| 0106 | NL Chamber of Commerce (KvK) |
| 0190 | NL OIN (government) |
| 9944 | NL VAT number |
| 0009 | FR SIRET |
| 0002 | FR SIRENE (SIREN) |
| 9957 | FR VAT number |
| 0007 | SE organisation number |
| 0192 | NO organisation number |
| 0184 | DK CVR |
| 0216 | FI OVT code |
| 9914 | AT VAT (UID) |
| 9915 | AT government (Verwaltungskennzeichen) |
| 0211 | IT VAT (Partita IVA) |
| 9920 | ES VAT |
| 0151 | AU ABN |
| 0195 | SG UEN |
| 0199 | Legal Entity Identifier (LEI) |

In Peppol, scheme + id must match the receiver's registration in the
Peppol Directory exactly.

## Identifier schemes (ISO 6523 ICD)

Used as `scheme` for `ids`, `legal_id`, `standard_item_id`: 0002 SIREN,
0009 SIRET, 0007 SE org.no, 0088 GLN, 0060 DUNS, 0106 KvK, 0190 OIN,
0192 NO org.no, 0208 BE KBO, 0184 DK CVR, 0160 GTIN (items), 0199 LEI.
German Handelsregister numbers have no ICD: give `legal_id` without scheme
(`{"id": "HRB 12345"}`) and the register court in `legal_info`.

## Allowance / charge reason codes

Allowances (UNCL 5189): 95 discount · 100 special rebate · 102 fixed long
term · 103 temporary · 104 standard · 41 bonus for works ahead of schedule ·
42 other bonus · 60 manufacturer's consumer discount · 62 due to military
status · 63 due to work accident · 64 special agreement · 65 production error
discount · 66 new outlet discount · 67 sample discount · 68 end-of-range
discount · 70 Incoterm discount · 71 point of sales threshold allowance ·
88 material surcharge/deduction.

Charges (UNCL 7161): FC freight service · ABL additional packaging ·
ADR other services · AAA telecommunication · ABK miscellaneous · ADK shipping ·
AEO collection and recycling · FI financing · LA labelling · PC packing ·
SAA shipping and handling · TAC testing.

## Note subject codes (UNTDID 4451, BT-21)

AAI general information · AAB terms of payments (DE: Zahlungsbedingungen) ·
ADU note · PMT payment information · PMD payment detail / remittance ·
REG regulatory information (e.g. FR mandatory legal mentions) · SUR supplier
remarks · TXD tax declaration · ABL government information.
France expects notes with subjects PMT (recovery fee), PMD (late-payment
penalties) and AAB (early payment discount) on B2B invoices.
