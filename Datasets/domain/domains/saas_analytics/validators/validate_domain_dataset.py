from __future__ import annotations
import subprocess, sys
from pathlib import Path
def main():
    d=Path(__file__).resolve().parents[1]
    v=Path('C:/tmp/safy_saas_runpack/INPUT/validate_domain_dataset.py')
    if not v.is_file():
        print('Runpack validator unavailable', file=sys.stderr); return 2
    return subprocess.call([sys.executable, str(v), str(d), '--domain', 'saas_analytics'])
if __name__ == '__main__': raise SystemExit(main())
