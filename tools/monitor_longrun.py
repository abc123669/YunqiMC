#!/usr/bin/env python3
"""Create local reports when a guarded long-running benchmark finishes."""
import ctypes
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / 'bench'
DIST = ROOT / 'dist'

def running(pid):
    kernel = ctypes.windll.kernel32
    kernel.OpenProcess.restype = ctypes.c_void_p
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    try:
        code = ctypes.c_ulong()
        return bool(kernel.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code))) and code.value == 259
    finally:
        kernel.CloseHandle(ctypes.c_void_p(handle))

def complete(suite):
    plan_path, result_path = suite / 'plan.json', suite / 'results.jsonl'
    if not plan_path.exists() or not result_path.exists() or (suite / 'failures.jsonl').exists():
        return False
    try:
        plan = json.loads(plan_path.read_text(encoding='utf8'))
        lines = result_path.read_text(encoding='utf8').splitlines()
        if len(lines) != len(plan['plan']):
            return False
        for line in lines:
            json.loads(line)
        return True
    except (OSError, ValueError, KeyError):
        return False

def main():
    if len(sys.argv) != 3:
        raise SystemExit('Usage: monitor_longrun.py <supervisor-pid> <paired-suite-directory>')
    pid, paired = int(sys.argv[1]), Path(sys.argv[2])
    pair_written = soak_written = False
    load_written = set()
    while True:
        if not pair_written and complete(paired):
            result = subprocess.run([sys.executable, str(BENCH / 'analyze_pairs.py'), str(paired)],
                                    capture_output=True, text=True, encoding='utf8')
            if result.returncode:
                (DIST / 'benchmark-report-error.txt').write_text(result.stderr or result.stdout, encoding='utf8')
            else:
                (DIST / 'benchmark-report.json').write_text(result.stdout, encoding='utf8')
            pair_written = True
        status_path = BENCH / 'longrun-status.json'
        try:
            state = json.loads(status_path.read_text(encoding='utf8'))['stage']
        except (OSError, ValueError, KeyError):
            state = 'unknown'
        for plan_path in (BENCH / 'suite-runs').glob('*/plan.json'):
            try:
                plan = json.loads(plan_path.read_text(encoding='utf8'))
            except (OSError, ValueError):
                continue
            args = plan.get('args', {})
            bots = args.get('bots')
            if args.get('smoke') and args.get('seconds') == 180 and bots in (10, 25) and bots not in load_written:
                suite = plan_path.parent
                if complete(suite):
                    (DIST / f'load-{bots}-report.json').write_text((suite / 'results.jsonl').read_text(encoding='utf8'), encoding='utf8')
                    load_written.add(bots)
        if state == 'completed' and not soak_written:
            candidates = []
            for plan_path in (BENCH / 'suite-runs').glob('*/plan.json'):
                try:
                    plan = json.loads(plan_path.read_text(encoding='utf8'))
                except (OSError, ValueError):
                    continue
                if plan.get('args', {}).get('smoke') and plan['args'].get('seconds') == 86400:
                    candidates.append(plan_path.parent)
            if candidates:
                soak = max(candidates, key=lambda p: p.name)
                if complete(soak):
                    (DIST / 'soak-report.json').write_text((soak / 'results.jsonl').read_text(encoding='utf8'), encoding='utf8')
                    soak_written = True
        if state.endswith('failed') or state == 'failed':
            (DIST / 'benchmark-incomplete.txt').write_text('The benchmark stopped before completion. See bench/longrun-status.json and bench/longrun.stderr.log.\n', encoding='utf8')
            return
        if state == 'completed' and pair_written:
            return
        if not running(pid):
            (DIST / 'benchmark-incomplete.txt').write_text('The benchmark supervisor is no longer running. Inspect bench/longrun-status.json and logs.\n', encoding='utf8')
            return
        time.sleep(20)

if __name__ == '__main__':
    main()
