#!/usr/bin/env python3
"""Run isolated, resource-guarded, paired local Paper/YunqiMC benchmarks."""
import argparse
import ctypes
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import random
import shutil
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / 'bench'
PAPER = ROOT / 'run/paper/paper-1.21.11-132.jar'
YUNQI = ROOT / 'dist/yunqimc-server-1.21.11-0.1.0-alpha.1.jar'
SOURCE = ROOT / 'run/paper'
PORT = 26651
CREATE_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
PROCESS_FLAGS = CREATE_NO_WINDOW | getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0x00004000)

class MemoryStatus(ctypes.Structure):
    _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong),
                ('total_phys', ctypes.c_ulonglong), ('available_phys', ctypes.c_ulonglong),
                ('total_page', ctypes.c_ulonglong), ('available_page', ctypes.c_ulonglong),
                ('total_virtual', ctypes.c_ulonglong), ('available_virtual', ctypes.c_ulonglong),
                ('available_extended_virtual', ctypes.c_ulonglong)]

class FileTime(ctypes.Structure):
    _fields_ = [('low', ctypes.c_ulong), ('high', ctypes.c_ulong)]

class ProcessMemory(ctypes.Structure):
    _fields_ = [('cb', ctypes.c_ulong), ('page_faults', ctypes.c_ulong),
                ('peak_working_set', ctypes.c_size_t), ('working_set', ctypes.c_size_t),
                ('quota_peak_paged', ctypes.c_size_t), ('quota_paged', ctypes.c_size_t),
                ('quota_peak_nonpaged', ctypes.c_size_t), ('quota_nonpaged', ctypes.c_size_t),
                ('pagefile_usage', ctypes.c_size_t), ('peak_pagefile_usage', ctypes.c_size_t)]

def memory():
    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise OSError('GlobalMemoryStatusEx failed')
    return {'physical_available': status.available_phys, 'commit_available': status.available_page}

def process_sample(pid):
    kernel = ctypes.windll.kernel32
    kernel.OpenProcess.restype = ctypes.c_void_p
    handle = kernel.OpenProcess(0x1000 | 0x0010, False, pid)
    if not handle:
        raise OSError('Cannot open benchmark process for metrics')
    try:
        creation, exit_time, system, user = FileTime(), FileTime(), FileTime(), FileTime()
        ptr = ctypes.c_void_p(handle)
        if not kernel.GetProcessTimes(ptr, ctypes.byref(creation), ctypes.byref(exit_time), ctypes.byref(system), ctypes.byref(user)):
            raise OSError('Cannot read benchmark process CPU time')
        info = ProcessMemory()
        info.cb = ctypes.sizeof(info)
        if not ctypes.windll.psapi.GetProcessMemoryInfo(ptr, ctypes.byref(info), info.cb):
            raise OSError('Cannot read benchmark process memory')
        ticks = (system.high << 32) + system.low + (user.high << 32) + user.low
        return {'server_cpu_seconds': ticks / 10_000_000, 'server_working_set_bytes': info.working_set,
                'server_commit_bytes': info.pagefile_usage}
    finally:
        kernel.CloseHandle(ctypes.c_void_p(handle))

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', PORT))

def record(path, value):
    with path.open('a', encoding='utf8') as out:
        out.write(json.dumps(value, ensure_ascii=False) + '\n')

def stop_process(proc, graceful=None):
    if proc is None or proc.poll() is not None:
        return
    if graceful is not None:
        try:
            proc.stdin.write(graceful + '\n')
            proc.stdin.flush()
            proc.wait(timeout=30)
            return
        except (OSError, subprocess.TimeoutExpired):
            pass
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)

def analyze(path, seconds):
    lines = path.read_text(encoding='utf8').splitlines()
    if not lines or lines[0] != 'tick,monotonic_ns,duration_ms':
        raise ValueError('Invalid tick CSV')
    footer = next((line for line in lines if line.startswith('# dropped=')), None)
    if footer != '# dropped=0':
        raise ValueError('Tick samples dropped or missing completion footer')
    rows = []
    for line in lines[1:]:
        if line.startswith('#'):
            continue
        tick, timestamp, duration = line.split(',')
        rows.append((int(tick), int(timestamp), float(duration)))
    if len(rows) < 2:
        raise ValueError('Insufficient tick samples')
    end = rows[-1][1]
    samples = [row for row in rows if end - row[1] <= seconds * 1_000_000_000]
    if len(samples) < 2 or (end - samples[0][1]) < (seconds - 2) * 1_000_000_000:
        raise ValueError('Sample window is shorter than requested')
    values = sorted(row[2] for row in samples)
    if not all(math.isfinite(value) and value >= 0 for value in values):
        raise ValueError('Invalid tick duration')
    percentile = lambda p: values[math.ceil(p * len(values)) - 1]
    elapsed = (samples[-1][1] - samples[0][1]) / 1e9
    return {'samples': len(samples), 'seconds': elapsed, 'p50_mspt': percentile(.5),
            'p95_mspt': percentile(.95), 'p99_mspt': percentile(.99), 'max_mspt': values[-1],
            'ticks_over_50ms': sum(v > 50 for v in values), 'observed_tps': (len(samples) - 1) / elapsed}

def run_one(suite, fixture, label, serial, args):
    available = memory()
    if available['physical_available'] < 4 * 1024**3 or available['commit_available'] < 4 * 1024**3:
        raise RuntimeError('Insufficient memory before starting a run')
    if shutil.disk_usage(suite).free < 4 * 1024**3:
        raise RuntimeError('Insufficient free disk space before starting a run')
    free_port()
    run = suite / f'{serial:02d}-{label}'
    server_dir = run / 'server'
    server_dir.mkdir(parents=True)
    for name in ('world', 'world_nether', 'world_the_end', 'plugins'):
        shutil.copytree(fixture / name, server_dir / name)
    (server_dir / 'plugins/bStats').mkdir(exist_ok=True)
    (server_dir / 'plugins/bStats/config.yml').write_text('enabled: false\n', encoding='utf8')
    # Reuse already-downloaded runtime files in a private copy. Paperclip still
    # validates its inputs; no network download occurs for each measurement.
    runtime_source = ROOT / ('run/paper' if label == 'paper' else 'run/yunqi')
    for name in ('cache', 'libraries'):
        shutil.copytree(runtime_source / name, server_dir / name)
    shutil.copy2(fixture / 'eula.txt', server_dir / 'eula.txt')
    (server_dir / 'server.properties').write_text(
        'server-ip=127.0.0.1\nserver-port=26651\nonline-mode=false\nenable-rcon=false\n'
        'enable-query=false\nview-distance=3\nsimulation-distance=3\nmax-players=32\n'
        'spawn-protection=0\nlevel-name=world\n', encoding='utf8')
    (server_dir / 'bukkit.yml').write_text('settings:\n  connection-throttle: -1\n', encoding='utf8')
    if label.startswith('yunqi'):
        (server_dir / 'yunqimc.yml').write_text(
            'config-version: 1\nnetwork:\n  flush-consolidation:\n    enabled: ' +
            ('true' if label == 'yunqi_on' else 'false') + '\n    max-pending-flushes: 256\n', encoding='utf8')
    jar = PAPER if label == 'paper' else YUNQI
    java = str(Path(os.environ.get('JAVA_HOME', '')) / 'bin/java.exe') if os.environ.get('JAVA_HOME') else 'java'
    cmd = [java, '-Xms512M', '-Xmx1536M', '-XX:ActiveProcessorCount=4',
           '-Dpaper.disableStartupVersionCheck=true', '-jar', str(jar), '--nogui']
    metadata = {'label': label, 'jar_sha256': digest(jar), 'command': cmd,
                'started_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'memory_at_start': available,
                'process_priority': 'below-normal'}
    (run / 'metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf8')
    server = bot = None
    events = run / 'resource-samples.jsonl'
    started = time.monotonic()
    try:
        with (run / 'server.log').open('wb') as out:
            server = subprocess.Popen(cmd, cwd=server_dir, stdin=subprocess.PIPE, stdout=out,
                                      stderr=subprocess.STDOUT, text=True, creationflags=PROCESS_FLAGS)
            kernel = ctypes.windll.kernel32
            kernel.OpenProcess.restype = ctypes.c_void_p
            handle = kernel.OpenProcess(0x0200 | 0x1000, False, server.pid)
            if not handle:
                raise OSError('Cannot set server CPU affinity')
            try:
                mask = ctypes.c_size_t()
                system_mask = ctypes.c_size_t()
                if not kernel.GetProcessAffinityMask(ctypes.c_void_p(handle), ctypes.byref(mask), ctypes.byref(system_mask)):
                    raise OSError('Cannot read CPU affinity')
                bits = [1 << i for i in range(ctypes.sizeof(ctypes.c_size_t) * 8) if mask.value & (1 << i)]
                if len(bits) < 4 or not kernel.SetProcessAffinityMask(ctypes.c_void_p(handle), ctypes.c_size_t(sum(bits[:4]))):
                    raise OSError('Cannot restrict server to four logical CPUs')
                metadata['affinity_mask'] = sum(bits[:4])
                (run / 'metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf8')
            finally:
                kernel.CloseHandle(ctypes.c_void_p(handle))
            while True:
                if server.poll() is not None:
                    raise RuntimeError(f'Server exited before ready: {server.returncode}')
                state = memory()
                if state['physical_available'] < int(1.5 * 1024**3) or state['commit_available'] < int(1.5 * 1024**3):
                    raise RuntimeError('Stopped during startup by local memory reserve guard')
                contents = (run / 'server.log').read_bytes()
                if b'Done (' in contents:
                    break
                if time.monotonic() - started > 240:
                    raise TimeoutError('Server startup exceeded four minutes')
                time.sleep(2)
            env = os.environ.copy()
            env.pop('YUNQIMC_BENCH_SWITCH_SERVER', None)
            env.update({'YUNQIMC_BENCH_PORT': str(PORT), 'YUNQIMC_BENCH_BOTS': str(args.bots),
                        'YUNQIMC_BENCH_SECONDS': str(args.warmup + args.seconds + 30),
                        'YUNQIMC_BENCH_OUTPUT_DIR': str(run / 'bot-data')})
            with (run / 'bot.log').open('wb') as bot_log:
                bot = subprocess.Popen(['node', str(BENCH / 'run.mjs')], cwd=BENCH, env=env,
                                       stdout=bot_log, stderr=subprocess.STDOUT, creationflags=PROCESS_FLAGS)
                low_count = 0
                bot_event_offset = 0
                while bot.poll() is None:
                    state = memory()
                    record(events, {'monotonic': time.monotonic(), **state, **process_sample(server.pid)})
                    candidates = list((run / 'bot-data').glob('*.jsonl')) if (run / 'bot-data').exists() else []
                    if len(candidates) > 1:
                        raise RuntimeError('Multiple bot event logs appeared')
                    if candidates:
                        with candidates[0].open('rb') as event_input:
                            event_input.seek(bot_event_offset)
                            while True:
                                line = event_input.readline()
                                if not line.endswith(b'\n'):
                                    break
                                event = json.loads(line)
                                bot_event_offset = event_input.tell()
                                if event.get('event') in ('error', 'kicked', 'disconnect'):
                                    raise RuntimeError('Bot disconnected during benchmark: ' + str(event))
                    low = state['physical_available'] < int(1.5 * 1024**3) or state['commit_available'] < int(1.5 * 1024**3)
                    low_count = low_count + 1 if low else 0
                    if low_count >= 3:
                        raise RuntimeError('Stopped by local memory reserve guard')
                    if shutil.disk_usage(suite).free < 3 * 1024**3:
                        raise RuntimeError('Stopped by local free disk reserve guard')
                    if server.poll() is not None:
                        raise RuntimeError(f'Server stopped during benchmark: {server.returncode}')
                    time.sleep(2)
                if bot.returncode:
                    raise RuntimeError(f'Bot controller exited {bot.returncode}')
            bot_files = list((run / 'bot-data').glob('*.jsonl'))
            if len(bot_files) != 1:
                raise RuntimeError('Expected exactly one bot event log')
            bot_events = [json.loads(line) for line in bot_files[0].read_text(encoding='utf8').splitlines()]
            spawned = {e.get('username') for e in bot_events if e['event'] == 'spawn'}
            if len(spawned) != args.bots or any(e['event'] in ('error', 'kicked', 'disconnect') for e in bot_events):
                raise RuntimeError('Bot did not remain connected for the full run')
            stop_process(server, 'stop')
        tick_files = list((server_dir / 'plugins/YunqiBench').glob('ticks-*.csv'))
        if len(tick_files) != 1:
            raise RuntimeError('Expected exactly one tick file')
        result = analyze(tick_files[0], args.seconds)
        resource_rows = [json.loads(line) for line in events.read_text(encoding='utf8').splitlines()]
        cutoff = resource_rows[-1]['monotonic'] - args.seconds
        resource_rows = [row for row in resource_rows if row['monotonic'] >= cutoff]
        if len(resource_rows) < 2:
            raise RuntimeError('Insufficient server resource samples')
        if any(b['monotonic'] - a['monotonic'] > 15 for a, b in zip(resource_rows, resource_rows[1:])):
            raise RuntimeError('Resource monitoring had a gap over 15 seconds; run may have been interrupted')
        cpu = [(b['server_cpu_seconds'] - a['server_cpu_seconds']) / (b['monotonic'] - a['monotonic']) * 100
               for a, b in zip(resource_rows, resource_rows[1:])]
        result['mean_cpu_percent_one_core'] = sum(cpu) / len(cpu)
        result['max_working_set_bytes'] = max(row['server_working_set_bytes'] for row in resource_rows)
        result['max_commit_bytes'] = max(row['server_commit_bytes'] for row in resource_rows)
        stop_event = next((e for e in reversed(bot_events) if e['event'] == 'stop'), None)
        if stop_event is None:
            raise RuntimeError('Bot event log lacks a stop marker')
        cutoff_ms = stop_event['elapsedMs'] - args.seconds * 1000
        rtts = sorted(e['rttMs'] for e in bot_events if e['event'] == 'game_rtt' and e['elapsedMs'] >= cutoff_ms)
        timeouts = sum(1 for e in bot_events if e['event'] == 'probe_timeout' and e['elapsedMs'] >= cutoff_ms)
        if not rtts:
            raise RuntimeError('No game round-trip samples in the measurement window')
        result['game_rtt'] = {'samples': len(rtts), 'timeouts': timeouts,
                              'p50_ms': rtts[math.ceil(.5 * len(rtts)) - 1],
                              'p95_ms': rtts[math.ceil(.95 * len(rtts)) - 1],
                              'p99_ms': rtts[math.ceil(.99 * len(rtts)) - 1]}
        result.update({'label': label, 'jar_sha256': metadata['jar_sha256'], 'bots': args.bots})
        (run / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf8')
        return result
    finally:
        stop_process(bot)
        stop_process(server, 'stop')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--warmup', type=int, default=300)
    parser.add_argument('--seconds', type=int, default=600)
    parser.add_argument('--pairs', type=int, default=5)
    parser.add_argument('--bots', type=int, default=5)
    parser.add_argument('--smoke', action='store_true', help='Run one YunqiMC case only; not a comparison')
    args = parser.parse_args()
    if os.name != 'nt' or args.warmup < 0 or args.seconds < 5 or not 1 <= args.pairs <= 20 or not 1 <= args.bots <= 32:
        raise SystemExit('Requires Windows; warmup >= 0, seconds >= 5, pairs 1..20, bots 1..32')
    if not PAPER.exists() or not YUNQI.exists():
        raise SystemExit('Build YunqiMC and download the pinned Paper 132 baseline first')
    suite = BENCH / 'suite-runs' / dt.datetime.now().strftime('%Y%m%d-%H%M%S')
    suite.mkdir(parents=True, exist_ok=False)
    fixture = suite / 'fixture'
    fixture.mkdir()
    for name in ('world', 'world_nether', 'world_the_end', 'plugins'):
        if name == 'plugins':
            (fixture / name).mkdir()
            for plugin in ('YunqiBench.jar', 'ProtocolLib.jar', 'LuckPerms-Bukkit-5.5.16.jar', 'YunqiProtocolProbe.jar'):
                shutil.copy2(SOURCE / 'plugins' / plugin, fixture / 'plugins' / plugin)
        else:
            shutil.copytree(SOURCE / name, fixture / name)
    shutil.copy2(SOURCE / 'eula.txt', fixture / 'eula.txt')
    inputs = {str(p.relative_to(fixture)): digest(p) for p in fixture.rglob('*') if p.is_file()}
    (suite / 'inputs.json').write_text(json.dumps(inputs, indent=2), encoding='utf8')
    randomizer = random.Random(20261105)
    plan = []
    for index in range(args.pairs):
        for pair in [('paper', 'yunqi_off'), ('yunqi_off', 'yunqi_on')]:
            order = list(pair)
            randomizer.shuffle(order)
            plan.extend((index + 1, pair, label) for label in order)
    if args.smoke:
        plan = [(1, ('paper', 'yunqi_off'), 'yunqi_off')]
    (suite / 'plan.json').write_text(json.dumps({'args': vars(args), 'plan': plan}, indent=2), encoding='utf8')
    print(f'YunqiMC paired benchmark output: {suite}', flush=True)
    for serial, (pair_index, pair, label) in enumerate(plan, 1):
        print(f'[{serial}/{len(plan)}] pair={pair_index} {pair} running {label}', flush=True)
        try:
            result = run_one(suite, fixture, label, serial, args)
            record(suite / 'results.jsonl', {'pair_index': pair_index, 'comparison': pair, **result})
        except Exception as ex:
            record(suite / 'failures.jsonl', {'serial': serial, 'label': label, 'error': str(ex)})
            raise
    print('Suite complete. Inspect results.jsonl and raw files before drawing conclusions.', flush=True)

if __name__ == '__main__':
    main()
