/* Copyright (c) YunqiMC. Licensed under GPL-3.0-only. */
package dev.yunqimc.bench;

import com.destroystokyo.paper.event.server.ServerTickEndEvent;
import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.LongAdder;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.block.Chest;
import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerAnimationEvent;
import org.bukkit.inventory.ItemStack;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.plugin.java.JavaPlugin;

/** Records bounded raw tick samples without performing disk writes on the main thread. */
public final class TickRecorder extends JavaPlugin implements Listener {
    private final ArrayBlockingQueue<String> samples = new ArrayBlockingQueue<>(8192);
    private final LongAdder dropped = new LongAdder();
    private volatile boolean running;
    private Thread writer;

    @Override public void onEnable() {
        try {
            final Path dir = this.getDataFolder().toPath();
            Files.createDirectories(dir);
            final Path output = dir.resolve("ticks-" + System.currentTimeMillis() + ".csv");
            final BufferedWriter out = Files.newBufferedWriter(output, StandardCharsets.UTF_8);
            out.write("tick,monotonic_ns,duration_ms\n");
            this.running = true;
            this.writer = new Thread(() -> this.writeSamples(out), "YunqiBench-writer");
            this.writer.setDaemon(true);
            this.writer.start();
            this.getServer().getPluginManager().registerEvents(this, this);
            this.getLogger().info("Recording raw tick samples to " + output);
        } catch (IOException ex) {
            this.getLogger().severe("Cannot start tick recording: " + ex.getMessage());
            this.getServer().getPluginManager().disablePlugin(this);
        }
    }

    @EventHandler public void onTick(final ServerTickEndEvent event) {
        if (!this.samples.offer(event.getTickNumber() + "," + System.nanoTime() + "," + event.getTickDuration())) this.dropped.increment();
    }

    @EventHandler public void onJoin(final PlayerJoinEvent event) {
        if (!Bukkit.isPrimaryThread()) this.getLogger().severe("COMPATIBILITY FAILURE: PlayerJoinEvent was not on the main thread");
        else this.getLogger().info("COMPATIBILITY PASS: PlayerJoinEvent ran on the main thread");
        Bukkit.getScheduler().runTask(this, () -> {
            if (!Bukkit.isPrimaryThread()) this.getLogger().severe("COMPATIBILITY FAILURE: synchronous scheduler was not on the main thread");
            else this.getLogger().info("COMPATIBILITY PASS: synchronous scheduler ran on the main thread");
        });
    }

    @EventHandler public void onAnimation(final PlayerAnimationEvent event) {
        if (event.getPlayer().getName().startsWith("YQBench")) {
            event.getPlayer().sendMessage("YQBENCH_PROBE");
        }
    }

    @Override public boolean onCommand(final CommandSender sender, final Command command, final String label, final String[] args) {
        if (args.length != 1) return false;
        final var world = this.getServer().getWorlds().getFirst();
        final var block = world.getBlockAt(args[0].equalsIgnoreCase("verify-legacy") ? 0 : 16, 250, 0);
        final var key = new NamespacedKey(this, "world_fixture");
        if (args[0].equalsIgnoreCase("prepare")) {
            if (!block.getType().isAir()) { sender.sendMessage("COMPATIBILITY FAILURE: fixture position is not air"); return true; }
            block.setType(Material.CHEST, false);
            final Chest chest = (Chest) block.getState();
            chest.getSnapshotInventory().setItem(0, new ItemStack(Material.DIAMOND, 3));
            chest.update(true, false);
            world.getPersistentDataContainer().set(key, PersistentDataType.STRING, "yunqimc-fixture-v1");
            sender.sendMessage("COMPATIBILITY PREPARED: chest and world PDC");
        } else if (args[0].equalsIgnoreCase("verify") || args[0].equalsIgnoreCase("verify-legacy")) {
            final var state = block.getState();
            final var stack = state instanceof Chest chest ? chest.getBlockInventory().getItem(0) : null;
            final boolean chestOk = stack != null && stack.getType() == Material.DIAMOND && stack.getAmount() == 3;
            final boolean pdcOk = "yunqimc-fixture-v1".equals(world.getPersistentDataContainer().get(key, PersistentDataType.STRING));
            sender.sendMessage(chestOk && pdcOk ? "COMPATIBILITY PASS: chest and world PDC survived restart"
                : "COMPATIBILITY FAILURE: chest=" + chestOk + ", world PDC=" + pdcOk);
        } else return false;
        return true;
    }

    private void writeSamples(final BufferedWriter out) {
        try (out) {
            while (this.running || !this.samples.isEmpty()) {
                final String sample = this.samples.poll(250, TimeUnit.MILLISECONDS);
                if (sample != null) { out.write(sample); out.newLine(); }
            }
            out.write("# dropped=" + this.dropped.sum() + "\n");
        } catch (IOException ex) {
            this.getLogger().severe("Tick recording failed: " + ex.getMessage());
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            this.getLogger().warning("Tick recording interrupted; samples may be incomplete");
        }
    }

    @Override public void onDisable() {
        this.running = false;
        if (this.writer != null) {
            try { this.writer.join(5000); }
            catch (InterruptedException ex) { Thread.currentThread().interrupt(); }
            if (this.writer.isAlive()) this.getLogger().warning("Tick recorder did not stop within five seconds");
        }
    }
}
