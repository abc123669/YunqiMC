# YunqiMC benchmark protocol

The benchmark controller targets an isolated test server, never a production
address by default. Run `npm ci` in `bench`, then set `YUNQIMC_BENCH_PORT`,
`YUNQIMC_BENCH_BOTS` and `YUNQIMC_BENCH_SECONDS` as needed and run
`node run.mjs`. Default target is `127.0.0.1:26651` with one offline test bot.
Inspect each JSONL event log for spawn and disconnect outcomes before treating
the run as valid. An offline test does not establish authenticated login.

Build `:yunqimc-bench-plugin:jar` and place the exact same JAR on the Paper
and YunqiMC test instances. Its CSV contains individual tick durations and
monotonic timestamps. After a clean shutdown run `node bench/summarize.mjs
<ticks.csv> 300 600` to calculate tick duration percentiles after a five-minute
warmup and during a ten-minute measurement window. A missing dropped-sample
footer or nonzero dropped count means the run must be investigated.

Use independent copies of a fixed world; record JDK, flags, server and plugin
hashes, settings, bot version, host load and world fixture hash. Alternate at
least five Paper/YunqiMC paired runs. Keep simulation distance, view distance,
player behavior and all gameplay settings identical. Report raw data and all
failed runs. The client script is an initial connection/movement probe, not yet
a complete survival or Velocity workload.

The first experimental network change remains off by default. A promotion
requires correctness and compatibility tests plus at least 5% improvement in
a preselected primary metric with a paired confidence interval excluding zero,
and no persistent regression exceeding 3% in other key metrics.

On Windows, `python bench/paired.py` creates a frozen fixture and runs five
randomized pairs each for Paper versus YunqiMC with the option off, and for
the option off versus on. Each run uses five bots, five minutes of warmup and
ten minutes of sampling; the full suite requires more than five hours. The
script restricts the server to four logical processors and stops its own test
processes if memory or free disk reserves fall below the configured limits. Its `--warmup`,
`--seconds`, `--pairs` and `--bots` flags support shorter pilot runs; short
runs are not evidence for the promotion criterion. Results, inputs and raw
logs are under the ignored `bench/suite-runs` directory. Run
`python bench/analyze_pairs.py <suite-directory>` only after a suite completes.
The current controller records client events, tick timing, host memory, and
the server process's cumulative CPU time and memory. A test-player arm animation
triggers a response on the server's main thread; the bot records the round-trip
time and timeouts. This includes game scheduling and is not a pure network RTT.
RTT percentiles include timely replies only; timeouts and late replies are
recorded separately in the raw bot event log and the timeout count.

`python bench/longrun.py` runs the full paired suite, then short 10- and
25-bot load checks and one guarded 24-hour YunqiMC soak with five bots. It stops if any run fails or the resource reserve
is exhausted and writes its stage to the ignored `bench/longrun-status.json`.
The computer must remain running; sleep or shutdown can interrupt the results.
To stop an active test safely, run `powershell -ExecutionPolicy Bypass -File
tools/stop_benchmark.ps1` from the project directory. It targets only the
test bot; the runner then stops its isolated server and marks the run incomplete.
When the accompanying local monitor is running, it writes a paired report to
`dist/benchmark-report.json` after the paired suite completes, and a soak
report to `dist/soak-report.json` only after the soak completes. Successful
load checks produce `dist/load-10-report.json` and `dist/load-25-report.json`.
A stopped or
interrupted suite is recorded as incomplete rather than a successful result.
