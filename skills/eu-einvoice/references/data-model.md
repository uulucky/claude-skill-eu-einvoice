# JSON invoice model

The CLI reads and writes this model. Keys are readable; each maps to an
EN 16931 business term (BT) or group (BG). Omit what you don't have - empty
strings and nulls are dropped, never written as empty XML elements.

Amounts may be strings or numbers; strings avoid binary float surprises
(`"39.90"`). Dates are `YYYY-MM-DD`.

## Contents
- [Document](#document)
- [Parties](#parties-seller-buyer)
- [Payee, tax representative, delivery](#payee-tax-representative-delivery)
- [Payment](#payment-bg-16)
- [Document allowances and charges](#document-level-allowances-and-charges)
- [Lines](#lines-bg-25)
- [VAT exemption reasons](#vat-exemption-reasons)
- [Computed / cross-checked values](#computed-and-cross-checked-values)
- [Attachments](#attachments-bg-24)

## Document

| key | BT | notes |
|---|---|---|
| `profile` | – | default profile if `--profile` not given |
| `type` | BT-3 | `invoice` (380), `credit_note` (381), `corrected` (384, DE only), `prepayment` (386), `self_billed` (389), `partial` (326), or any UNTDID 1001 code |
| `number` | BT-1 | invoice number, unique per seller |
| `issue_date` | BT-2 | |
| `due_date` | BT-9 | required when amount due > 0 unless `payment.terms` given (BR-CO-25) |
| `currency` | BT-5 | ISO 4217, default EUR |
| `tax_currency` | BT-6 | only if VAT must be reported in another currency; then `tax_total_in_tax_currency` (BT-111) is required |
| `tax_point_date` | BT-7 | date VAT becomes chargeable, if different from issue date |
| `tax_point_code` | BT-8 | `invoice` / `delivery` / `payment` (mapped to the right code list per syntax) |
| `buyer_reference` | BT-10 | XRechnung: Leitweg-ID (mandatory). Peppol: this or `order_reference` |
| `project_reference` | BT-11 | |
| `contract_reference` | BT-12 | |
| `order_reference` | BT-13 | buyer's purchase order number |
| `sales_order_reference` | BT-14 | seller's order confirmation number |
| `receiving_advice_reference` | BT-15 | |
| `despatch_advice_reference` | BT-16 | |
| `tender_reference` | BT-17 | tender or lot |
| `object_reference` | BT-18 | `"id"` or `{"id", "scheme"}` (UNTDID 1153 scheme, e.g. `AAG`) |
| `accounting_reference` | BT-19 | buyer's cost centre / account |
| `notes` | BT-22 (BT-21) | list of strings, or `{"subject": "AAI", "text": "..."}`; Peppol allows only one unless both parties are German |
| `period` | BG-14 | `{"start", "end"}` invoicing period |
| `preceding_invoices` | BG-3 | `[{"number", "date"}]` - required for credit notes in some countries, for 384 in XRechnung |
| `language` | – | label language for render: en, de, fr, nl, it, es (default from seller country) |

## Parties (`seller`, `buyer`)

| key | seller BT | buyer BT | notes |
|---|---|---|---|
| `name` | BT-27 | BT-44 | legal registration name |
| `trading_name` | BT-28 | BT-45 | |
| `ids` | BT-29 | BT-46 | list of `"id"` or `{"id", "scheme"}` (ISO 6523 ICD, e.g. `0088` GLN) |
| `legal_id` | BT-30 | BT-47 | company register no.; `{"id": "123456782", "scheme": "0002"}` (FR SIREN), `0106` (NL KvK), `0208` (BE KBO), `0007` (SE) |
| `vat_id` | BT-31 | BT-48 | with country prefix: `DE123456782`, `FR11123456782`, Greece `EL...` |
| `tax_registration_id` | BT-32 | – | local tax number (DE: Steuernummer) when no VAT ID |
| `legal_info` | BT-33 | – | additional legal info: share capital, register court, managing directors |
| `electronic_address` | BT-34 | BT-49 | `{"id", "scheme"}`; scheme is an EAS code (`EM` e-mail, `0204` Leitweg-ID, `9930` DE VAT, `0088` GLN, `0208` BE KBO, `0106` NL KvK, `0192` NO org.no). For Peppol this is the participant ID |
| `address` | BG-5 | BG-8 | `line1` (street), `line2`, `line3`, `city`, `postal_code`, `subdivision`, `country` (ISO alpha-2, mandatory) |
| `contact` | BG-6 | BG-9 | `{"name", "phone", "email"}`; XRechnung requires all three for the seller |

## Payee, tax representative, delivery

- `payee` (BG-10, only if someone other than the seller is paid, e.g. factoring):
  `{"name" BT-59, "ids" BT-60, "legal_id" BT-61}`
- `tax_representative` (BG-11): `{"name" BT-62, "vat_id" BT-63, "address" BG-12}`
- `delivery` (BG-13): `{"date" BT-72, "party_name" BT-70, "location_id" BT-71 (str or {"id","scheme"}), "address" BG-15}`.
  Intra-EU supply (K) needs `date` (or `period`) and `address.country`.

## Payment (BG-16)

```json
"payment": {
  "means_code": "58",                 // BT-81: 58 SEPA transfer, 30 transfer, 59 SEPA direct debit, 49 direct debit, 48/54/55 card, 10 cash, 57 standing agreement, 1 not defined
  "means_text": "SEPA credit transfer", // BT-82
  "remittance_info": "RE-2026-0042",  // BT-83 what the payer should put in the transfer reference
  "credit_transfers": [{"iban": "DE02...", "bic": "BYLADEM1001", "account_name": "..."}],  // BG-17 (BT-84..86); "account_id" for non-IBAN accounts
  "card": {"pan_last4": "1234", "network": "VISA", "holder": "..."},   // BG-18 - never the full card number
  "direct_debit": {"mandate_id": "...", "creditor_id": "DE98ZZZ09999999999", "debited_account": "DE..."},  // BG-19 (BT-89..91)
  "terms": "Zahlbar innerhalb 30 Tagen"  // BT-20
}
```
XRechnung Skonto must be machine-readable inside `terms`:
`"#SKONTO#TAGE=14#PROZENT=2.00#\n"` (one line per tier, upper case, exactly this
shape; free text may follow on later lines).

## Document level allowances and charges

`allowances` (BG-20) and `charges` (BG-21), each a list of:

| key | BT (allowance / charge) | notes |
|---|---|---|
| `amount` | BT-92 / BT-99 | computed from `percent` x `base_amount` if omitted |
| `base_amount` | BT-93 / BT-100 | defaults to the sum of line net amounts when only `percent` is given |
| `percent` | BT-94 / BT-101 | |
| `reason` | BT-97 / BT-104 | text; `reason` or `reason_code` required |
| `reason_code` | BT-98 / BT-105 | allowances UNCL 5189 (95 discount), charges UNCL 7161 (FC freight) |
| `vat_category`, `vat_rate` | BT-95/96, BT-102/103 | required: the allowance/charge falls into that VAT group |

## Lines (BG-25)

| key | BT | notes |
|---|---|---|
| `id` | BT-126 | defaults to 1, 2, 3... |
| `note` | BT-127 | |
| `object_id` | BT-128 | |
| `quantity` | BT-129 | negative allowed for returns on an invoice |
| `unit` | BT-130 | UN/ECE Rec 20/21, default `C62` |
| `net_amount` | BT-131 | **computed**; if given it is cross-checked |
| `period` | BG-26 | `{"start", "end"}` |
| `order_line_reference` | BT-132 | |
| `accounting_reference` | BT-133 | |
| `allowances` / `charges` | BG-27 / BG-28 | `{amount | percent(+base_amount), reason/reason_code}` - no VAT fields at line level |
| `price` | BT-146 | **net** unit price, never negative |
| `price_discount` | BT-147 | per-unit discount; with `gross_price` the net price is derived |
| `gross_price` | BT-148 | |
| `base_quantity` | BT-149 | price per N units, e.g. 100 |
| `base_unit` | BT-150 | defaults to `unit` (Peppol requires them equal) |
| `vat_category` | BT-151 | S, Z, E, AE, K, G, O, L, M, B |
| `vat_rate` | BT-152 | omit for O; 0 for Z/E/AE/K/G |
| `name` | BT-153 | required |
| `description` | BT-154 | |
| `seller_item_id` / `buyer_item_id` | BT-155 / BT-156 | |
| `standard_item_id` | BT-157 | `{"id": "4012345678901", "scheme": "0160"}` (GTIN) |
| `classifications` | BT-158 | `[{"id", "scheme" (UNTDID 7143: STI, HS, CV...), "version"}]` |
| `origin_country` | BT-159 | |
| `attributes` | BG-32 | `[{"name", "value"}]` |

Line net amount = quantity x price / base_quantity + charges - allowances,
rounded half-up to 2 decimals.

## VAT exemption reasons

Per category, for E (mandatory), AE, K, G, O (defaults filled in if absent):
```json
"vat_exemptions": {"E": {"code": "VATEX-EU-132", "reason": "Exempt based on article 132 of Council Directive 2006/112/EC"}}
```

## Computed and cross-checked values

Written by the tool (BG-22, BG-23): line net amounts, `vat_breakdown`
(per category+rate: taxable BT-116, tax BT-117 = taxable x rate / 100 rounded),
totals BT-106..BT-115. Optional inputs:

- `prepaid_amount` (BT-113), `rounding_amount` (BT-114)
- `totals` - the figures from the user's ERP (`line_total`, `allowance_total`,
  `charge_total`, `tax_exclusive`, `tax_total`, `tax_inclusive`, `payable`).
  A mismatch with the computed figures is an error: find which input is wrong
  instead of forcing the ERP number into the XML.
- `vat_breakdown` - when present (e.g. from `extract`), its tax amounts are
  compared; in convert/render (fidelity) mode a ±1 rounding difference allowed
  by BR-CO-17 is kept as in the source.

## Attachments (BG-24)

```json
"attachments": [{"id": "Timesheet-10-2026", "description": "Stundennachweis", "file": "~/Docs/timesheet.pdf"}]
```
`file` is read and embedded (base64) with its filename and MIME type; or give
`uri` (BT-124) for an external link. Peppol allows PDF, PNG, JPEG, CSV, XLSX,
ODS. Keep attachments small (most platforms cap the message at 10-100 MB).
