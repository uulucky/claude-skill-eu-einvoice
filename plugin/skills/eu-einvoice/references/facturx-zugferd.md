# Factur-X / ZUGFeRD hybrid PDFs

## What makes a valid hybrid invoice

1. **PDF/A-3** (ISO 19005-3), because only PDF/A-3 allows embedded files in
   an archival PDF. Requirements that matter in practice:
   - all fonts embedded (the generated layout embeds a TrueType font:
     DejaVu Sans / Arial if present, otherwise Bitstream Vera from reportlab;
     set `EINVOICE_FONT=/path/regular.ttf` and `EINVOICE_FONT_BOLD=...` to use
     your corporate font - it must cover every character on the invoice),
   - an OutputIntent with an ICC profile (an sRGB profile is generated and added),
   - XMP metadata with `pdfaid:part=3` and the Factur-X extension schema
     (`fx:DocumentType`, `fx:DocumentFileName`, `fx:Version`, `fx:ConformanceLevel`),
   - no encryption, no JavaScript, no external content.
2. The CII XML attached as **`factur-x.xml`** (ZUGFeRD 2.x uses the same name)
   with `/AFRelationship` - `Data` by default (Factur-X), `Alternative` is
   also common in Germany. Both are accepted by the spec.
3. Visual content and XML must say the same thing. The XML is legally
   authoritative in Germany; never edit one without regenerating the other.

## Using the customer's own PDF layout

`create invoice.json --profile facturx --pdf erp-layout.pdf -o out.pdf`
embeds the XML into an existing PDF. The tool adds the OutputIntent and XMP,
but cannot embed fonts that the source PDF left out: PDFs exported from Word
or most ERPs embed fonts, "Print to PDF" from browsers usually does too;
PDFs using the 14 standard fonts (Helvetica, Times...) without embedding are
not PDF/A conformant. If in doubt, verify (below) or use the generated layout.

## Formal PDF/A verification (optional)

veraPDF is the reference validator (Java):

```bash
# https://verapdf.org/software/ - CLI after install:
verapdf --flavour 3b out.pdf
```

The skill's `validate` checks the container (embedded XML, filename, XMP
pdfaid part 3, Factur-X XMP, OutputIntent) and the XML fully, but not
glyph-level PDF/A rules; say so when it matters (archiving, public tenders).

## Profiles

| Factur-X | ZUGFeRD 2.x name | full invoice? | here |
|---|---|---|---|
| MINIMUM | MINIMUM | no (booking aid only; not an invoice in DE) | no |
| BASIC WL | BASIC WL | no line items | no |
| BASIC | BASIC | yes, restricted | no |
| EN 16931 | COMFORT | yes - EN 16931 compliant | **yes** |
| EXTENDED | EXTENDED | yes, superset | no |
| – | XRECHNUNG | XRechnung CII inside a PDF | no (send plain XRechnung instead) |

## Reading a received Factur-X / ZUGFeRD

`extract received.pdf -o data.json`, `validate received.pdf`,
`render received.pdf -o view.html`. If `extract` says the PDF has no
embedded XML, it is an ordinary PDF invoice - not an e-invoice in the sense
of the German 2025 rules.
