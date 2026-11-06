# YunqiMC

**YunqiMC — An Independent High-Performance Minecraft Server Core**

YunqiMC is a Minecraft Java Edition 1.21.11 server based on Paper. The project
preserves the Bukkit, Spigot and Paper plugin APIs while developing its own
configuration, diagnostics and performance improvements.

## Development status

**0.1.0-alpha.1 is an experimental preview**, intended for isolated test servers.
Startup, local bot login, saving and reloading a test world, selected plugins,
and Velocity modern forwarding have been exercised. Extended stability testing,
the wider plugin matrix, and paired performance comparisons are incomplete;
there is no performance claim. Back up worlds and plugins before testing.
The experimental network flush consolidation is disabled by default.

Download the server JAR from [Releases](../../releases), run it with Java 21,
and review [the Chinese usage guide](docs/使用说明.md) and
[verification record](docs/验证记录.md). Accept Minecraft's EULA only if you
agree to its terms. Please report reproducible failures with version and sanitized
logs; remove credentials, IP addresses and other private information first.

## Building

Use JDK 21 and Git. The Gradle wrapper verifies the distribution checksum.

```powershell
.\gradlew.bat applyAllPatches
.\gradlew.bat check
.\gradlew.bat createMojmapPaperclipJar
```

The Paper upstream is pinned in `gradle.properties`. Builds download upstream
sources and Minecraft artifacts, and require sufficient memory and disk space.
paperweight requires a Git repository with a commit. When starting from a source
ZIP rather than a clone, initialize a local repository and create an initial
commit before running the wrapper; preserve the included upstream notices.
When Git has no configured committer identity, set `GIT_COMMITTER_NAME` and
`GIT_COMMITTER_EMAIL` for the build process; do not alter global Git settings.
For a memory-limited build use `--max-workers=2` and set
`-Dorg.gradle.jvmargs="-Xmx1536m -XX:MaxMetaspaceSize=512m -XX:ActiveProcessorCount=4"`.

## Test tooling

The benchmark plugin and bot controller are development tools; see
[the benchmark protocol](docs/benchmark.md). The test bot targets the loopback
address and a dedicated test port by default. The independent experimental
flush configuration defaults to disabled.

## Attribution and licensing

Project owner and maintainer: YunqiMC. New YunqiMC code is GPL-3.0-only.
Paper and its upstream projects retain their own copyright notices and license
terms; their license and contributor notices are preserved under
`licenses/upstream/Paper` and in the upstream sources.
The build layout originated from PaperMC's paperweight-examples at commit
`b8d7e6bddaf8596c042a3761aa892f21a6a7d3e9`.

After staging the built Paperclip JAR in `dist`, run
`python tools/package_release.py` to create a deterministic source archive,
source-file hash manifest and release checksums. Run
`python tools/inventory_dependencies.py <jar> <output.json>` to inventory the
embedded dependency JARs and their existing notice filenames.
