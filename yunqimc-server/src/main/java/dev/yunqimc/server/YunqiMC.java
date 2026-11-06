/* Copyright (c) YunqiMC. Licensed under GPL-3.0-only. */
package dev.yunqimc.server;

import dev.yunqimc.server.network.NetworkCounters;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.logging.Logger;
import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.configuration.InvalidConfigurationException;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.craftbukkit.CraftServer;

/** YunqiMC-owned configuration and administrator diagnostics. */
public final class YunqiMC {
    private static final Logger LOGGER = Logger.getLogger("YunqiMC");
    private static final File CONFIG_FILE = new File("yunqimc.yml");
    public static final NetworkCounters NETWORK = new NetworkCounters();
    private static volatile boolean initialized;
    private static boolean flushConsolidation;
    private static int maxPendingFlushes = 256;
    private static volatile int networkSampleRate = 64;

    private YunqiMC() {}

    public static synchronized void initialize(final CraftServer server) {
        if (!initialized) {
            final YamlConfiguration config = new YamlConfiguration();
            try {
                if (CONFIG_FILE.exists()) config.load(CONFIG_FILE);
                config.addDefault("config-version", 1);
                config.addDefault("network.flush-consolidation.enabled", false);
                config.addDefault("network.flush-consolidation.max-pending-flushes", 256);
                config.addDefault("diagnostics.network.sample-rate", 64);
                config.options().copyDefaults(true);
                if (config.getInt("config-version") != 1) throw new IllegalArgumentException("config-version must be 1");
                if (!config.isBoolean("network.flush-consolidation.enabled")) throw new IllegalArgumentException("network.flush-consolidation.enabled must be boolean");
                if (!config.isInt("network.flush-consolidation.max-pending-flushes")) throw new IllegalArgumentException("network.flush-consolidation.max-pending-flushes must be an integer");
                if (!config.isInt("diagnostics.network.sample-rate")) throw new IllegalArgumentException("diagnostics.network.sample-rate must be an integer");
                final int max = config.getInt("network.flush-consolidation.max-pending-flushes");
                if (max < 1 || max > 65536) throw new IllegalArgumentException("network.flush-consolidation.max-pending-flushes must be between 1 and 65536");
                final int sampleRate = config.getInt("diagnostics.network.sample-rate");
                if (sampleRate < 0 || sampleRate > 65536) throw new IllegalArgumentException("diagnostics.network.sample-rate must be between 0 and 65536");
                flushConsolidation = config.getBoolean("network.flush-consolidation.enabled");
                maxPendingFlushes = max;
                networkSampleRate = sampleRate;
                if (!CONFIG_FILE.exists()) config.save(CONFIG_FILE);
                initialized = true;
            } catch (IOException | InvalidConfigurationException | IllegalArgumentException ex) {
                throw new IllegalStateException("Cannot load yunqimc.yml: " + ex.getMessage(), ex);
            }
            LOGGER.info("YunqiMC " + YunqiVersion.VERSION + " initialized; experimental flush consolidation: " + flushConsolidation);
        }
        server.getCommandMap().register("yunqimc", new YunqiCommand());
    }

    public static boolean flushConsolidationEnabled() { return flushConsolidation; }
    public static int maxPendingFlushes() { return maxPendingFlushes; }
    public static int networkSampleRate() { return networkSampleRate; }

    private static final class YunqiCommand extends Command {
        YunqiCommand() {
            super("yunqimc");
            this.description = "YunqiMC server status and diagnostics";
            this.usageMessage = "/yunqimc <version|status|network|diagnostics>";
            this.setPermission("yunqimc.admin");
        }

        @Override
        public boolean execute(final CommandSender sender, final String label, final String[] args) {
            if (!this.testPermission(sender)) return true;
            final String action = args.length == 0 ? "status" : args[0].toLowerCase(java.util.Locale.ROOT);
            switch (action) {
                case "version" -> sender.sendMessage("YunqiMC " + YunqiVersion.VERSION + " | Minecraft 1.21.11 | Paper c5eb0790f199");
                case "status" -> sender.sendMessage("YunqiMC | flush consolidation=" + flushConsolidation + " | processors=" + Runtime.getRuntime().availableProcessors()
                    + " | compression=" + com.velocitypowered.natives.util.Natives.compress.getLoadedVariant()
                    + " | cipher=" + com.velocitypowered.natives.util.Natives.cipher.getLoadedVariant());
                case "network" -> sender.sendMessage("YunqiMC network counters: " + NETWORK.snapshot());
                case "diagnostics" -> {
                    try {
                        final Path directory = Path.of("yunqimc-diagnostics");
                        Files.createDirectories(directory);
                        final Path path = directory.resolve("diagnostics-" + System.currentTimeMillis() + ".txt");
                        Files.writeString(path, "YunqiMC diagnostic snapshot\nTime: " + Instant.now()
                            + "\nJava: " + System.getProperty("java.version")
                            + "\nProcessors: " + Runtime.getRuntime().availableProcessors()
                            + "\nCompression: " + com.velocitypowered.natives.util.Natives.compress.getLoadedVariant()
                            + "\nCipher: " + com.velocitypowered.natives.util.Natives.cipher.getLoadedVariant()
                            + "\nFlush consolidation: " + flushConsolidation
                            + "\nNetwork: " + NETWORK.snapshot() + "\n", StandardCharsets.UTF_8);
                        sender.sendMessage("YunqiMC diagnostics written to " + path);
                    } catch (IOException ex) {
                        LOGGER.warning("Could not write YunqiMC diagnostics: " + ex.getMessage());
                        sender.sendMessage("Could not write YunqiMC diagnostics; see server log.");
                    }
                }
                default -> { return false; }
            }
            return true;
        }
    }
}
