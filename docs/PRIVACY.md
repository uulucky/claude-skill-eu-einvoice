# Privacy policy: eu-einvoice

_Last updated: 2026-10-24_

eu-einvoice is an open-source skill/plugin and Python package. It runs entirely in your own
environment (your computer, or the code-execution environment of the Claude app you use).

**What it processes.** The invoice data you give it (names, addresses, VAT and registration
numbers, bank details, line items) is processed locally to compute amounts, generate XML/PDF
files and validate them. Nothing is sent to the author or to any third party by this software.

**Network access.** The software makes outbound requests only to download public resources:
the official validation rule sets (from github.com and raw.githubusercontent.com) and the
SchXslt compiler (from repo1.maven.org), plus Python packages from PyPI when you install it.
These requests contain no invoice data.

**No telemetry, no accounts, no cookies.** The software collects no usage data and has no
server component.

**Claude.** When you use it through Claude, your conversation is handled by Anthropic under
Anthropic's own privacy policy; this plugin does not change that.

**Contact.** Questions or issues: https://github.com/uulucky/claude-skill-eu-einvoice/issues
