#!/usr/bin/env python3
"""Entry point used by the skill: python scripts/einvoice_cli.py <command> ...

The implementation lives in eu_einvoice/cli.py (also installed as the
`eu-einvoice` command by `pip install eu-einvoice`).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from eu_einvoice.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
