# YunqiMC architecture and provenance

YunqiMC targets Minecraft Java Edition 1.21.11 and preserves the standard
Bukkit, Spigot and Paper APIs. The fork is built from Paper commit
`c5eb0790f199da6c38d0a650e1e5cd5415b28185` using paperweight 2.0.0-beta.19
and the 1.21.11 template at
`b8d7e6bddaf8596c042a3761aa892f21a6a7d3e9`.

`yunqimc-api` compiles the upstream API alongside YunqiMC extensions;
`yunqimc-server` compiles the upstream server and YunqiMC implementation.
The upstream Minecraft and Paper modifications are maintained as patches.
`yunqimc-bench-plugin` is a separate Paper-compatible measurement plugin, and
`bench` contains the test client and raw-data analysis tools.

The Paper `ServerBuildInfo.asString` format and Minecraft API version remain
compatible with Paper. YunqiMC's own release identifier is available through
`YunqiServer.yunqiVersion()`, startup diagnostics and `/yunqimc version`.

YunqiMC retains Paper's main-thread and plugin scheduling behavior. The
experimental Netty flush consolidator is disabled by default and scoped to the
PLAY outbound protocol. Configuration changes take effect after restart.
Its order, reference ownership, protocol boundaries and end-to-end behavior
must pass tests before it may be enabled in production.

Network measurements are aggregate process-wide counters. Byte counts refer
to data passed through the server's transport pipeline; they are not evidence
that a remote client has acknowledged or processed the data. No individual
player labels are retained in the aggregate counters.
Non-writable time is added when each affected interval ends or the channel
closes, and sampled write-completion times are local pipeline observations.

Paper already integrates Velocity native compression and cipher backends. A
future Rust implementation must demonstrate a meaningful end-to-end benefit
against those backends, justify its maintenance cost, and preserve protocol
and plugin semantics. The user's reference to “Papokin” could not be verified;
Pumpkin is a plausible project to study, not a confirmed identification.

New YunqiMC code and patches are GPL-3.0-only. Paper and upstream copyrights
and licenses continue to apply to their contributions. The template and Paper
project have independent authors and are not represented as YunqiMC authors.
