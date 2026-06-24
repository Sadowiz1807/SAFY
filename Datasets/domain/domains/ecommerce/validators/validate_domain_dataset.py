#!/usr/bin/env python
"""Domain-local validator wrapper for the generated ecommerce dataset.

Uses only standard library and delegates to the runpack validator when available.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    domain_dir = Path(__file__).resolve().parents[1]
    candidates = [
        Path('C:/tmp/safy_ecommerce_runpack/INPUT/validate_domain_dataset.py'),
        Path.cwd() / 'INPUT' / 'validate_domain_dataset.py',
    ]
    for validator in candidates:
        if validator.is_file():
            return subprocess.call([sys.executable, str(validator), str(domain_dir), '--domain', 'ecommerce'])
    print('Runpack validator not found; use INPUT/validate_domain_dataset.py from the runpack.', file=sys.stderr)
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
