// Copyright (c) YunqiMC. Licensed under GPL-3.0-only.
import { readFileSync } from 'node:fs';

const filename = process.argv[2];
if (!filename) throw new Error('Usage: node summarize.mjs <ticks.csv> [warmupSeconds] [sampleSeconds]');
const warmup = Number(process.argv[3] ?? 0);
const duration = Number(process.argv[4] ?? Infinity);
if (!Number.isFinite(warmup) || warmup < 0 || duration <= 0 || Number.isNaN(duration)) throw new Error('Invalid sampling window');
const lines = readFileSync(filename, 'utf8').trim().split(/\r?\n/);
if (lines[0] !== 'tick,monotonic_ns,duration_ms') throw new Error('Not a YunqiBench tick file');
const rows = lines.slice(1).filter(line => !line.startsWith('#')).map(line => {
  const [tick, ns, ms] = line.split(',');
  return { tick: Number(tick), ns: BigInt(ns), ms: Number(ms) };
});
if (!rows.length) throw new Error('No tick samples');
const start = rows[0].ns;
const selected = rows.filter(row => {
  const elapsed = Number(row.ns - start) / 1e9;
  return elapsed >= warmup && elapsed < warmup + duration;
});
if (selected.length < 2 || selected.some(row => !Number.isFinite(row.ms))) throw new Error('Insufficient or invalid samples');
const sorted = selected.map(row => row.ms).sort((a, b) => a - b);
const pct = p => sorted[Math.ceil(p * sorted.length) - 1];
const elapsedSeconds = Number(selected.at(-1).ns - selected[0].ns) / 1e9;
const droppedLine = lines.find(line => line.startsWith('# dropped='));
console.log(JSON.stringify({ filename, warmupSeconds: warmup, measuredSeconds: elapsedSeconds, samples: selected.length,
  dropped: droppedLine ? Number(droppedLine.slice('# dropped='.length)) : null,
  mspt: { p50: pct(0.5), p95: pct(0.95), p99: pct(0.99), max: sorted.at(-1) },
  over50ms: sorted.filter(n => n > 50).length, over100ms: sorted.filter(n => n > 100).length,
  observedTicksPerSecond: (selected.length - 1) / elapsedSeconds }, null, 2));
