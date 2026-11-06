#!/usr/bin/env python3
"""Summarize paired runs without hiding missing or failed observations."""
import json
import random
import statistics
import sys
from pathlib import Path

def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python analyze_pairs.py <suite-directory>')
    suite = Path(sys.argv[1])
    if (suite / 'failures.jsonl').exists():
        raise SystemExit('Suite contains failures; inspect raw records before comparison')
    plan = json.loads((suite / 'plan.json').read_text(encoding='utf8'))
    results = [json.loads(line) for line in (suite / 'results.jsonl').read_text(encoding='utf8').splitlines()]
    if len(results) != len(plan['plan']):
        raise SystemExit('Suite is incomplete')
    groups = {}
    for row in results:
        key = (row['pair_index'], tuple(row['comparison']))
        if row['label'] in groups.setdefault(key, {}):
            raise SystemExit(f'Duplicate observation: {key}')
        groups[key][row['label']] = row
    rng = random.Random(20261105)
    output = {'sample_seconds': plan['args']['seconds'], 'warmup_seconds': plan['args']['warmup'],
              'bots': plan['args']['bots'], 'comparisons': [],
              'limitation': 'Windows local development workload; wider protocol latency and broader compatibility are not yet validated; no promotion decision.'}
    for a, b in [('paper', 'yunqi_off'), ('yunqi_off', 'yunqi_on')]:
        pairs = [value for (index, comparison), value in sorted(groups.items()) if comparison == (a, b)]
        if not pairs or any(set(pair) != {a, b} for pair in pairs):
            raise SystemExit(f'Missing data for {a} / {b}')
        metrics = {}
        selectors = {'p95_mspt': lambda r: r['p95_mspt'], 'p99_mspt': lambda r: r['p99_mspt'],
                     'server_cpu': lambda r: r['mean_cpu_percent_one_core'],
                     'server_working_set': lambda r: r['max_working_set_bytes'],
                     'game_rtt_p95': lambda r: r['game_rtt']['p95_ms'],
                     'game_rtt_p99': lambda r: r['game_rtt']['p99_ms']}
        for metric, select in selectors.items():
            try:
                changes = [100 * (select(pair[a]) - select(pair[b])) / select(pair[a]) for pair in pairs]
            except (KeyError, ZeroDivisionError):
                continue
            interval = None
            if len(changes) >= 5:
                means = sorted(statistics.mean(rng.choices(changes, k=len(changes))) for _ in range(10000))
                interval = [means[249], means[9749]]
            metrics[metric] = {'per_pair_improvement_percent': changes, 'mean_improvement_percent': statistics.mean(changes),
                               'bootstrap_95_percent_interval': interval}
        timeout_counts = [{'baseline': pair[a].get('game_rtt', {}).get('timeouts'),
                           'candidate': pair[b].get('game_rtt', {}).get('timeouts')} for pair in pairs]
        output['comparisons'].append({'baseline': a, 'candidate': b, 'pairs': len(pairs),
                                      'metrics': metrics, 'game_rtt_timeouts_by_pair': timeout_counts})
    print(json.dumps(output, indent=2))

if __name__ == '__main__':
    main()
