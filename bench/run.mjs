// Copyright (c) YunqiMC. Licensed under GPL-3.0-only.
import mineflayer from 'mineflayer';
import { createWriteStream, mkdirSync } from 'node:fs';
import { performance } from 'node:perf_hooks';
import { randomUUID } from 'node:crypto';

const host = process.env.YUNQIMC_BENCH_HOST ?? '127.0.0.1';
const port = Number(process.env.YUNQIMC_BENCH_PORT ?? 26651);
const count = Number(process.env.YUNQIMC_BENCH_BOTS ?? 1);
const seconds = Number(process.env.YUNQIMC_BENCH_SECONDS ?? 60);
const switchServer = process.env.YUNQIMC_BENCH_SWITCH_SERVER ?? '';
const outputDirectory = process.env.YUNQIMC_BENCH_OUTPUT_DIR ?? 'runs';
if (switchServer && !/^[A-Za-z0-9_-]{1,32}$/.test(switchServer)) throw new Error('Invalid proxy server name');
if (!Number.isInteger(count) || count < 1 || count > 64 || !Number.isInteger(port) || port < 1 || port > 65535 || !Number.isInteger(seconds) || seconds < 5 || seconds > 90000) {
  throw new Error('Invalid benchmark configuration: bots 1..64, port 1..65535, seconds 5..90000');
}
mkdirSync(outputDirectory, { recursive: true });
const path = `${outputDirectory}/${new Date().toISOString().replaceAll(':', '-')}-${randomUUID()}.jsonl`;
const stream = createWriteStream(path, { flags: 'wx' });
const start = performance.now();
const bots = [];
let stopping = false;
function log(event, details = {}) {
  stream.write(JSON.stringify({ event, elapsedMs: Math.round(performance.now() - start), ...details }) + '\n');
}
function stop(reason) {
  if (stopping) return;
  stopping = true;
  log('stop', { reason });
  for (const bot of bots) { try { bot.quit(); } catch {} }
  stream.end();
  setTimeout(() => process.exit(0), 500).unref();
}
log('start', { host, port, count, seconds, minecraft: '1.21.11', node: process.version });
console.log(`YunqiMC benchmark output: ${path}`);
for (let i = 0; i < count; i++) {
  await new Promise(resolve => setTimeout(resolve, i === 0 ? 0 : 1500));
  if (stopping) break;
  const username = `YQBench${String(i).padStart(3, '0')}`;
  const bot = mineflayer.createBot({ host, port, username, auth: 'offline', version: '1.21.11' });
  bots.push(bot);
  let spawns = 0;
  let movementTimer;
  let moveForward = false;
  let probeTimer;
  let pendingProbe;
  let probeTimedOut = false;
  bot.on('messagestr', message => {
    if (pendingProbe !== undefined && message.includes('YQBENCH_PROBE')) {
      log(probeTimedOut ? 'game_rtt_late' : 'game_rtt', { username, rttMs: performance.now() - pendingProbe });
      pendingProbe = undefined;
      probeTimedOut = false;
    }
  });
  bot.on('spawn', () => {
    spawns++;
    log('spawn', { username });
    bot.setControlState('forward', true);
    setTimeout(() => { if (!stopping) bot.setControlState('forward', false); }, 5000).unref();
    if (!movementTimer) movementTimer = setInterval(() => {
      if (stopping || !bot.entity) return;
      const direction = moveForward ? 'forward' : 'back';
      moveForward = !moveForward;
      bot.setControlState(direction, true);
      setTimeout(() => { if (!stopping && bot.entity) bot.setControlState(direction, false); }, 3000).unref();
    }, 20000);
    if (!probeTimer) probeTimer = setInterval(() => {
      if (stopping || !bot.entity) return;
      if (pendingProbe !== undefined) {
        if (!probeTimedOut) {
          log('probe_timeout', { username, waitMs: Math.round(performance.now() - pendingProbe) });
          probeTimedOut = true;
        }
        return;
      }
      pendingProbe = performance.now();
      bot.swingArm('right');
    }, 5000);
    if (switchServer && spawns === 1) setTimeout(() => {
      if (!stopping) { log('switch_request', { username, server: switchServer }); bot.chat(`/server ${switchServer}`); }
    }, 10000).unref();
  });
  bot.on('kicked', reason => log('kicked', { username, reason: String(reason).slice(0, 1000) }));
  bot.on('error', err => log('error', { username, message: err.message }));
  bot.on('end', reason => { if (movementTimer) clearInterval(movementTimer); if (probeTimer) clearInterval(probeTimer); if (!stopping) log('disconnect', { username, reason: String(reason) }); });
}
setTimeout(() => stop('duration'), Math.max(0, seconds * 1000 - (performance.now() - start)));
process.once('SIGINT', () => stop('signal'));
process.once('SIGTERM', () => stop('signal'));
