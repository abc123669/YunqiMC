#!/usr/bin/env python3
"""Run the formal paired suite, followed by a guarded 24-hour soak."""
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys

bench = Path(__file__).resolve().parent
status_path = bench / 'longrun-status.json'

def status(stage, **extra):
    temporary = status_path.with_suffix('.tmp')
    temporary.write_text(json.dumps({'stage': stage, 'updated_utc': dt.datetime.now(dt.timezone.utc).isoformat(), **extra}, indent=2), encoding='utf8')
    temporary.replace(status_path)
    print(stage, extra, flush=True)

def main():
    status('paired-running')
    result = subprocess.run([sys.executable, '-u', str(bench / 'paired.py')], cwd=bench.parent)
    if result.returncode:
        status('paired-failed', returncode=result.returncode)
        return result.returncode
    for bots in (10, 25):
        status(f'load-{bots}-running')
        result = subprocess.run([sys.executable, '-u', str(bench / 'paired.py'), '--smoke', '--pairs', '1',
                                 '--warmup', '60', '--seconds', '180', '--bots', str(bots)], cwd=bench.parent)
        if result.returncode:
            status(f'load-{bots}-failed', returncode=result.returncode)
            return result.returncode
    status('soak-running')
    result = subprocess.run([sys.executable, '-u', str(bench / 'paired.py'), '--smoke', '--pairs', '1',
                             '--warmup', '300', '--seconds', '86400', '--bots', '5'], cwd=bench.parent)
    if result.returncode:
        status('soak-failed', returncode=result.returncode)
        return result.returncode
    status('completed')
    return 0

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        status('failed', error=str(exc))
        raise
