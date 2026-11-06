/* Copyright (c) YunqiMC. Licensed under GPL-3.0-only. */
package dev.yunqimc.api;

import org.jetbrains.annotations.NotNull;

/** Read-only extension implemented by a YunqiMC Bukkit server. */
public interface YunqiServer {
    /** Returns the YunqiMC release version independently of the Paper API version. */
    @NotNull String yunqiVersion();

    /** Returns an immutable snapshot of process-wide counters since startup. */
    @NotNull NetworkStats yunqiNetworkStats();
}
