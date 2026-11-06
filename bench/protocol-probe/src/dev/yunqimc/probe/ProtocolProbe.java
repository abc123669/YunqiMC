/* Copyright (c) YunqiMC. Licensed under GPL-3.0-only. */
package dev.yunqimc.probe;

import com.comphenix.protocol.PacketType;
import com.comphenix.protocol.ProtocolLibrary;
import com.comphenix.protocol.events.ListenerPriority;
import com.comphenix.protocol.events.PacketAdapter;
import com.comphenix.protocol.events.PacketEvent;
import java.util.concurrent.atomic.AtomicLong;
import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.plugin.java.JavaPlugin;

/** Test-only ProtocolLib interception and same-value rewrite of keepalive packets. */
public final class ProtocolProbe extends JavaPlugin {
    private final AtomicLong observed = new AtomicLong();
    private final AtomicLong failures = new AtomicLong();

    @Override public void onEnable() {
        ProtocolLibrary.getProtocolManager().addPacketListener(new PacketAdapter(this, ListenerPriority.NORMAL, PacketType.Play.Server.KEEP_ALIVE) {
            @Override public void onPacketSending(final PacketEvent event) {
                try {
                    final long value = event.getPacket().getLongs().read(0);
                    event.getPacket().getLongs().write(0, value);
                    observed.incrementAndGet();
                } catch (RuntimeException ex) {
                    failures.incrementAndGet();
                    getLogger().warning("ProtocolLib rewrite failed: " + ex.getMessage());
                }
            }
        });
    }

    @Override public boolean onCommand(final CommandSender sender, final Command command, final String label, final String[] args) {
        sender.sendMessage("YunqiMC ProtocolLib probe: keepalive rewrites=" + observed.get() + ", failures=" + failures.get());
        return true;
    }
}
