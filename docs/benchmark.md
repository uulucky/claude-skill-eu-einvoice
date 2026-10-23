# Benchmark: with skill vs. without skill

The benchmark followed the skill-creator method. Each case ran as an independent
Claude agent (Opus 5.5) twice: once with the skill and once without it. All outputs
were graded by script with the official validators, plus checks on amounts and
identifiers. Run date: 2026-10-23. The cases are in [`../evals`](../evals).

## Round 1: standard cases

The without-skill runs got a Python environment with lxml, saxonche and factur-x
already installed.

| Case | With skill | Without skill |
|---|---|---|
| XRechnung for a city (freelancer, chat data) | 4/4, 67 s | 4/4, 132 s |
| Fix a rejected Peppol invoice (R003, CL008, BR-CO-15) | 4/4, 73 s | 4/4, 139 s |
| Factur-X PDF for a French client | 4/4, 82 s | 4/4, 225 s |
| **Mean** | **100 %, 74 s** | **100 %, 165 s** |

Both configurations passed everything, but with the skill each case finished about
2.2× faster. Without it, the agent had to write a generator and a validation pipeline
from scratch every time.

## Round 2: harder cases, nothing pre-installed

| Case | With skill | Without skill |
|---|---|---|
| XRechnung CII: price per 100 pieces, 19 %/7 %, freight, 500 € prepayment, Skonto, mistyped Leitweg-ID | 5/5, 124 s | 4/5, 178 s |
| ZUGFeRD PDF → XRechnung UBL for a federal authority (ZRE) | 5/5, 93 s | 5/5, 234 s |
| Belgian Peppol credit note: line discount, goodwill credit, two VAT rates | 5/5, 104 s | 5/5, 166 s |
| **Mean** | **100 %, 107 s** | **93 %, 193 s** |

The one difference was in the first case. The user gave the Leitweg-ID
`08315000-0001-34`, but its MOD 97-10 check digits should be `43`. The skill's
pre-flight caught this, and the agent asked the user to confirm the ID before sending.
Without the skill, the agent wrote the wrong ID into the invoice, and the official
Schematron does not check it.

## Notes

- A strong model can produce compliant XML without the skill when it has enough time
  and tooling. The skill makes the result faster and consistent, and it adds checks a
  from-scratch approach tends to skip.
- Trigger-description optimization: the skill-creator optimization loop and a
  hand-tuned variant were each compared with the shipped description at low
  concurrency (20 queries × 3 runs). The shipped description triggered most reliably
  (mean recall 37–43 % against 13–17 %). None of the three versions ever triggered on
  the ten near-miss queries (OCR, Stripe, SEPA, camt.053, India GST, …). The harness
  only counts a trigger when the skill is the very first tool call, so in real use the
  skill triggers more often than these numbers suggest.
