# eu-einvoice: a Claude skill for European e-invoices

[中文说明](https://github.com/uulucky/claude-skill-eu-einvoice/blob/main/README.zh-CN.md) · [PyPI: eu-einvoice](https://pypi.org/project/eu-einvoice/)

![Demo: creating a validated XRechnung and diagnosing a rejected Peppol invoice](https://raw.githubusercontent.com/uulucky/claude-skill-eu-einvoice/main/docs/img/demo.gif)

A Claude skill (packaged as a Claude Code plugin) that **creates, validates, reads and
converts European structured e-invoices** following EN 16931: **XRechnung** (UBL and CII),
**Peppol BIS Billing 3.0**, **ZUGFeRD / Factur-X** hybrid PDFs, and plain UBL 2.1 or
UN/CEFACT CII.

Ask Claude in plain words, for example "make this an XRechnung for the city of Köln",
"why was my Peppol invoice rejected with BR-CO-15?", or "what's in this xrechnung.xml
my supplier sent?". Claude then uses the bundled tooling instead of writing XML by hand:

- **Amounts are computed, not typed.** Line totals, the VAT breakdown per category and
  rate, document totals, prepayments and allowances are calculated to the cent, the
  way EN 16931 (BR-CO-10..17) and Peppol (R040, R120) require. Arithmetic is the most
  common reason e-invoices get rejected.
- **It is validated with the official rules**, the same ones receiving platforms use:
  XSD, CEN EN 16931 Schematron, KoSIT XRechnung and OpenPeppol BIS 3.0. They run in
  pure Python through Saxon-HE (`saxonche`), so **no Java is needed**. Rule sets are
  pinned to exact releases and SHA-256 verified.
- **Errors come with fixes.** Each finding shows the official rule ID, its message, the
  location and a hint written in terms of the invoice data.
- **It checks what the official rules miss:** check digits of Leitweg-IDs, SIREN, SIRET,
  French and Belgian VAT numbers and GLN/GTIN. A typo there gives an invoice that
  validates but can't be routed.
- **It reads and converts invoices.** Received XML or Factur-X/ZUGFeRD PDFs become JSON,
  or a readable HTML/PDF with labels in the seller's language (de/fr/nl/it/es/en).
  Conversions (UBL ↔ CII, ZUGFeRD → XRechnung, …) keep the source amounts.
- **It makes Factur-X / ZUGFeRD PDFs**: PDF/A-3 with embedded fonts, an sRGB
  OutputIntent, Factur-X XMP metadata and the embedded `factur-x.xml`. It can also
  embed the XML into your own PDF layout.

## Install

**Claude Code** (plugin marketplace):

```
/plugin marketplace add uulucky/claude-skill-eu-einvoice
/plugin install eu-einvoice@uulucky-skills
```

**claude.ai / Claude desktop app**: download `eu-einvoice.skill` from the
[latest release](https://github.com/uulucky/claude-skill-eu-einvoice/releases/latest)
and upload it as a skill (drag it into a chat and click "Save skill", or upload it in
the Skills settings).

**Manual**: copy `plugin/skills/eu-einvoice/` to `~/.claude/skills/eu-einvoice/`.

**Without Claude** (Python library and command line):

```bash
pip install eu-einvoice
eu-einvoice template xrechnung-b2g > invoice.json   # edit, then:
eu-einvoice create invoice.json -o invoice.xml      # computes totals, writes XML, validates it
```

**Requirements**: Python 3.9+. On first use the skill creates a virtual environment from
`plugin/skills/eu-einvoice/requirements.txt` (lxml, saxonche, factur-x, pypdf, reportlab). The
official rule sets are downloaded on the first validation into `~/.cache/eu-einvoice/rules`
(set `EINVOICE_RULES_DIR` to change the location).

## What you can ask

| You say | What happens |
|---|---|
| "Die Stadt Köln will eine XRechnung, Leitweg-ID …, 38 Std. à 85 € + Hosting 250 €" | builds the JSON, computes totals, writes XRechnung XML, validates it (XSD + CEN + KoSIT) |
| "Our Belgian customer rejected invoice-1187.xml (R003, CL008, BR-CO-15)" | explains each error, regenerates a corrected Peppol invoice and re-validates it |
| "Make a Factur-X PDF for my French client" | renders the invoice, makes it PDF/A-3, embeds `factur-x.xml`, validates both |
| "I got xrechnung.xml from a supplier and can't open it" | shows amount, due date and IBAN, and renders a printable PDF |
| "Convert this ZUGFeRD PDF to XRechnung UBL for the ZRE portal" | extracts, adds the missing XRechnung fields (asks you for them), converts, validates |

The same commands work without Claude (`pip install eu-einvoice`):

```bash
eu-einvoice template                                  # list example scenarios
eu-einvoice check invoice.json -p xrechnung-ubl       # computed lines, VAT breakdown, problems
eu-einvoice create invoice.json -p peppol -o out.xml
eu-einvoice validate received.xml                     # or a Factur-X / ZUGFeRD PDF
eu-einvoice extract received.pdf -o data.json
eu-einvoice convert in.xml --to xrechnung-cii -o out.xml
eu-einvoice render received.xml -o view.pdf
```

## Profiles and rule sets

| Profile | Syntax | Validation layers |
|---|---|---|
| `xrechnung-ubl`, `xrechnung-cii` | UBL / CII | XSD, CEN EN 16931 1.3.17, KoSIT XRechnung 3.0.2 (schematron 2.6.0) |
| `peppol` | UBL | XSD, CEN EN 16931 1.3.17, OpenPeppol BIS Billing 3.0.20 |
| `facturx` | CII in PDF/A-3 | PDF container, Factur-X XSD, CEN EN 16931, Factur-X EN 16931 schematron |
| `en16931-ubl`, `en16931-cii` | UBL / CII | XSD, CEN EN 16931 |

Rule-set updates come out about twice a year. `einvoice_cli.py rules check-updates`
reports newer releases, and `plugin/skills/eu-einvoice/references/maintenance.md` explains how
to bump the pins.

## Quality

- All 35 official CEN example invoices round-trip (parse → regenerate as UBL and as CII
  → validate), 70/70.
- The bundled examples (B2G XRechnung, Peppol reverse charge, French Factur-X, credit
  note, intra-EU supply) are all valid.
- Six eval cases live in [`evals/`](https://github.com/uulucky/claude-skill-eu-einvoice/blob/main/evals); see [docs/benchmark.md](https://github.com/uulucky/claude-skill-eu-einvoice/blob/main/docs/benchmark.md)
  for with-skill vs. without-skill results. You can run them yourself with
  `claude plugin eval plugin --eval-dir evals`.

## Limits

- It **produces and checks** documents; it does not **send** them. Peppol needs an
  access point, and German B2G portals need an upload or a Peppol channel.
- PDF/A-3 output is built to the spec, but the formal glyph-level check needs
  [veraPDF](https://verapdf.org).
- Not covered: non-EN 16931 national formats (Italy FatturaPA/SDI, Poland KSeF, Spain
  Verifactu/Facturae, Hungary NAV, Greece myDATA, India GST/IRN), the Factur-X
  MINIMUM/BASIC WL/EXTENDED profiles, France's EXTENDED-CTC-FR flows, and the XRechnung
  extension profile.
- This is not tax advice. Choosing a VAT category or exemption is a tax decision, so
  check with your accountant.

## Third-party components

Python dependencies: [factur-x](https://github.com/akretion/factur-x) (BSD), which provides
the XSDs, the Factur-X schematron and PDF embedding; `saxonche` (Saxon-HE, MPL-2.0);
lxml; pypdf; reportlab. The validation artefacts are **not bundled**. They are
downloaded at run time from their publishers under the publishers' terms:
[CEN/TC 434 EN 16931 validation artefacts](https://github.com/ConnectingEurope/eInvoicing-EN16931),
[KoSIT XRechnung schematron](https://github.com/itplr-kosit/xrechnung-schematron) (Apache-2.0),
[OpenPeppol BIS Billing 3.0](https://github.com/OpenPEPPOL/peppol-bis-invoice-3),
and [SchXslt](https://github.com/schxslt/schxslt), which compiles the Peppol schematron.

## License

MIT, see [LICENSE](https://github.com/uulucky/claude-skill-eu-einvoice/blob/main/LICENSE).
